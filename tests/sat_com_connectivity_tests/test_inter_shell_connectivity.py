import datetime
import math
import uuid
from unittest.mock import MagicMock, patch

from sat_com_connectivity.inter_satellite_link_connectivity.addressing_plans import (
    _is_inter_shell_capable,
    StaticAddressingPlan,
)
from sat_com_connectivity.inter_satellite_link_connectivity.models import (
    InterSatelliteConnectivityResult,
    LinkAssociation,
    OpticISLVisibilityConstraintResult,
    ConnectivityLedger,
)
from sat_com_connectivity.inter_satellite_link_connectivity.strategies import (
    InterShellSSOPriorityConnectivity,
)
from sat_com_model.models import (
    InterSatelliteLinkDirection,
    InterSatelliteLinkOrientation,
    WalkerShell,
    DawnDuskSSOShell,
    OpticalLinkTerminal,
    Satellite,
    InterSatelliteLink,
    Shell,
)

MODULE = "sat_com_connectivity.inter_satellite_link_connectivity.strategies"


# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------


def make_terminal(
    is_inter_shell: bool = False,
    link: InterSatelliteLink = None,
    peer_terminal: OpticalLinkTerminal = None,
    host_satellite: Satellite = None,
) -> OpticalLinkTerminal:
    terminal = MagicMock(spec=OpticalLinkTerminal)
    terminal.terminal_id = uuid.uuid4()
    terminal.link = link
    terminal.target_optical_link_terminal = peer_terminal
    terminal.host_satellite = host_satellite
    terminal.terminal_configuration = MagicMock()
    terminal.terminal_configuration.min_elevation_degrees = -25.0
    terminal.terminal_configuration.max_elevation_degrees = 5.0
    terminal.terminal_configuration.max_azimuth_degrees = 175.0
    terminal.terminal_configuration.maximum_range_distance_km = 7800.0
    terminal.terminal_configuration.maximum_angular_velocity_degree_per_second = 1.0
    terminal.terminal_configuration.minimum_contact_duration_seconds = 30
    terminal.azimuth_angle_configuration = 0.0
    terminal.elevation_angle_configuration = -180.0
    terminal.orientation_possibilities = (
        [InterSatelliteLinkOrientation.INTER_SHELL_LEFT]
        if is_inter_shell
        else [InterSatelliteLinkOrientation.INTRA_PLANE_FORWARD]
    )
    terminal.__hash__ = lambda self: hash(self.terminal_id)
    terminal.__eq__ = lambda self, other: (
        isinstance(other, type(self)) and self.terminal_id == other.terminal_id
    )
    return terminal


def make_walker_shell(identifier: str = "walker-a") -> WalkerShell:
    shell = MagicMock(spec=WalkerShell)
    shell.identifier = identifier
    return shell


def make_sso_shell(identifier: str = "sso-a") -> DawnDuskSSOShell:
    shell = MagicMock(spec=DawnDuskSSOShell)
    shell.identifier = identifier
    return shell


def make_satellite(
    topology_id: int,
    shell,
    terminals: list[OpticalLinkTerminal] = None,
    object_id: int = None,
    local_date: datetime.datetime | None = None,
) -> Satellite:
    sat = MagicMock(spec=Satellite)
    sat.topology_uniq_id = topology_id
    sat.object_id = object_id if object_id is not None else topology_id
    sat.shell = shell
    sat.optical_link_terminals = terminals or []
    sat.get_movement_model().get_datetime.return_value = local_date
    for t in sat.optical_link_terminals:
        t.host_satellite = sat
        t.terminal_configuration.minimum_contact_duration_seconds = 30
    return sat


