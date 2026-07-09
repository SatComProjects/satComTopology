import inspect
import math
import uuid
import warnings
from abc import abstractmethod, ABC
from dataclasses import field, dataclass
from enum import Enum

from sat_com_builder.links.inter_satellite_link_generator import (
    generate_walker_star_constellation_grid,
    generate_walker_delta_constellation_grid,
    generate_sun_synchronous_constellation_grid,
    generate_checkerboard_walker_star_constellation_grid,
    generate_checkerboard_walker_delta_constellation_grid,
)
from sat_com_connectivity.inter_satellite_link_connectivity.models import (
    PossibleOpticalLink,
    LinkAssociation,
)
from sat_com_connectivity.inter_satellite_link_connectivity.optical_helpers import (
    compute_OISL_links_from_terminal_pools,
)
from sat_com_model.models import (
    WalkerShell,
    Satellite,
    OpticalLinkTerminal,
    InterSatelliteLinkDirection,
    DawnDuskSSOShell,
    InterSatelliteLinkOrientation,
)

# ---------------------------------------------------------------------------
# ADDRESSING PLAN — static topology descriptor
# One plan per shell type. Describes which satellite connects to which,
# and on which terminal, without touching simulation state.
# ---------------------------------------------------------------------------


_ORBITAL_INTER_SATELLITE_LINK_ORIENTATION = {
    InterSatelliteLinkOrientation.INTRA_PLANE_FORWARD,
    InterSatelliteLinkOrientation.INTRA_PLANE_BACKWARD,
}

_ADJACENT_INTER_SATELLITE_LINK_ORIENTATION = {
    InterSatelliteLinkOrientation.INTER_PLANE_RIGHT,
    InterSatelliteLinkOrientation.INTER_PLANE_LEFT,
}

_INTER_SHELL_ORIENTATIONS = {
    InterSatelliteLinkOrientation.INTER_SHELL_FORWARD,
    InterSatelliteLinkOrientation.INTER_SHELL_BACKWARD,
    InterSatelliteLinkOrientation.INTER_SHELL_LEFT,
    InterSatelliteLinkOrientation.INTER_SHELL_RIGHT,
}

_ADJACENT_INTRA_SHELL_RULES = {
    InterSatelliteLinkOrientation.INTER_PLANE_RIGHT: InterSatelliteLinkOrientation.INTER_PLANE_LEFT,
    InterSatelliteLinkOrientation.INTER_PLANE_LEFT: InterSatelliteLinkOrientation.INTER_PLANE_RIGHT,
}


def _filter_by_orientation(
    candidates: list[PossibleOpticalLink],
    expected_a: set[InterSatelliteLinkOrientation],
    expected_b: set[InterSatelliteLinkOrientation],
) -> list[PossibleOpticalLink]:
    return [
        c
        for c in candidates
        if c.terminal_a.descriptor in expected_a
        and c.terminal_b.descriptor in expected_b
    ]


def _filter_terminals_by_orientation(
    candidates: list[OpticalLinkTerminal],
    expected: set[InterSatelliteLinkOrientation],
) -> list[OpticalLinkTerminal]:
    possible_candidates = []
    for candidate in candidates:
        for possibility in candidate.orientation_possibilities:
            if possibility in expected:
                possible_candidates.append(candidate)

    return possible_candidates


def _filter_terminals_pool_by_orientation(
    pool_a: list[OpticalLinkTerminal],
    pool_b: list[OpticalLinkTerminal],
    expected_a: set[InterSatelliteLinkOrientation],
    expected_b: set[InterSatelliteLinkOrientation],
):
    return (
        _filter_terminals_by_orientation(pool_a, expected_a),
        _filter_terminals_by_orientation(pool_b, expected_b),
    )


def _is_inter_shell_capable(terminal: OpticalLinkTerminal) -> bool:
    """A terminal is inter-shell capable if any of its orientation_possibilities
    includes an INTER_SHELL orientation."""
    return any(
        o in _INTER_SHELL_ORIENTATIONS for o in terminal.orientation_possibilities
    )


class StaticAddressingPlan(ABC):
    """
    Base class for static intra-shell addressing plans.
    A plan is a pure descriptor — it computes intended connectivity
    but does not create or modify any simulation objects.
    """

    @abstractmethod
    def get_link_associations(
        self, satellites: list[Satellite]
    ) -> list["LinkAssociation"]:
        """
        Compute the full set of intended terminal-to-terminal associations
        for all satellites in this shell.
        Returns LinkAssociation objects with link=None — the SimulationManager
        is responsible for actually creating the ISL objects.
        """
        pass

    @abstractmethod
    def get_type(self) -> str:
        raise NotImplementedError()


