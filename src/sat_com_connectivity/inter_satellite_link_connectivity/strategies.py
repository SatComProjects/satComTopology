from abc import ABC, abstractmethod
from datetime import timedelta
from typing import cast

from pydantic import Field

from sat_com_connectivity.inter_satellite_link_connectivity.addressing_plans import (
    StaticAddressingPlan,
    _is_inter_shell_capable,
)
from sat_com_connectivity.inter_satellite_link_connectivity.models import (
    InterSatelliteConnectivityResult,
    LinkAssociation,
    ConnectivityLedger,
)
from sat_com_connectivity.inter_satellite_link_connectivity.optical_helpers import (
    compute_OISL_feasibility_for_terminal_pair,
    compute_OISL_links_from_terminal_pools_filtered,
)
from sat_com_model.models import (
    Satellite,
    Shell,
    OpticalLinkTerminal,
    InterSatelliteLinkDirection,
    DawnDuskSSOShell,
    WalkerShell,
    InterSatelliteLink,
)


class InterSatelliteConnectivityStrategy(ABC):
    type: str = Field(default="base")

    @abstractmethod
    def compute_strategy(self) -> InterSatelliteConnectivityResult:
        pass


# ---------------------------------------------------------------------------
# Shared helper — build existing link lookup from satellite list
# ---------------------------------------------------------------------------


def _build_existing_link_lookup(
    satellites: list[Satellite],
) -> dict[tuple[int, int], InterSatelliteLink]:
    lookup: dict[tuple[int, int], InterSatelliteLink] = {}
    for sat in satellites:
        for terminal in sat.optical_link_terminals:
            if terminal.link is None:
                continue
            link = terminal.link
            key = (
                min(link.source.topology_uniq_id, link.destination.topology_uniq_id),
                max(link.source.topology_uniq_id, link.destination.topology_uniq_id),
            )
            lookup[key] = link
    return lookup


# ---------------------------------------------------------------------------
# InterShellSSOPriorityConnectivity
# ---------------------------------------------------------------------------