def make_isl(
    source: Satellite,
    destination: Satellite,
    source_terminal: OpticalLinkTerminal = None,
    dest_terminal: OpticalLinkTerminal = None,
    direction: InterSatelliteLinkDirection = InterSatelliteLinkDirection.ORBITAL,
    temporary_unavailable: bool = False,
    recovery_time: datetime.datetime | None = None,
) -> InterSatelliteLink:
    link = MagicMock(spec=InterSatelliteLink)
    link.link_id = uuid.uuid4()
    link.source = source
    link.destination = destination
    link.source_optical_terminal = source_terminal
    link.destination_optical_terminal = dest_terminal
    link.inter_satellite_direction = direction
    link.temporary_unavailable = temporary_unavailable
    link.recovery_time = recovery_time
    link.__hash__ = lambda self: hash(self.link_id)
    link.__eq__ = lambda self, other: (
        isinstance(other, type(self)) and self.link_id == other.link_id
    )

    def get_terminal_for_satellite(sat):
        if sat == source:
            return source_terminal
        if sat == destination:
            return dest_terminal
        raise ValueError("Satellite not in link")

    def get_peer_satellite(sat):
        if sat == source:
            return destination
        if sat == destination:
            return source
        raise ValueError("Satellite not in link")

    def get_peer_terminal(terminal):
        if terminal == source_terminal:
            return dest_terminal
        if terminal == dest_terminal:
            return source_terminal
        raise ValueError("Terminal not in link")

    link.get_terminal_for_satellite.side_effect = get_terminal_for_satellite
    link.get_peer_satellite.side_effect = get_peer_satellite
    link.get_peer_terminal.side_effect = get_peer_terminal
    return link


def make_constraint() -> OpticISLVisibilityConstraintResult:
    return OpticISLVisibilityConstraintResult(
        elevation_angle_degree=10.0,
        azimuth_angle_degree=0.0,
        range_distance_km=500.0,
        angular_velocity_rate_degree_per_second=0.1,
        flag_elevation=True,
        flag_azimuth=True,
        flag_range=True,
        flag_angular_velocity=True,
        flag_overall=True,
        flag_bidirectional=True,
        range_rate=5,
        los_min_altitude_km=5000,
        los_clear=True,
    )


def make_possible_link(
    terminal_a: OpticalLinkTerminal,
    terminal_b: OpticalLinkTerminal,
    score: float = 0.0,
    temporary_unavailable: bool = None,
    estimated_recover_time: float = math.inf,
) -> MagicMock:
    possible = MagicMock()
    possible.terminal_a = terminal_a
    possible.terminal_b = terminal_b
    possible.selection_score = score
    possible.bidirectional_possible = True
    possible.constraint_a_to_b = make_constraint()
    possible.constraint_b_to_a = make_constraint()
    possible.temporary_unavailable = temporary_unavailable
    possible.estimated_recover_time = estimated_recover_time
    return possible


def make_mock_plan(associations: list[LinkAssociation] = None) -> StaticAddressingPlan:
    plan = MagicMock(spec=StaticAddressingPlan)
    plan.get_link_associations.return_value = associations or []
    return plan


def make_strategy(
    satellites: list[Satellite],
    shell_and_plans: list[tuple[Shell, StaticAddressingPlan]] = None,
) -> InterShellSSOPriorityConnectivity:
    return InterShellSSOPriorityConnectivity(
        satellites=satellites,
        shell_and_plans=shell_and_plans or [],
    )


def run_inter_shell(strategy) -> ConnectivityLedger:
    """Run phase 1 and return the populated ledger."""
    ledger = ConnectivityLedger()
    strategy._compute_inter_shell_associations(ledger)
    return ledger


def run_intra_shell(strategy, ledger: ConnectivityLedger = None) -> ConnectivityLedger:
    """Run phase 2 on an existing or fresh ledger and return it."""
    if ledger is None:
        ledger = ConnectivityLedger()
    strategy._compute_intra_shell_associations(ledger)
    return ledger


# ---------------------------------------------------------------------------
# _is_inter_shell_capable
# ---------------------------------------------------------------------------


class TestIsInterShellCapable:

    def test_returns_true_when_inter_shell_orientation_present(self):
        assert _is_inter_shell_capable(make_terminal(is_inter_shell=True)) is True

    def test_returns_false_when_only_intra_plane_orientation(self):
        assert _is_inter_shell_capable(make_terminal(is_inter_shell=False)) is False

    def test_returns_true_when_one_of_several_is_inter_shell(self):
        terminal = make_terminal()
        terminal.orientation_possibilities = [
            InterSatelliteLinkOrientation.INTRA_PLANE_FORWARD,
            InterSatelliteLinkOrientation.INTER_SHELL_RIGHT,
        ]
        assert _is_inter_shell_capable(terminal) is True

    def test_returns_false_for_empty_orientation_list(self):
        terminal = make_terminal()
        terminal.orientation_possibilities = []
        assert _is_inter_shell_capable(terminal) is False


# ---------------------------------------------------------------------------
# Phase 1 — _compute_inter_shell_associations
# ---------------------------------------------------------------------------