@dataclass
class LinkSelectionDebugRecord:
    a_id: int
    b_id: int
    direction: InterSatelliteLinkDirection
    # candidates actually eligible for booking (grouped orientation logic)
    eligible_candidates: list[PossibleOpticalLink] = field(default_factory=list)
    # candidates excluded by the orientation grouping (e.g. LEFT-LEFT, RIGHT-RIGHT)
    # kept only for diagnosis, never used for booking
    outcome: str = ""  # "booked" | "bumped" | "failed"
    booked_pair: tuple[uuid.UUID, uuid.UUID] | None = None
    notes: list[str] = field(default_factory=list)


class WalkerStaticAddressingPlan(StaticAddressingPlan):

    def __init__(self, walker_shell: WalkerShell):
        self.walker_shell = walker_shell
        self.grid: list[tuple[int, int, InterSatelliteLinkDirection]] = []
        self._terminal_assignment: dict[
            tuple[int, int], tuple[OpticalLinkTerminal, OpticalLinkTerminal]
        ] = {}
        self._terminals_selected = False
        self.debug_records: list[LinkSelectionDebugRecord] = []

        self.get_type()

    def _select_static_terminals(
        self, satellite_lookup: dict[int, Satellite], debug: bool = False
    ) -> None:
        booked_terminals: set[OpticalLinkTerminal] = set()
        booked_by: dict[
            OpticalLinkTerminal, tuple[int, int, InterSatelliteLinkDirection]
        ] = {}
        self.debug_records = []

        for a_id, b_id, direction in self.grid:
            sat_a = satellite_lookup.get(a_id)
            sat_b = satellite_lookup.get(b_id)

            if sat_a is None or sat_b is None:
                warnings.warn(
                    f"Satellite id {a_id if sat_a is None else b_id} not found "
                    f"in satellite list — skipping link ({a_id}, {b_id})."
                )
                continue

            record = LinkSelectionDebugRecord(a_id=a_id, b_id=b_id, direction=direction)

            if direction == InterSatelliteLinkDirection.ADJACENT:
                sources_left, destinations_right = (
                    _filter_terminals_pool_by_orientation(
                        sat_a.optical_link_terminals,
                        sat_b.optical_link_terminals,
                        {InterSatelliteLinkOrientation.INTER_PLANE_LEFT},
                        {InterSatelliteLinkOrientation.INTER_PLANE_RIGHT},
                    )
                )
                sources_right, destinations_left = (
                    _filter_terminals_pool_by_orientation(
                        sat_a.optical_link_terminals,
                        sat_b.optical_link_terminals,
                        {InterSatelliteLinkOrientation.INTER_PLANE_RIGHT},
                        {InterSatelliteLinkOrientation.INTER_PLANE_LEFT},
                    )
                )

                total_source_terminals = len(sources_left) + len(sources_right)
                total_destination_terminals = len(destinations_left) + len(
                    destinations_right
                )

                candidates_left_right = compute_OISL_links_from_terminal_pools(
                    terminals_group_1=sources_left,
                    terminals_group_2=destinations_right,
                    angular_velocity_dt_seconds=1.0,
                )
                candidates_right_left = compute_OISL_links_from_terminal_pools(
                    terminals_group_1=destinations_left,
                    terminals_group_2=sources_right,
                    angular_velocity_dt_seconds=1.0,
                )
                # Previously excluded — confirmed geometrically valid via azimuth steering
                # (~175°), and necessary to resolve conflicts that pure LEFT-RIGHT /
                # RIGHT-LEFT pairing can't. Included as real, bookable candidates now.
                candidates_left_left = compute_OISL_links_from_terminal_pools(
                    terminals_group_1=sources_left,
                    terminals_group_2=destinations_left,
                    angular_velocity_dt_seconds=1.0,
                )
                candidates_right_right = compute_OISL_links_from_terminal_pools(
                    terminals_group_1=sources_right,
                    terminals_group_2=destinations_right,
                    angular_velocity_dt_seconds=1.0,
                )

                all_candidates: list[PossibleOpticalLink] = (
                    candidates_left_right
                    + candidates_right_left
                    + candidates_left_left
                    + candidates_right_right
                )
                all_candidates.sort(key=lambda x: x.selection_score)
                pool_a = sources_left + sources_right
                pool_b = destinations_left + destinations_right

            elif direction == InterSatelliteLinkDirection.ORBITAL:
                sources_forward, destinations_backward = (
                    _filter_terminals_pool_by_orientation(
                        sat_a.optical_link_terminals,
                        sat_b.optical_link_terminals,
                        {InterSatelliteLinkOrientation.INTRA_PLANE_FORWARD},
                        {InterSatelliteLinkOrientation.INTRA_PLANE_BACKWARD},
                    )
                )
                sources_backward, destinations_forward = (
                    _filter_terminals_pool_by_orientation(
                        sat_a.optical_link_terminals,
                        sat_b.optical_link_terminals,
                        {InterSatelliteLinkOrientation.INTRA_PLANE_BACKWARD},
                        {InterSatelliteLinkOrientation.INTRA_PLANE_FORWARD},
                    )
                )
                total_source_terminals = len(sources_forward) + len(sources_backward)
                total_destination_terminals = len(destinations_backward) + len(
                    destinations_forward
                )

                candidates_case_1 = compute_OISL_links_from_terminal_pools(
                    terminals_group_1=sources_forward,
                    terminals_group_2=destinations_backward,
                    angular_velocity_dt_seconds=1.0,
                )
                candidates_case_2 = compute_OISL_links_from_terminal_pools(
                    terminals_group_1=sources_backward,
                    terminals_group_2=destinations_forward,
                    angular_velocity_dt_seconds=1.0,
                )

                all_candidates = candidates_case_1 + candidates_case_2
                all_candidates.sort(key=lambda x: x.selection_score)
                pool_a = sources_forward + sources_backward
                pool_b = destinations_forward + destinations_backward

            else:
                raise ValueError(
                    "This direction is not recognized by the addressing plan."
                )

            record.eligible_candidates = list(all_candidates)

            if not all_candidates:
                msg = (
                    f"No valid {direction.name} terminal pair found between "
                    f"{sat_a.satellite_name} and {sat_b.satellite_name} — skipping.\n"
                    f"{sat_a.satellite_name} has {total_source_terminals} terminal(s) for this direction. "
                    f"{sat_b.satellite_name} has {total_destination_terminals} terminal(s) for this direction. "
                    f"impossible connection might be due to an azimuth constraint as a dead zone is possible in some cases."
                )
                warnings.warn(msg)
                record.outcome = "failed"
                record.notes.append(msg)
                if debug:
                    self.debug_records.append(record)
                continue

            candidate_selected_rank = 0
            best = all_candidates[candidate_selected_rank]

            while (
                best.terminal_a in booked_terminals
                or best.terminal_b in booked_terminals
            ):
                record.notes.append(
                    f"Candidate rank {candidate_selected_rank} rejected: "
                    f"terminal already booked by "
                    f"{booked_by.get(best.terminal_a) or booked_by.get(best.terminal_b)}"
                )
                candidate_selected_rank += 1
                if candidate_selected_rank > len(all_candidates) - 1:
                    conflicts = [
                        f"terminal {t.terminal_id} already booked by link {booked_by.get(t)}"
                        for t in pool_a + pool_b
                        if t in booked_terminals
                    ]
                    warnings.warn(
                        f"No available terminal found for the {direction} link between {a_id} and {b_id}. "
                        f"Conflicts: {conflicts}"
                    )
                    best = None
                    record.outcome = "failed"
                    record.notes.append(
                        f"Exhausted all {len(all_candidates)} candidates. Conflicts: {conflicts}"
                    )
                    break
                best = all_candidates[candidate_selected_rank]

            if best is None:
                warnings.warn(
                    "No terminal pair could be permanently assigned for this link."
                )
                if debug:
                    self.debug_records.append(record)
                continue

            if best.terminal_a not in sat_a.optical_link_terminals:
                # switch
                best = PossibleOpticalLink(
                    satellite_a=sat_a,
                    satellite_b=sat_b,
                    terminal_a=best.terminal_b,
                    terminal_b=best.terminal_a,
                    selection_score=best.selection_score,
                    constraint_a_to_b=best.constraint_b_to_a,
                    constraint_b_to_a=best.constraint_a_to_b,
                    estimated_duration=best.estimated_duration,
                    temporary_unavailable=best.temporary_unavailable,
                    estimated_recover_time=best.estimated_recover_time,
                    bidirectional_possible=best.bidirectional_possible,
                )

            booked_terminals.add(best.terminal_a)
            booked_terminals.add(best.terminal_b)
            booked_by[best.terminal_a] = (a_id, b_id, direction)
            booked_by[best.terminal_b] = (a_id, b_id, direction)

            self._terminal_assignment[(a_id, b_id)] = (best.terminal_a, best.terminal_b)
            record.outcome = "booked"
            record.booked_pair = (
                best.terminal_a.terminal_id,
                best.terminal_b.terminal_id,
            )

            if debug:
                self.debug_records.append(record)

        self._terminals_selected = True

    def print_debug_report(self, only_failed: bool = True) -> None:
        """
        Human-readable summary of the static selection pass. Requires
        `_select_static_terminals(..., debug=True)` to have been run first.
        For each failed link, reports whether a same-side (LEFT-LEFT /
        RIGHT-RIGHT) pairing would have been geometrically valid — this is
        the diagnostic for the azimuth-steering-cone hypothesis.
        """
        if not self.debug_records:
            print(
                "No debug records available. Run _select_static_terminals(..., debug=True) first."
            )
            return

        for r in self.debug_records:
            if only_failed and r.outcome == "booked":
                continue

            print(
                f"--- Link ({r.a_id}, {r.b_id}) [{r.direction.name}] -> {r.outcome.upper()} ---"
            )
            print(f"  Eligible candidates found: {len(r.eligible_candidates)}")
            for c in r.eligible_candidates[:5]:
                print(
                    f"    score={c.selection_score:.2f} terminal_a={c.terminal_a.terminal_id} terminal_b={c.terminal_b.terminal_id}"
                )
            for note in r.notes:
                print(f"  note: {note}")
            print()

    def _build_associations_from_grid(
        self,
        satellite_lookup: dict[int, Satellite],
    ) -> list[LinkAssociation]:
        if not self._terminals_selected:
            self._select_static_terminals(satellite_lookup, debug=True)
            self.print_debug_report()

        associations: list[LinkAssociation] = []

        for a_id, b_id, direction in self.grid:
            sat_a = satellite_lookup.get(a_id)
            sat_b = satellite_lookup.get(b_id)
            if sat_a is None or sat_b is None:
                continue

            assignment = self._terminal_assignment.get((a_id, b_id))
            if assignment is None:
                continue

            terminal_a, terminal_b = assignment

            candidates = compute_OISL_links_from_terminal_pools(
                terminals_group_1=[terminal_a],
                terminals_group_2=[terminal_b],
                angular_velocity_dt_seconds=1.0,
            )

            if not candidates:
                warnings.warn(
                    f"Statically assigned terminals for link ({a_id}, {b_id}) can't compute "
                    f"a valid constraint at this time step — skipping."
                )
                continue

            best = next(
                (
                    c
                    for c in candidates
                    if c.terminal_a == terminal_a and c.terminal_b == terminal_b
                ),
                None,
            )

            if best is None:
                warnings.warn(
                    f"Statically assigned terminals for link ({a_id}, {b_id}) returned "
                    f"candidates but none matched the frozen terminal orientation — skipping."
                )
                continue

            associations.append(
                LinkAssociation(
                    satellite_a=sat_a,
                    terminal_a=best.terminal_a,
                    satellite_b=sat_b,
                    terminal_b=best.terminal_b,
                    direction=direction,
                    link=None,
                    constraint_a_to_b=best.constraint_a_to_b,
                    constraint_b_to_a=best.constraint_b_to_a,
                )
            )

        return associations

    def get_link_associations(
        self, satellites: list[Satellite]
    ) -> list[LinkAssociation]:
        satellite_lookup = {sat.object_id: sat for sat in satellites}

        return self._build_associations_from_grid(satellite_lookup)

    @abstractmethod
    def get_type(self) -> str:
        raise NotImplementedError()