class InterShellSSOPriorityConnectivity(InterSatelliteConnectivityStrategy):
    """
    Two-phase ISL connectivity strategy.

    Phase 1 — inter-shell (priority):
        Terminals flagged for inter-shell connections get first pick.

    Phase 2 — intra-shell (regular):
        Remaining terminals assigned according to each shell's addressing plan.
    """

    type: str = "inter-shell-sso-priority"

    def __init__(
        self,
        satellites: list[Satellite],
        shell_and_plans: list[tuple[Shell, StaticAddressingPlan]],
    ):
        self.satellites = satellites
        self.shell_and_plans = shell_and_plans

    def _compute_inter_shell_associations(self, ledger: ConnectivityLedger) -> None:
        # -----------------------------------------------------------------------
        # Step 1 — collect inter-shell capable terminals
        # -----------------------------------------------------------------------
        unassigned_pool: list[OpticalLinkTerminal] = []

        for sat in self.satellites:
            now = sat.get_movement_model().get_datetime()

            for terminal in sat.optical_link_terminals:
                if not _is_inter_shell_capable(terminal):
                    continue

                # -------------------------------------------------------------------
                # CASE 1 — terminal has NO link
                # -------------------------------------------------------------------
                if terminal.link is None:
                    unassigned_pool.append(terminal)
                    continue

                peer_terminal = terminal.target_optical_link_terminal
                peer_sat = peer_terminal.host_satellite

                # -------------------------------------------------------------------
                # CASE 1.b — Terminal has a link that is already accounted in the ledger
                # -------------------------------------------------------------------
                if ledger.is_link_accounted(terminal.link):
                    continue

                # -------------------------------------------------------------------
                # CASE 2 — intra-shell link → allow override
                # -------------------------------------------------------------------
                if peer_sat.shell.identifier == sat.shell.identifier:
                    unassigned_pool.append(terminal)
                    continue

                # -------------------------------------------------------------------
                # CASE 3 — existing inter-shell link → check feasibility
                # -------------------------------------------------------------------
                result = compute_OISL_feasibility_for_terminal_pair(
                    satellite_a=sat,
                    terminal_a=terminal,
                    satellite_b=peer_sat,
                    terminal_b=peer_terminal,
                    angular_velocity_dt_seconds=1.0,
                )

                # -------------------------------------------------------------------
                # CASE 3.1 — link fully valid
                # -------------------------------------------------------------------
                if not result.temporary_unavailable:
                    ledger.add_updated(
                        LinkAssociation(
                            satellite_a=sat,
                            terminal_a=terminal,
                            satellite_b=peer_sat,
                            terminal_b=peer_terminal,
                            direction=InterSatelliteLinkDirection.INTER_SHELL,
                            link=terminal.link,
                            constraint_a_to_b=result.constraint_a_to_b,
                            constraint_b_to_a=result.constraint_b_to_a,
                            temporary_unavailable=False,
                            recovery_time=None,
                        )
                    )
                    continue

                # -------------------------------------------------------------------
                # CASE 3.2 — link temporarily invalid → evaluate tolerance window
                # -------------------------------------------------------------------

                # Safe duration handling
                estimated_recover_time = result.estimated_recover_time
                if estimated_recover_time is None:
                    ledger.add_obsolete(
                        LinkAssociation(
                            satellite_a=sat,
                            terminal_a=terminal,
                            satellite_b=peer_sat,
                            terminal_b=peer_terminal,
                            direction=InterSatelliteLinkDirection.INTER_SHELL,
                            link=terminal.link,
                            constraint_a_to_b=None,
                            constraint_b_to_a=None,
                        )
                    )
                    unassigned_pool.append(terminal)

                estimated_recover_time = max(0.0, estimated_recover_time)

                min_duration_a = (
                    result.terminal_a.terminal_configuration.minimum_contact_duration_seconds
                )
                min_duration_b = (
                    result.terminal_b.terminal_configuration.minimum_contact_duration_seconds
                )

                # Keep link if violation is SHORT (precision / jitter)
                try_to_keep_link = (
                    estimated_recover_time < min_duration_a
                    or estimated_recover_time < min_duration_b
                )
                # -------------------------------------------------------------------
                # CASE 3.2.A — tolerate temporary violation
                # -------------------------------------------------------------------
                if try_to_keep_link:

                    # Already in temporary state
                    if terminal.link.temporary_unavailable:

                        recovery_time = terminal.link.recovery_time

                        # If recovery time is invalid or passed → kill link
                        if recovery_time is None or recovery_time <= now:
                            ledger.add_obsolete(
                                LinkAssociation(
                                    satellite_a=sat,
                                    terminal_a=terminal,
                                    satellite_b=peer_sat,
                                    terminal_b=peer_terminal,
                                    direction=InterSatelliteLinkDirection.INTER_SHELL,
                                    link=terminal.link,
                                    constraint_a_to_b=None,
                                    constraint_b_to_a=None,
                                )
                            )
                            unassigned_pool.append(terminal)

                        else:
                            # Still inside grace window → keep link
                            ledger.add_updated(
                                LinkAssociation(
                                    satellite_a=sat,
                                    terminal_a=terminal,
                                    satellite_b=peer_sat,
                                    terminal_b=peer_terminal,
                                    direction=InterSatelliteLinkDirection.INTER_SHELL,
                                    link=terminal.link,
                                    constraint_a_to_b=result.constraint_a_to_b,
                                    constraint_b_to_a=result.constraint_b_to_a,
                                    temporary_unavailable=True,
                                    recovery_time=now
                                    + timedelta(seconds=estimated_recover_time),
                                )
                            )

                    else:
                        # Enter temporary unavailable state
                        ledger.add_updated(
                            LinkAssociation(
                                satellite_a=sat,
                                terminal_a=terminal,
                                satellite_b=peer_sat,
                                terminal_b=peer_terminal,
                                direction=InterSatelliteLinkDirection.INTER_SHELL,
                                link=terminal.link,
                                constraint_a_to_b=result.constraint_a_to_b,
                                constraint_b_to_a=result.constraint_b_to_a,
                                temporary_unavailable=True,
                                recovery_time=now
                                + timedelta(seconds=estimated_recover_time),
                            )
                        )

                # -------------------------------------------------------------------
                # CASE 3.2.B — violation too large → remove link
                # -------------------------------------------------------------------
                else:
                    ledger.add_obsolete(
                        LinkAssociation(
                            satellite_a=sat,
                            terminal_a=terminal,
                            satellite_b=peer_sat,
                            terminal_b=peer_terminal,
                            direction=InterSatelliteLinkDirection.INTER_SHELL,
                            link=terminal.link,
                            constraint_a_to_b=None,
                            constraint_b_to_a=None,
                        )
                    )
                    unassigned_pool.append(terminal)

        # -----------------------------------------------------------------------
        # Step 2 — inter-shell assignment via terminal pools
        # -----------------------------------------------------------------------
        sso_pool = [
            t
            for t in unassigned_pool
            if isinstance(t.host_satellite.shell, DawnDuskSSOShell)
            and not ledger.is_terminal_booked(t)
        ]
        walker_pool = [
            t
            for t in unassigned_pool
            if isinstance(t.host_satellite.shell, WalkerShell)
            and not ledger.is_terminal_booked(t)
        ]

        inter_shell_links = compute_OISL_links_from_terminal_pools_filtered(
            terminals_group_1=sso_pool,
            terminals_group_2=walker_pool,
            maximum_range_to_filter_in_km=10_000.0,
            angular_velocity_dt_seconds=1.0,
        )

        for possible_link in inter_shell_links:
            terminal_a = possible_link.terminal_a
            terminal_b = possible_link.terminal_b

            # Displace any intra-shell link currently held by these terminals
            for terminal in (terminal_a, terminal_b):
                if terminal.link is not None:
                    displaced_link = terminal.link
                    peer_terminal = terminal.target_optical_link_terminal
                    peer_sat = peer_terminal.host_satellite
                    if (
                        peer_sat.shell.identifier
                        == terminal.host_satellite.shell.identifier
                    ):
                        ledger.add_obsolete(
                            LinkAssociation(
                                satellite_a=terminal.host_satellite,
                                terminal_a=terminal,
                                satellite_b=peer_sat,
                                terminal_b=peer_terminal,
                                direction=displaced_link.inter_satellite_direction,
                                link=displaced_link,
                                constraint_a_to_b=None,
                                constraint_b_to_a=None,
                            )
                        )
                    else:
                        if not ledger.is_link_obsoleted(terminal.link):
                            raise RuntimeError("Link was not added tot he obsolete")

            ledger.add_new(
                LinkAssociation(
                    satellite_a=terminal_a.host_satellite,
                    terminal_a=terminal_a,
                    satellite_b=terminal_b.host_satellite,
                    terminal_b=terminal_b,
                    direction=InterSatelliteLinkDirection.INTER_SHELL,
                    link=None,
                    constraint_a_to_b=possible_link.constraint_a_to_b,
                    constraint_b_to_a=possible_link.constraint_b_to_a,
                )
            )

    def _compute_intra_shell_associations(self, ledger: ConnectivityLedger) -> None:
        satellites_by_shell: dict[Shell, list[Satellite]] = {}
        for sat in self.satellites:
            satellites_by_shell.setdefault(sat.shell, []).append(sat)

        existing_link_lookup = _build_existing_link_lookup(self.satellites)

        for shell, plan in self.shell_and_plans:
            shell_satellites = satellites_by_shell.get(shell)

            for association in plan.get_link_associations(shell_satellites):

                if ledger.is_terminal_booked(
                    association.terminal_a
                ) or ledger.is_terminal_booked(association.terminal_b):
                    continue

                link_key = (
                    min(
                        association.satellite_a.topology_uniq_id,
                        association.satellite_b.topology_uniq_id,
                    ),
                    max(
                        association.satellite_a.topology_uniq_id,
                        association.satellite_b.topology_uniq_id,
                    ),
                )
                existing_link = existing_link_lookup.get(link_key)

                if existing_link is not None:

                    # Phase 1 already handled this link — skip entirely
                    if ledger.is_link_accounted(existing_link):
                        continue

                    existing_terminal_a = existing_link.get_terminal_for_satellite(
                        association.satellite_a
                    )
                    existing_terminal_b = existing_link.get_terminal_for_satellite(
                        association.satellite_b
                    )

                    if (
                        existing_terminal_a == association.terminal_a
                        and existing_terminal_b == association.terminal_b
                    ):
                        ledger.add_updated(
                            LinkAssociation(
                                satellite_a=association.satellite_a,
                                terminal_a=association.terminal_a,
                                satellite_b=association.satellite_b,
                                terminal_b=association.terminal_b,
                                direction=association.direction,
                                link=existing_link,
                                constraint_a_to_b=association.constraint_a_to_b,
                                constraint_b_to_a=association.constraint_b_to_a,
                            )
                        )
                    else:
                        ledger.add_obsolete(
                            LinkAssociation(
                                satellite_a=association.satellite_a,
                                terminal_a=existing_terminal_a,
                                satellite_b=association.satellite_b,
                                terminal_b=existing_terminal_b,
                                direction=existing_link.inter_satellite_direction,
                                link=existing_link,
                                constraint_a_to_b=None,
                                constraint_b_to_a=None,
                            )
                        )
                        ledger.add_new(
                            LinkAssociation(
                                satellite_a=association.satellite_a,
                                terminal_a=association.terminal_a,
                                satellite_b=association.satellite_b,
                                terminal_b=association.terminal_b,
                                direction=association.direction,
                                link=None,
                                constraint_a_to_b=association.constraint_a_to_b,
                                constraint_b_to_a=association.constraint_b_to_a,
                            )
                        )
                else:
                    ledger.add_new(
                        LinkAssociation(
                            satellite_a=association.satellite_a,
                            terminal_a=association.terminal_a,
                            satellite_b=association.satellite_b,
                            terminal_b=association.terminal_b,
                            direction=association.direction,
                            link=None,
                            constraint_a_to_b=association.constraint_a_to_b,
                            constraint_b_to_a=association.constraint_b_to_a,
                        )
                    )

        # Dangling intra-shell links not covered by any plan
        for link_key, existing_link in existing_link_lookup.items():
            if ledger.is_link_accounted(existing_link):
                continue

            source = cast(Satellite, existing_link.source)
            destination = cast(Satellite, existing_link.destination)

            if source.shell.identifier != destination.shell.identifier:
                continue

            source_terminal = existing_link.get_terminal_for_satellite(source)
            dest_terminal = existing_link.get_terminal_for_satellite(destination)

            if ledger.is_terminal_booked(source_terminal) or ledger.is_terminal_booked(
                dest_terminal
            ):
                continue

            ledger.add_obsolete(
                LinkAssociation(
                    satellite_a=source,
                    terminal_a=source_terminal,
                    satellite_b=destination,
                    terminal_b=dest_terminal,
                    direction=existing_link.inter_satellite_direction,
                    link=existing_link,
                    constraint_a_to_b=None,
                    constraint_b_to_a=None,
                )
            )
        for link_key, existing_link in existing_link_lookup.items():
            if ledger.is_link_accounted(existing_link):
                continue

            source = cast(Satellite, existing_link.source)
            destination = cast(Satellite, existing_link.destination)

            ledger.add_obsolete(
                LinkAssociation(
                    satellite_a=source,
                    terminal_a=existing_link.get_terminal_for_satellite(source),
                    satellite_b=destination,
                    terminal_b=existing_link.get_terminal_for_satellite(destination),
                    direction=existing_link.inter_satellite_direction,
                    link=existing_link,
                    constraint_a_to_b=None,
                    constraint_b_to_a=None,
                )
            )

    def compute_strategy(self) -> InterSatelliteConnectivityResult:
        ledger = ConnectivityLedger()
        self._compute_inter_shell_associations(ledger)
        self._compute_intra_shell_associations(ledger)
        return ledger.to_result()