class TestComputeInterShellAssociationsNoExistingLinks:

    def test_empty_ledger_when_no_satellites(self):
        strategy = make_strategy(satellites=[])
        ledger = run_inter_shell(strategy)
        result = ledger.to_result()
        assert result.new_links == []
        assert result.obsolete_links == []
        assert result.updated_links == []

    def test_non_inter_shell_terminals_are_ignored(self):
        shell = make_walker_shell()
        terminal = make_terminal(is_inter_shell=False)
        sat = make_satellite(1, shell, [terminal])

        strategy = make_strategy([sat])
        ledger = run_inter_shell(strategy)
        result = ledger.to_result()

        assert result.new_links == []
        assert not ledger.is_terminal_booked(terminal)

    def test_unlinked_inter_shell_terminal_produces_new_link(self):
        sso_shell = make_sso_shell()
        walker_shell = make_walker_shell()
        t_sso = make_terminal(is_inter_shell=True)
        t_walker = make_terminal(is_inter_shell=True)
        sat_sso = make_satellite(1, sso_shell, [t_sso])
        sat_walker = make_satellite(2, walker_shell, [t_walker])
        possible = make_possible_link(t_sso, t_walker, score=5.0)

        with patch(
            f"{MODULE}.compute_OISL_links_from_terminal_pools_filtered",
            return_value=[possible],
        ):
            strategy = make_strategy([sat_sso, sat_walker])
            ledger = run_inter_shell(strategy)

        result = ledger.to_result()
        assert len(result.new_links) == 1
        assert result.new_links[0].terminal_a == t_sso
        assert result.new_links[0].terminal_b == t_walker
        assert result.new_links[0].link is None
        assert ledger.is_terminal_booked(t_sso)
        assert ledger.is_terminal_booked(t_walker)

    def test_new_link_direction_is_inter_shell(self):
        sso_shell = make_sso_shell()
        walker_shell = make_walker_shell()
        t_sso = make_terminal(is_inter_shell=True)
        t_walker = make_terminal(is_inter_shell=True)
        sat_sso = make_satellite(1, sso_shell, [t_sso])
        sat_walker = make_satellite(2, walker_shell, [t_walker])
        possible = make_possible_link(t_sso, t_walker)

        with patch(
            f"{MODULE}.compute_OISL_links_from_terminal_pools_filtered",
            return_value=[possible],
        ):
            strategy = make_strategy([sat_sso, sat_walker])
            ledger = run_inter_shell(strategy)

        assert (
            ledger.to_result().new_links[0].direction
            == InterSatelliteLinkDirection.INTER_SHELL
        )