class OldWalkerStaticAddressingPlan(StaticAddressingPlan):
    """
    Static addressing plan for a Walker constellation (delta or star).
    Encodes the intra-plane (ORBITAL) and inter-plane (ADJACENT) mesh topology.
    Uses compute_OISL_links_from_terminal_pools to select the best
    terminal pair per intended link, filtered by descriptor group so ORBITAL
    links never land on ADJACENT-facing terminals and vice versa.

    Walker constellation has 4 intra-shell ISL. two inter-plane, two intra-plane.
    This addressing plan generate the grid according to the old pattern, that has been used and tested.

    What it does now is parameterizing the optical link terminals pairs. The rules are the following:
    --
    For a satellite A and a Satellite B, both on the same plane, both neighbors according to the plan.
    Satellite A will have two terminals that can connect to satellite B, one with INTRA_PLANE_FORWARD and the other with INTRA_PLANE_BACKWARD.
    The one that will be selected will be the one with the best alignment. Has there is no ambiguity, it should be enough to always tales the best alignment score.
    Satellite B will have the same but in reverse.

    So for the link A to B, we will first try to connect the terminal of A with INTRA_PLANE_FORWARD with the terminal of B with INTRA_PLANE_BACKWARD.
    If this pair is not available (that should not happen for orbital link), we will try the other way around, so A with INTRA_PLANE_BACKWARD and B with INTRA_PLANE_FORWARD.
    --
    For a Satellite A and a Satellite B, both on adjacent plane, both neighbors (and connected) according to the plan.
    The same logic apply, as before. But this time it can have an ambiguity near the pole, has the alignment can be very close between the left and the right.
    So we will try first the terminal of A with INTER_PLANE_RIGHT with the terminal of B with INTER_PLANE_LEFT, then the other way around if the first pair is not available.

    """

    def __init__(self, walker_shell: WalkerShell):
        self.walker_shell = walker_shell

        self.grid: list[tuple[int, int, InterSatelliteLinkDirection]] = []

        self.get_type()

    def _build_associations_from_grid(
        self,
        satellite_lookup: dict[int, Satellite],
    ) -> list[LinkAssociation]:
        associations: list[LinkAssociation] = []
        booked_terminals: set[OpticalLinkTerminal] = set()

        for a_id, b_id, direction in self.grid:
            sat_a = satellite_lookup.get(a_id)
            sat_b = satellite_lookup.get(b_id)

            if sat_a is None or sat_b is None:
                warnings.warn(
                    f"Satellite id {a_id if sat_a is None else b_id} not found "
                    f"in satellite list — skipping link ({a_id}, {b_id})."
                )
                continue

            if direction == InterSatelliteLinkDirection.ADJACENT:
                sources_left, destinations_right = (
                    _filter_terminals_pool_by_orientation(
                        sat_a.optical_link_terminals,
                        sat_b.optical_link_terminals,
                        {InterSatelliteLinkOrientation.INTER_PLANE_LEFT},
                        {InterSatelliteLinkOrientation.INTER_PLANE_RIGHT},
                    )
                )
                sources_right, destinations_left = (
                    _filter_terminals_pool_by_orientation(
                        sat_a.optical_link_terminals,
                        sat_b.optical_link_terminals,
                        {InterSatelliteLinkOrientation.INTER_PLANE_RIGHT},
                        {InterSatelliteLinkOrientation.INTER_PLANE_LEFT},
                    )
                )

                total_source_terminals = len(sources_left) + len(sources_right)
                total_destination_terminals = len(destinations_left) + len(
                    destinations_right
                )

                candidates_left_right = compute_OISL_links_from_terminal_pools(
                    terminals_group_1=sources_left,
                    terminals_group_2=destinations_right,
                    angular_velocity_dt_seconds=1.0,
                )
                candidates_right_left = compute_OISL_links_from_terminal_pools(
                    terminals_group_1=destinations_left,
                    terminals_group_2=sources_right,
                    angular_velocity_dt_seconds=1.0,
                )
                # Previously excluded — confirmed geometrically valid via azimuth steering
                # (~175°), and necessary to resolve conflicts that pure LEFT-RIGHT /
                # RIGHT-LEFT pairing can't. Included as real, bookable candidates now.
                candidates_left_left = compute_OISL_links_from_terminal_pools(
                    terminals_group_1=sources_left,
                    terminals_group_2=destinations_left,
                    angular_velocity_dt_seconds=1.0,
                )
                candidates_right_right = compute_OISL_links_from_terminal_pools(
                    terminals_group_1=sources_right,
                    terminals_group_2=destinations_right,
                    angular_velocity_dt_seconds=1.0,
                )

                all_candidates: list[PossibleOpticalLink] = (
                    candidates_left_right
                    + candidates_right_left
                    + candidates_left_left
                    + candidates_right_right
                )
                all_candidates.sort(key=lambda x: x.selection_score)

            elif direction == InterSatelliteLinkDirection.ORBITAL:
                sources_forward, destinations_backward = (
                    _filter_terminals_pool_by_orientation(
                        sat_a.optical_link_terminals,
                        sat_b.optical_link_terminals,
                        {InterSatelliteLinkOrientation.INTRA_PLANE_FORWARD},
                        {InterSatelliteLinkOrientation.INTRA_PLANE_BACKWARD},
                    )
                )
                sources_backward, destinations_forward = (
                    _filter_terminals_pool_by_orientation(
                        sat_a.optical_link_terminals,
                        sat_b.optical_link_terminals,
                        {InterSatelliteLinkOrientation.INTRA_PLANE_BACKWARD},
                        {InterSatelliteLinkOrientation.INTRA_PLANE_FORWARD},
                    )
                )
                total_source_terminals = len(sources_forward) + len(sources_backward)
                total_destination_terminals = len(destinations_backward) + len(
                    destinations_forward
                )

                candidates_case_1 = compute_OISL_links_from_terminal_pools(
                    terminals_group_1=sources_forward,
                    terminals_group_2=destinations_backward,
                    angular_velocity_dt_seconds=1.0,
                )
                candidates_case_2 = compute_OISL_links_from_terminal_pools(
                    terminals_group_1=sources_backward,
                    terminals_group_2=destinations_forward,
                    angular_velocity_dt_seconds=1.0,
                )

                all_candidates: list[PossibleOpticalLink] = (
                    candidates_case_1 + candidates_case_2
                )
                all_candidates.sort(key=lambda x: x.selection_score)

            else:
                raise ValueError(
                    "This direction is not recognized by the addressing plan."
                )

            if not all_candidates:
                warnings.warn(
                    f"No valid {direction.name} terminal pair found between "
                    f"{sat_a.satellite_name} and {sat_b.satellite_name} — skipping.\n"
                    f"{sat_a.satellite_name} has {total_source_terminals} terminal(s) for this direction."
                    f"{sat_b.satellite_name} has {total_destination_terminals} terminal(s) for this direction."
                    f"{sat_b.satellite_name} has {total_destination_terminals} terminal(s) for this direction."
                    f"impossible connection might be due to an azimuth constraint as a dead zone is possible in some cases."
                )
                continue

            # The best candidate is the one with the best score. But in some case where the satellite are
            # approaching the descending / ascending transition, the LEFT and right has no sense. There is a time step t
            # where the satellite from the adjacent orbit that was at right has a better angle to the left. but the left
            # is already booked before by the other adjacent sat that is still on the left ! So we have to iterate
            # if not will  have two satellites that will try to tke the same terminal

            candidate_selected_rank = 0

            best = all_candidates[candidate_selected_rank]

            while (
                best.terminal_a in booked_terminals
                or best.terminal_b in booked_terminals
            ):
                warnings.warn(
                    "Special situation where the satellite alignment is ambiguous"
                )
                candidate_selected_rank += 1
                if candidate_selected_rank > len(all_candidates) - 1:
                    warnings.warn(
                        f"No available terminal found for the {direction} link between {a_id} and {b_id}."
                    )
                    best = None
                    break

                best = all_candidates[candidate_selected_rank]

            if best is None:
                warnings.warn("No link will be created as no terminal are available.")
                continue

            booked_terminals.add(best.terminal_a)
            booked_terminals.add(best.terminal_b)

            associations.append(
                LinkAssociation(
                    satellite_a=sat_a,
                    terminal_a=best.terminal_a,
                    satellite_b=sat_b,
                    terminal_b=best.terminal_b,
                    direction=direction,
                    link=None,
                    constraint_a_to_b=best.constraint_a_to_b,
                    constraint_b_to_a=best.constraint_b_to_a,
                )
            )

        return associations

    def get_link_associations(
        self, satellites: list[Satellite]
    ) -> list[LinkAssociation]:
        satellite_lookup = {sat.object_id: sat for sat in satellites}

        return self._build_associations_from_grid(satellite_lookup)

    @abstractmethod
    def get_type(self) -> str:
        raise NotImplementedError()