# ---------------------------------------------------------------------------
# IntraShellStaticConnectivity
# ---------------------------------------------------------------------------


class IntraShellStaticConnectivity(InterSatelliteConnectivityStrategy):
    """
    Static ISL connectivity strategy — no inter-shell assignment.
    Follows each shell's StaticAddressingPlan only.
    """

    type: str = "intra-shell-static-connectivity"

    def __init__(
        self,
        satellites: list[Satellite],
        shell_and_plans: list[tuple[Shell, StaticAddressingPlan]],
    ):
        self.satellites = satellites
        self.shell_and_plans = shell_and_plans

    def compute_strategy(self) -> InterSatelliteConnectivityResult:
        ledger = ConnectivityLedger()

        satellites_by_shell: dict[Shell, list[Satellite]] = {}
        for sat in self.satellites:
            satellites_by_shell.setdefault(sat.shell, []).append(sat)

        existing_link_lookup = _build_existing_link_lookup(self.satellites)

        for shell, plan in self.shell_and_plans:
            shell_satellites = satellites_by_shell.get(shell)
            for association in plan.get_link_associations(shell_satellites):
                link_key = (
                    min(
                        association.satellite_a.topology_uniq_id,
                        association.satellite_b.topology_uniq_id,
                    ),
                    max(
                        association.satellite_a.topology_uniq_id,
                        association.satellite_b.topology_uniq_id,
                    ),
                )
                existing_link = existing_link_lookup.get(link_key)

                if existing_link is not None:
                    if ledger.is_link_accounted(existing_link):
                        continue

                    existing_terminal_a = existing_link.get_terminal_for_satellite(
                        association.satellite_a
                    )
                    existing_terminal_b = existing_link.get_terminal_for_satellite(
                        association.satellite_b
                    )

                    if (
                        existing_terminal_a == association.terminal_a
                        and existing_terminal_b == association.terminal_b
                    ):
                        ledger.add_updated(
                            LinkAssociation(
                                satellite_a=association.satellite_a,
                                terminal_a=association.terminal_a,
                                satellite_b=association.satellite_b,
                                terminal_b=association.terminal_b,
                                direction=association.direction,
                                link=existing_link,
                                constraint_a_to_b=association.constraint_a_to_b,
                                constraint_b_to_a=association.constraint_b_to_a,
                            )
                        )
                    else:
                        ledger.add_obsolete(
                            LinkAssociation(
                                satellite_a=association.satellite_a,
                                terminal_a=existing_terminal_a,
                                satellite_b=association.satellite_b,
                                terminal_b=existing_terminal_b,
                                direction=existing_link.inter_satellite_direction,
                                link=existing_link,
                                constraint_a_to_b=None,
                                constraint_b_to_a=None,
                            )
                        )
                        ledger.add_new(
                            LinkAssociation(
                                satellite_a=association.satellite_a,
                                terminal_a=association.terminal_a,
                                satellite_b=association.satellite_b,
                                terminal_b=association.terminal_b,
                                direction=association.direction,
                                link=None,
                                constraint_a_to_b=association.constraint_a_to_b,
                                constraint_b_to_a=association.constraint_b_to_a,
                            )
                        )
                else:
                    ledger.add_new(
                        LinkAssociation(
                            satellite_a=association.satellite_a,
                            terminal_a=association.terminal_a,
                            satellite_b=association.satellite_b,
                            terminal_b=association.terminal_b,
                            direction=association.direction,
                            link=None,
                            constraint_a_to_b=association.constraint_a_to_b,
                            constraint_b_to_a=association.constraint_b_to_a,
                        )
                    )

        # Dangling links not covered by any plan
        for link_key, existing_link in existing_link_lookup.items():
            if ledger.is_link_accounted(existing_link):
                continue

            source = cast(Satellite, existing_link.source)
            destination = cast(Satellite, existing_link.destination)

            ledger.add_obsolete(
                LinkAssociation(
                    satellite_a=source,
                    terminal_a=existing_link.get_terminal_for_satellite(source),
                    satellite_b=destination,
                    terminal_b=existing_link.get_terminal_for_satellite(destination),
                    direction=existing_link.inter_satellite_direction,
                    link=existing_link,
                    constraint_a_to_b=None,
                    constraint_b_to_a=None,
                )
            )

        return ledger.to_result()