class TestComputeInterShellAssociationsExistingInterShellLinks:

    def test_still_feasible_inter_shell_link_goes_to_updated(self):
        sso_shell = make_sso_shell()
        walker_shell = make_walker_shell()
        t_sso = make_terminal(is_inter_shell=True)
        t_walker = make_terminal(is_inter_shell=True)
        t_walker.host_satellite = make_satellite(2, walker_shell)

        link = make_isl(
            make_satellite(1, sso_shell), t_walker.host_satellite, t_sso, t_walker
        )
        t_sso.link = link
        t_sso.target_optical_link_terminal = t_walker

        sat_sso = make_satellite(1, sso_shell, [t_sso])
        t_sso.host_satellite = sat_sso

        feasible = make_possible_link(t_sso, t_walker)

        with patch(
            f"{MODULE}.compute_OISL_feasibility_for_terminal_pair",
            return_value=feasible,
        ), patch(
            f"{MODULE}.compute_OISL_links_from_terminal_pools_filtered", return_value=[]
        ):
            strategy = make_strategy([sat_sso])
            ledger = run_inter_shell(strategy)

        result = ledger.to_result()
        assert len(result.updated_links) == 1
        assert result.updated_links[0].link == link
        assert ledger.is_terminal_booked(t_sso)
        assert ledger.is_terminal_booked(t_walker)
        assert len(result.new_links) == 0

    def test_infeasible_inter_shell_link_goes_to_obsolete(self):
        sso_shell = make_sso_shell()
        walker_shell = make_walker_shell()
        t_sso = make_terminal(is_inter_shell=True)
        t_walker = make_terminal(is_inter_shell=True)
        t_walker.host_satellite = make_satellite(2, walker_shell)

        link = make_isl(
            make_satellite(1, sso_shell), t_walker.host_satellite, t_sso, t_walker
        )
        t_sso.link = link
        t_sso.target_optical_link_terminal = t_walker

        sat_sso = make_satellite(1, sso_shell, [t_sso])
        t_sso.host_satellite = sat_sso

        not_feasible_impossible_to_recover = make_possible_link(
            t_sso, t_walker, temporary_unavailable=True, estimated_recover_time=6000
        )

        with patch(
            f"{MODULE}.compute_OISL_feasibility_for_terminal_pair",
            return_value=not_feasible_impossible_to_recover,
        ), patch(
            f"{MODULE}.compute_OISL_links_from_terminal_pools_filtered", return_value=[]
        ):
            strategy = make_strategy([sat_sso])
            ledger = run_inter_shell(strategy)

        result = ledger.to_result()
        assert len(result.obsolete_links) == 1
        assert result.obsolete_links[0].link == link
        assert len(result.updated_links) == 0
        assert not ledger.is_terminal_booked(t_sso)

    def test_infeasible_but_maintainable_inter_shell_link_goes_to_updated(self):
        sso_shell = make_sso_shell()
        walker_shell = make_walker_shell()
        t_sso = make_terminal(is_inter_shell=True)
        t_walker = make_terminal(is_inter_shell=True)
        t_walker.host_satellite = make_satellite(
            2, walker_shell, local_date=datetime.datetime(2018, 1, 1)
        )

        link = make_isl(
            make_satellite(1, sso_shell), t_walker.host_satellite, t_sso, t_walker
        )
        t_sso.link = link
        t_sso.target_optical_link_terminal = t_walker

        sat_sso = make_satellite(
            1, sso_shell, [t_sso], local_date=datetime.datetime(2018, 1, 1)
        )
        t_sso.host_satellite = sat_sso

        not_feasible_possible_to_recover = make_possible_link(
            t_sso, t_walker, temporary_unavailable=True, estimated_recover_time=29
        )

        with patch(
            f"{MODULE}.compute_OISL_feasibility_for_terminal_pair",
            return_value=not_feasible_possible_to_recover,
        ), patch(
            f"{MODULE}.compute_OISL_links_from_terminal_pools_filtered", return_value=[]
        ):
            strategy = make_strategy([sat_sso])
            ledger = run_inter_shell(strategy)

        result = ledger.to_result()
        assert len(result.updated_links) == 1
        assert result.updated_links[0].link == link
        assert result.updated_links[0].temporary_unavailable == True
        assert result.updated_links[0].recovery_time == datetime.datetime(
            2018, 1, 1
        ) + datetime.timedelta(seconds=29)
        assert len(result.obsolete_links) == 0
        assert ledger.is_terminal_booked(t_sso)
        assert ledger.is_terminal_booked(t_walker)

    def test_infeasible_but_maintainable_but_maintainability_promise_broken_inter_shell_link_goes_to_obsolete(
        self,
    ):
        sso_shell = make_sso_shell()
        walker_shell = make_walker_shell()
        t_sso = make_terminal(is_inter_shell=True)
        t_walker = make_terminal(is_inter_shell=True)
        t_walker.host_satellite = make_satellite(
            2, walker_shell, local_date=datetime.datetime(2018, 1, 1)
        )

        link = make_isl(
            make_satellite(1, sso_shell),
            t_walker.host_satellite,
            t_sso,
            t_walker,
            temporary_unavailable=True,
            recovery_time=datetime.datetime(
                2017, 2, 1
            ),  # A recovery time promised long time ago
        )
        t_sso.link = link
        t_sso.target_optical_link_terminal = t_walker

        sat_sso = make_satellite(
            1, sso_shell, [t_sso], local_date=datetime.datetime(2018, 1, 1)
        )
        t_sso.host_satellite = sat_sso

        not_feasible_possible_to_recover_but_long_time_ago = make_possible_link(
            t_sso, t_walker, temporary_unavailable=True, estimated_recover_time=29
        )

        with patch(
            f"{MODULE}.compute_OISL_feasibility_for_terminal_pair",
            return_value=not_feasible_possible_to_recover_but_long_time_ago,
        ), patch(
            f"{MODULE}.compute_OISL_links_from_terminal_pools_filtered", return_value=[]
        ):
            strategy = make_strategy([sat_sso])
            ledger = run_inter_shell(strategy)

        result = ledger.to_result()
        assert len(result.updated_links) == 0
        assert result.obsolete_links[0].link == link

        assert len(result.obsolete_links) == 1
        assert not ledger.is_terminal_booked(t_sso)
        assert not ledger.is_terminal_booked(t_walker)