class SSODawnDuskStaticAddressingPlan(StaticAddressingPlan):
    """
    Static addressing plan for a Dawn-Dusk Sun-Synchronous orbit constellation.
    SSO constellations have only a single orbital plane, so only intra-plane
    (ORBITAL) links exist — there are no adjacent-plane links.
    The grid is a simple ring: each satellite connects to the next in the orbit.


    This type of shell uses the same logic has WalkerShell but only with orbital links. There is no adjacent planes.
    Right now, no adjacent intra-shell exists. Intershell could exist, but they can only be managed with the strategy,
    not with a static plan.
    We might add the adjacent plane in the future, but this is not our priority.

    """

    name = "LINKED_SSO"

    def get_type(self) -> str:
        return self.name

    def __init__(self, sso_shell: DawnDuskSSOShell):
        self.sso_shell = sso_shell

        self.grid: list[tuple[int, int, InterSatelliteLinkDirection]] = (
            generate_sun_synchronous_constellation_grid(
                number_satellites_per_orbit=sso_shell.amount_of_satellite,
            )
        )

    def _build_associations_from_grid(
        self,
        satellite_lookup: dict[int, Satellite],
    ) -> list[LinkAssociation]:
        associations: list[LinkAssociation] = []
        booked_terminals: set[OpticalLinkTerminal] = set()

        for a_id, b_id, direction in self.grid:
            sat_a = satellite_lookup.get(a_id)
            sat_b = satellite_lookup.get(b_id)

            if sat_a is None or sat_b is None:
                warnings.warn(
                    f"Satellite id {a_id if sat_a is None else b_id} not found "
                    f"in satellite list — skipping link ({a_id}, {b_id})."
                )
                continue

            if direction != InterSatelliteLinkDirection.ORBITAL:
                raise NotImplementedError(
                    f"{direction} direction links are not implemented yet."
                )

            sources_forward, destinations_backward = (
                _filter_terminals_pool_by_orientation(
                    sat_a.optical_link_terminals,
                    sat_b.optical_link_terminals,
                    {InterSatelliteLinkOrientation.INTRA_PLANE_FORWARD},
                    {InterSatelliteLinkOrientation.INTRA_PLANE_BACKWARD},
                )
            )
            sources_backward, destinations_forward = (
                _filter_terminals_pool_by_orientation(
                    sat_a.optical_link_terminals,
                    sat_b.optical_link_terminals,
                    {InterSatelliteLinkOrientation.INTRA_PLANE_BACKWARD},
                    {InterSatelliteLinkOrientation.INTRA_PLANE_FORWARD},
                )
            )

            candidates_case_1 = compute_OISL_links_from_terminal_pools(
                terminals_group_1=sources_forward,
                terminals_group_2=destinations_backward,
                angular_velocity_dt_seconds=1.0,
            )
            candidates_case_2 = compute_OISL_links_from_terminal_pools(
                terminals_group_1=sources_backward,
                terminals_group_2=destinations_forward,
                angular_velocity_dt_seconds=1.0,
            )

            all_candidates: list[PossibleOpticalLink] = (
                candidates_case_1 + candidates_case_2
            )
            all_candidates.sort(key=lambda x: x.selection_score)

            if not all_candidates:
                warnings.warn(
                    f"No valid {direction.name} terminal pair found between "
                    f"{sat_a.satellite_name} and {sat_b.satellite_name} — skipping."
                )
                continue

            # The best candidate is the one with the best score. But in some case where the satellite are
            # approaching the descending / ascending transition, the LEFT and right has no sense. There is a time step t
            # where the satellite from the adjacent orbit that was at right has a better angle to the left. but the left
            # is already booked before by the other adjacent sat that is still on the left ! So we have to iterate
            # if not will  have two satellites that will try to tke the same terminal

            candidate_selected_rank = 0

            best = all_candidates[candidate_selected_rank]

            while (
                best.terminal_a in booked_terminals
                or best.terminal_b in booked_terminals
            ):
                warnings.warn(
                    "Special situation where the satellite alignment is ambiguous"
                )
                candidate_selected_rank += 1
                if candidate_selected_rank > len(all_candidates) - 1:
                    warnings.warn(
                        f"No available terminal found for the {direction} link between {a_id} and {b_id}."
                    )
                    best = None
                    break

                best = all_candidates[candidate_selected_rank]

            if best is None:
                warnings.warn("No link will be created as no terminal are available.")
                continue

            booked_terminals.add(best.terminal_a)
            booked_terminals.add(best.terminal_b)

            associations.append(
                LinkAssociation(
                    satellite_a=sat_a,
                    terminal_a=best.terminal_a,
                    satellite_b=sat_b,
                    terminal_b=best.terminal_b,
                    direction=direction,
                    link=None,
                    constraint_a_to_b=best.constraint_a_to_b,
                    constraint_b_to_a=best.constraint_b_to_a,
                )
            )

        return associations

    def get_link_associations(
        self, satellites: list[Satellite]
    ) -> list[LinkAssociation]:
        satellite_lookup = {sat.object_id: sat for sat in satellites}

        return self._build_associations_from_grid(satellite_lookup)