class TestComputeInterShellAssociationsDisplacedIntraShellLinks:

    def test_intra_shell_link_is_displaced_when_terminal_selected_for_inter_shell(self):
        sso_shell = make_sso_shell()
        walker_shell_b = make_walker_shell("walker-b")

        t_sso = make_terminal(is_inter_shell=True)
        t_peer_intra = make_terminal(is_inter_shell=False)

        sat_sso_peer = make_satellite(99, sso_shell, [t_peer_intra])
        t_peer_intra.host_satellite = sat_sso_peer

        intra_link = make_isl(
            make_satellite(1, sso_shell),
            sat_sso_peer,
            t_sso,
            t_peer_intra,
            direction=InterSatelliteLinkDirection.ORBITAL,
        )
        t_sso.link = intra_link
        t_sso.target_optical_link_terminal = t_peer_intra
        t_peer_intra.link = intra_link
        t_peer_intra.target_optical_link_terminal = t_sso

        sat_sso = make_satellite(1, sso_shell, [t_sso])
        t_sso.host_satellite = sat_sso

        t_walker = make_terminal(is_inter_shell=True)
        sat_walker = make_satellite(2, walker_shell_b, [t_walker])
        t_walker.host_satellite = sat_walker

        possible = make_possible_link(t_sso, t_walker)

        with patch(
            f"{MODULE}.compute_OISL_links_from_terminal_pools_filtered",
            return_value=[possible],
        ):
            strategy = make_strategy([sat_sso, sat_walker])
            ledger = run_inter_shell(strategy)

        result = ledger.to_result()
        displaced = [o for o in result.obsolete_links if o.link == intra_link]
        assert len(displaced) == 1
        assert displaced[0].terminal_a == t_sso
        assert len(result.new_links) == 1

    def test_displaced_link_not_double_obsoleted(self):
        """
        If both terminals of a displaced intra-shell link are inter-shell capable,
        the link must appear in obsolete_links exactly once — not twice.
        """
        sso_shell = make_sso_shell()
        walker_shell_b = make_walker_shell("walker-b")

        t_sso = make_terminal(is_inter_shell=True)
        t_peer = make_terminal(is_inter_shell=True)  # also inter-shell capable

        sat_peer = make_satellite(99, sso_shell, [t_peer])
        t_peer.host_satellite = sat_peer

        intra_link = make_isl(
            make_satellite(1, sso_shell),
            sat_peer,
            t_sso,
            t_peer,
            direction=InterSatelliteLinkDirection.ORBITAL,
        )
        t_sso.link = intra_link
        t_sso.target_optical_link_terminal = t_peer
        t_peer.link = intra_link
        t_peer.target_optical_link_terminal = t_sso

        sat_sso = make_satellite(1, sso_shell, [t_sso])
        t_sso.host_satellite = sat_sso

        t_walker = make_terminal(is_inter_shell=True)
        sat_walker = make_satellite(2, walker_shell_b, [t_walker])
        t_walker.host_satellite = sat_walker

        possible = make_possible_link(t_sso, t_walker)

        with patch(
            f"{MODULE}.compute_OISL_links_from_terminal_pools_filtered",
            return_value=[possible],
        ):
            strategy = make_strategy([sat_sso, sat_peer, sat_walker])
            ledger = run_inter_shell(strategy)

        result = ledger.to_result()
        displaced = [o for o in result.obsolete_links if o.link == intra_link]
        assert len(displaced) == 1


# ---------------------------------------------------------------------------
# Phase 2 — _compute_intra_shell_associations
# ---------------------------------------------------------------------------


class TestComputeIntraShellAssociationsNoExistingLinks:

    def test_all_new_when_no_existing_links(self):
        walker_shell = make_walker_shell()
        t_a, t_b = make_terminal(), make_terminal()
        sat_a = make_satellite(1, walker_shell, [t_a])
        sat_b = make_satellite(2, walker_shell, [t_b])

        intended = [
            LinkAssociation(
                satellite_a=sat_a,
                terminal_a=t_a,
                satellite_b=sat_b,
                terminal_b=t_b,
                direction=InterSatelliteLinkDirection.ORBITAL,
                link=None,
            )
        ]
        plan = make_mock_plan(intended)
        strategy = make_strategy([sat_a, sat_b], [(walker_shell, plan)])
        ledger = run_intra_shell(strategy)
        result = ledger.to_result()

        assert len(result.new_links) == 1
        assert result.new_links[0].satellite_a == sat_a
        assert result.new_links[0].link is None
        assert result.obsolete_links == [] and result.updated_links == []

    def test_terminal_a_booked_in_ledger_skips_association(self):
        walker_shell = make_walker_shell()
        t_a, t_b = make_terminal(), make_terminal()
        sat_a = make_satellite(1, walker_shell, [t_a])
        sat_b = make_satellite(2, walker_shell, [t_b])

        intended = [
            LinkAssociation(
                satellite_a=sat_a,
                terminal_a=t_a,
                satellite_b=sat_b,
                terminal_b=t_b,
                direction=InterSatelliteLinkDirection.ORBITAL,
                link=None,
            )
        ]
        plan = make_mock_plan(intended)
        strategy = make_strategy([sat_a, sat_b], [(walker_shell, plan)])

        # Pre-book t_a in the ledger (simulates phase 1 claiming it)
        ledger = ConnectivityLedger()
        ledger.add_new(
            LinkAssociation(
                satellite_a=sat_a,
                terminal_a=t_a,
                satellite_b=sat_b,
                terminal_b=t_b,
                direction=InterSatelliteLinkDirection.INTER_SHELL,
                link=None,
            )
        )
        run_intra_shell(strategy, ledger)
        result = ledger.to_result()

        # Only the inter-shell new link — intra was skipped
        assert len(result.new_links) == 1
        assert result.new_links[0].direction == InterSatelliteLinkDirection.INTER_SHELL

    def test_terminal_b_booked_in_ledger_also_skipped(self):
        walker_shell = make_walker_shell()
        t_a, t_b = make_terminal(), make_terminal()
        sat_a = make_satellite(1, walker_shell, [t_a])
        sat_b = make_satellite(2, walker_shell, [t_b])

        intended = [
            LinkAssociation(
                satellite_a=sat_a,
                terminal_a=t_a,
                satellite_b=sat_b,
                terminal_b=t_b,
                direction=InterSatelliteLinkDirection.ORBITAL,
                link=None,
            )
        ]
        plan = make_mock_plan(intended)
        strategy = make_strategy([sat_a, sat_b], [(walker_shell, plan)])

        ledger = ConnectivityLedger()
        ledger.add_new(
            LinkAssociation(
                satellite_a=sat_a,
                terminal_a=t_b,
                satellite_b=sat_b,
                terminal_b=t_a,
                direction=InterSatelliteLinkDirection.INTER_SHELL,
                link=None,
            )
        )
        run_intra_shell(strategy, ledger)
        result = ledger.to_result()

        intra_new = [
            l
            for l in result.new_links
            if l.direction == InterSatelliteLinkDirection.ORBITAL
        ]
        assert intra_new == []

    def test_plan_called_with_shell_satellites(self):
        walker_shell = make_walker_shell()
        t_a = make_terminal()
        sat_a = make_satellite(1, walker_shell, [t_a])

        plan = make_mock_plan([])
        strategy = make_strategy([sat_a], [(walker_shell, plan)])
        run_intra_shell(strategy)

        plan.get_link_associations.assert_called_once_with([sat_a])