class FullMeshWalkerStarStaticAddressingPlan(WalkerStaticAddressingPlan):
    name = "FULL_MESH_WALKER_STAR"

    def get_type(self) -> str:
        return self.name

    def __init__(self, walker_shell: WalkerShell):
        super().__init__(walker_shell)

        self.grid = generate_walker_star_constellation_grid(
            number_orbits=self.walker_shell.amount_of_orbit_plane,
            number_satellites_per_orbit=self.walker_shell.amount_of_satellite_per_orbit_plane,
            isl_shift=self.walker_shell.adjacent_inter_satellite_shifting,
        )


class FullMeshWalkerDeltaStaticAddressingPlan(WalkerStaticAddressingPlan):
    name = "FULL_MESH_WALKER_DELTA"

    def get_type(self) -> str:
        return self.name

    def __init__(self, walker_shell: WalkerShell):
        super().__init__(walker_shell)

        self.grid = generate_walker_delta_constellation_grid(
            number_orbits=self.walker_shell.amount_of_orbit_plane,
            number_satellites_per_orbit=self.walker_shell.amount_of_satellite_per_orbit_plane,
            isl_shift=self.walker_shell.adjacent_inter_satellite_shifting,
        )


class CheckerboardWalkerStarStaticAddressingPlan(WalkerStaticAddressingPlan):
    name = "CHECKERBOARD_WALKER_STAR"

    def get_type(self) -> str:
        return self.name

    def __init__(self, walker_shell: WalkerShell):
        super().__init__(walker_shell)

        self.grid = generate_checkerboard_walker_star_constellation_grid(
            number_orbits=self.walker_shell.amount_of_orbit_plane,
            number_satellites_per_orbit=self.walker_shell.amount_of_satellite_per_orbit_plane,
            isl_shift=self.walker_shell.adjacent_inter_satellite_shifting,
        )