class TestComputeIntraShellAssociationsExistingLinks:

    def _setup(self):
        walker_shell = make_walker_shell()
        t_a, t_b = make_terminal(), make_terminal()
        sat_a = make_satellite(1, walker_shell, [t_a])
        sat_b = make_satellite(2, walker_shell, [t_b])
        t_a.host_satellite = sat_a
        t_b.host_satellite = sat_b
        link = make_isl(sat_a, sat_b, t_a, t_b, InterSatelliteLinkDirection.ORBITAL)
        t_a.link = link
        t_b.link = link
        return walker_shell, sat_a, sat_b, t_a, t_b, link

    def test_matching_existing_link_goes_to_updated(self):
        walker_shell, sat_a, sat_b, t_a, t_b, link = self._setup()

        intended = [
            LinkAssociation(
                satellite_a=sat_a,
                terminal_a=t_a,
                satellite_b=sat_b,
                terminal_b=t_b,
                direction=InterSatelliteLinkDirection.ORBITAL,
                link=None,
            )
        ]
        plan = make_mock_plan(intended)
        strategy = make_strategy([sat_a, sat_b], [(walker_shell, plan)])
        ledger = run_intra_shell(strategy)
        result = ledger.to_result()

        assert len(result.updated_links) == 1
        assert result.updated_links[0].link == link
        assert result.new_links == [] and result.obsolete_links == []

    def test_terminal_reassignment_produces_obsolete_and_new(self):
        walker_shell, sat_a, sat_b, t_a_old, t_b_old, link = self._setup()

        t_a_new, t_b_new = make_terminal(), make_terminal()
        t_a_new.host_satellite = sat_a
        t_b_new.host_satellite = sat_b

        intended = [
            LinkAssociation(
                satellite_a=sat_a,
                terminal_a=t_a_new,
                satellite_b=sat_b,
                terminal_b=t_b_new,
                direction=InterSatelliteLinkDirection.ORBITAL,
                link=None,
            )
        ]
        plan = make_mock_plan(intended)
        strategy = make_strategy([sat_a, sat_b], [(walker_shell, plan)])
        ledger = run_intra_shell(strategy)
        result = ledger.to_result()

        assert len(result.obsolete_links) == 1
        assert result.obsolete_links[0].link == link
        assert len(result.new_links) == 1
        assert result.new_links[0].terminal_a == t_a_new
        assert result.new_links[0].link is None

    def test_dangling_link_not_in_plan_goes_to_obsolete(self):
        walker_shell, sat_a, sat_b, t_a, t_b, link = self._setup()

        plan = make_mock_plan([])
        strategy = make_strategy([sat_a, sat_b], [(walker_shell, plan)])
        ledger = run_intra_shell(strategy)
        result = ledger.to_result()

        assert any(o.link == link for o in result.obsolete_links)

    def test_dangling_inter_shell_link_is_emitted(self):
        sso_shell = make_sso_shell()
        walker_shell = make_walker_shell()

        t_sso = make_terminal(is_inter_shell=True)
        t_walker = make_terminal(is_inter_shell=True)

        sat_sso = make_satellite(1, sso_shell, [t_sso])
        sat_walker = make_satellite(2, walker_shell, [t_walker])

        t_sso.host_satellite = sat_sso
        t_walker.host_satellite = sat_walker

        inter_link = make_isl(sat_sso, sat_walker, t_sso, t_walker)

        # Only attach the link to ONE side → dangling
        t_sso.link = inter_link
        t_walker.link = None  # or simply don't assign it

        plan = make_mock_plan([])
        strategy = make_strategy([sat_sso, sat_walker], [(walker_shell, plan)])

        ledger = run_intra_shell(strategy)
        result = ledger.to_result()

        assert any(d.link == inter_link for d in result.obsolete_links)

    def test_link_already_accounted_in_ledger_is_not_double_obsoleted(self):
        """
        If phase 1 already obsoleted a link, phase 2 must not obsolete it again.
        This is the core regression test for the double-remove bug.
        """
        walker_shell, sat_a, sat_b, t_a, t_b, link = self._setup()

        plan = make_mock_plan([])
        strategy = make_strategy([sat_a, sat_b], [(walker_shell, plan)])

        # Simulate phase 1 having already obsoleted this link
        ledger = ConnectivityLedger()
        ledger.add_obsolete(
            LinkAssociation(
                satellite_a=sat_a,
                terminal_a=t_a,
                satellite_b=sat_b,
                terminal_b=t_b,
                direction=InterSatelliteLinkDirection.ORBITAL,
                link=link,
                constraint_a_to_b=None,
                constraint_b_to_a=None,
            )
        )

        run_intra_shell(strategy, ledger)
        result = ledger.to_result()

        obsolete_for_link = [o for o in result.obsolete_links if o.link == link]
        assert len(obsolete_for_link) == 1  # exactly once, not twice

    def test_dangling_link_whose_terminals_are_not_booked_is_emitted(self):
        walker_shell, sat_a, sat_b, t_a, t_b, link = self._setup()

        plan = make_mock_plan([])
        strategy = make_strategy([sat_a, sat_b], [(walker_shell, plan)])

        # No pre-booking in ledger → this is the key difference
        ledger = ConnectivityLedger()

        run_intra_shell(strategy, ledger)
        result = ledger.to_result()

        dangling_links = [d for d in result.obsolete_links if d.link == link]
        assert dangling_links != []

    def test_multiple_shells_all_plans_are_called(self):
        shell_a = make_walker_shell("shell-a")
        shell_b = make_walker_shell("shell-b")
        sat_a = make_satellite(1, shell_a)
        sat_b = make_satellite(2, shell_b)

        plan_a = make_mock_plan([])
        plan_b = make_mock_plan([])
        strategy = make_strategy([sat_a, sat_b], [(shell_a, plan_a), (shell_b, plan_b)])
        run_intra_shell(strategy)

        plan_a.get_link_associations.assert_called_once()
        plan_b.get_link_associations.assert_called_once()


# ---------------------------------------------------------------------------
# compute_strategy — full integration
# ---------------------------------------------------------------------------


class TestComputeStrategy:

    def test_returns_inter_satellite_connectivity_result(self):
        result = make_strategy([]).compute_strategy()
        assert isinstance(result, InterSatelliteConnectivityResult)

    def test_empty_simulation_returns_empty_result(self):
        result = make_strategy([]).compute_strategy()
        assert (
            result.new_links == []
            and result.obsolete_links == []
            and result.updated_links == []
        )

    def test_phases_share_the_same_ledger(self):
        """
        Phase 1 books terminals → phase 2 must see them as booked.
        Verified by having phase 1 book a terminal that phase 2 would otherwise use.
        """
        walker_shell = make_walker_shell()
        sso_shell = make_sso_shell()
        t_shared = make_terminal(is_inter_shell=True)
        t_walker_intra = make_terminal(is_inter_shell=False)

        sat_sso = make_satellite(1, sso_shell, [t_shared])
        sat_walker = make_satellite(2, walker_shell, [t_shared, t_walker_intra])

        # Phase 2 plan tries to use t_shared — must be skipped
        intended = [
            LinkAssociation(
                satellite_a=sat_sso,
                terminal_a=t_shared,
                satellite_b=sat_walker,
                terminal_b=t_walker_intra,
                direction=InterSatelliteLinkDirection.ORBITAL,
                link=None,
            )
        ]
        plan = make_mock_plan(intended)

        possible = make_possible_link(t_shared, t_walker_intra)

        with patch(
            f"{MODULE}.compute_OISL_links_from_terminal_pools_filtered",
            return_value=[possible],
        ):
            strategy = make_strategy([sat_sso, sat_walker], [(walker_shell, plan)])
            result = strategy.compute_strategy()

        # t_shared booked by phase 1 → phase 2 association skipped → only 1 new link
        inter_shell_new = [
            l
            for l in result.new_links
            if l.direction == InterSatelliteLinkDirection.INTER_SHELL
        ]
        intra_new = [
            l
            for l in result.new_links
            if l.direction == InterSatelliteLinkDirection.ORBITAL
        ]
        assert len(inter_shell_new) == 1
        assert intra_new == []

    def test_same_link_not_double_obsoleted_across_phases(self):
        """
        The core regression: a link displaced by phase 1 must not also appear
        in phase 2 obsolete_links. Ledger.add_obsolete is idempotent.
        """
        sso_shell = make_sso_shell()
        walker_shell = make_walker_shell()

        t_sso = make_terminal(is_inter_shell=True)
        t_peer_intra = make_terminal(is_inter_shell=False)
        sat_peer = make_satellite(99, sso_shell, [t_peer_intra])
        t_peer_intra.host_satellite = sat_peer

        intra_link = make_isl(
            make_satellite(1, sso_shell),
            sat_peer,
            t_sso,
            t_peer_intra,
            direction=InterSatelliteLinkDirection.ORBITAL,
        )
        t_sso.link = intra_link
        t_sso.target_optical_link_terminal = t_peer_intra
        t_peer_intra.link = intra_link
        t_peer_intra.target_optical_link_terminal = t_sso

        sat_sso = make_satellite(1, sso_shell, [t_sso])
        t_sso.host_satellite = sat_sso

        t_walker = make_terminal(is_inter_shell=True)
        sat_walker = make_satellite(2, walker_shell, [t_walker])
        t_walker.host_satellite = sat_walker

        possible = make_possible_link(t_sso, t_walker)

        plan = make_mock_plan(
            []
        )  # phase 2 finds nothing — falls through to dangling check

        with patch(
            f"{MODULE}.compute_OISL_links_from_terminal_pools_filtered",
            return_value=[possible],
        ):
            strategy = make_strategy(
                [sat_sso, sat_peer, sat_walker], [(sso_shell, plan)]
            )
            result = strategy.compute_strategy()

        obsolete_for_intra = [o for o in result.obsolete_links if o.link == intra_link]
        assert len(obsolete_for_intra) == 1