class CheckerboardWalkerDeltaStaticAddressingPlan(WalkerStaticAddressingPlan):
    name = "CHECKERBOARD_WALKER_DELTA"

    def get_type(self) -> str:
        return self.name

    def _check_compatibility(self):
        problems: list[str] = []
        n_orbits = self.walker_shell.amount_of_orbit_plane
        n_satellites = self.walker_shell.amount_of_satellite_per_orbit_plane
        if n_orbits % 2 != 0 or n_satellites % 2 != 0:
            problems.append(
                "Checkerboard addressing requires both number of orbits "
                "and satellites per orbit to be even."
            )
        if math.gcd(n_orbits, n_satellites) < 2:
            problems.append(
                "Checkerboard addressing requires orbit and satellite counts "
                "to be commensurate (gcd >= 2) to avoid disconnected patterns."
            )

    def __init__(self, walker_shell: WalkerShell):
        super().__init__(walker_shell)

        self.grid = generate_checkerboard_walker_delta_constellation_grid(
            number_orbits=self.walker_shell.amount_of_orbit_plane,
            number_satellites_per_orbit=self.walker_shell.amount_of_satellite_per_orbit_plane,
            isl_shift=self.walker_shell.adjacent_inter_satellite_shifting,
        )


class AvailableAddressingPlans(str, Enum):
    CHECKERBOARD_WALKER_DELTA = CheckerboardWalkerDeltaStaticAddressingPlan.name
    CHECKERBOARD_WALKER_STAR = CheckerboardWalkerStarStaticAddressingPlan.name
    FULL_MESH_WALKER_DELTA = FullMeshWalkerDeltaStaticAddressingPlan.name
    FULL_MESH_WALKER_STAR = FullMeshWalkerStarStaticAddressingPlan.name
    LINKED_SSO = SSODawnDuskStaticAddressingPlan.name

    @classmethod
    def _mapping(cls):
        return {
            cls.CHECKERBOARD_WALKER_DELTA: CheckerboardWalkerDeltaStaticAddressingPlan,
            cls.CHECKERBOARD_WALKER_STAR: CheckerboardWalkerStarStaticAddressingPlan,
            cls.FULL_MESH_WALKER_DELTA: FullMeshWalkerDeltaStaticAddressingPlan,
            cls.FULL_MESH_WALKER_STAR: FullMeshWalkerStarStaticAddressingPlan,
            cls.LINKED_SSO: SSODawnDuskStaticAddressingPlan,
        }

    def get_class(self):
        return self._mapping()[self]

    def build(self, **kwargs) -> StaticAddressingPlan:
        self.validate_kwargs(**kwargs)
        return self.get_class()(**kwargs)

    def required_parameters(self) -> list[str]:
        sig = inspect.signature(self.get_class().__init__)
        return [
            name
            for name, param in sig.parameters.items()
            if name != "self" and param.default == inspect.Parameter.empty
        ]

    def validate_kwargs(self, **kwargs):
        required = self.required_parameters()
        missing = [p for p in required if p not in kwargs]

        if missing:
            raise ValueError(f"{self.value} missing required parameters: {missing}")

    def get_signature(self) -> str:
        return str(inspect.signature(self.get_class().__init__))

    @classmethod
    def from_string(cls, value: str):
        try:
            return cls(value)
        except ValueError:
            raise ValueError(
                f"Unknown addressing plan '{value}'. Available: {cls.list()}"
            )

    @classmethod
    def list(cls) -> list[str]:
        return [e.value for e in cls]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        return value in cls._value2member_map_

    # ---- Classification helpers ----
    def is_walker(self) -> bool:
        return "WALKER" in self.value

    def is_star(self) -> bool:
        return "STAR" in self.value

    def is_delta(self) -> bool:
        return "DELTA" in self.value

    def is_checkerboard(self) -> bool:
        return "CHECKERBOARD" in self.value

    def is_full_mesh(self) -> bool:
        return "FULL_MESH" in self.value
