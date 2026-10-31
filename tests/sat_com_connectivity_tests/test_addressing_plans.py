import uuid
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from sat_com_connectivity.inter_satellite_link_connectivity.addressing_plans import (
    SSODawnDuskStaticAddressingPlan,
    _filter_by_orientation,
    FullMeshWalkerDeltaStaticAddressingPlan,
    FullMeshWalkerStarStaticAddressingPlan,
)
from sat_com_connectivity.inter_satellite_link_connectivity.models import (
    PossibleOpticalLink,
    OpticISLVisibilityConstraintResult,
)
from sat_com_model.models import OpticalInterSatelliteLinkModel
from sat_com_model.models import (
    InterSatelliteLinkDirection,
    InterSatelliteLinkOrientation,
    WalkerShell,
    DawnDuskSSOShell,
    OpticalLinkTerminal,
    Satellite,
    OpticalTerminalConfiguration,
)

ADVANCED = OpticalInterSatelliteLinkModel.ADVANCED

ADDRESSING_PLANS = (
    "sat_com_connectivity.inter_satellite_link_connectivity.addressing_plans"
)


# ===========================================================================
# Factories
# ===========================================================================


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
        los_min_altitude_km=7000,
        los_clear=True,
        relative_azimuth_angle_degree=0.0,
    )


def make_terminal(
    descriptor: InterSatelliteLinkOrientation = InterSatelliteLinkOrientation.INTRA_PLANE_FORWARD,
    terminal_configuration: OpticalTerminalConfiguration | None = None,
) -> OpticalLinkTerminal:
    terminal = MagicMock(spec=OpticalLinkTerminal)
    terminal.terminal_id = uuid.uuid4()
    terminal.descriptor = descriptor
    terminal.link = None
    terminal.orientation_possibilities = [descriptor]
    terminal.__hash__ = lambda self: hash(self.terminal_id)
    terminal.__eq__ = lambda self, other: (
        isinstance(other, type(self)) and self.terminal_id == other.terminal_id
    )
    terminal.terminal_configuration = (
        terminal_configuration or OpticalTerminalConfiguration()
    )
    return terminal


def make_4_terminal_satellite(object_id: int, topology_id: int, shell) -> Satellite:
    """
    Satellite with 4 terminals:
      [0] INTRA_PLANE_FORWARD
      [1] INTER_PLANE_LEFT
      [2] INTER_PLANE_RIGHT
      [3] INTRA_PLANE_BACKWARD
    """
    terminals = [
        make_terminal(InterSatelliteLinkOrientation.INTRA_PLANE_FORWARD),
        make_terminal(InterSatelliteLinkOrientation.INTER_PLANE_LEFT),
        make_terminal(InterSatelliteLinkOrientation.INTER_PLANE_RIGHT),
        make_terminal(InterSatelliteLinkOrientation.INTRA_PLANE_BACKWARD),
    ]
    sat = MagicMock(spec=Satellite)
    sat.topology_uniq_id = topology_id
    sat.object_id = object_id
    sat.shell = shell
    sat.satellite_name = f"SAT-{object_id}"
    sat.optical_link_terminals = terminals
    for t in terminals:
        t.host_satellite = sat
    return sat


def make_walker_shell(
    identifier: str = "walker-a",
    shell_type: str = "delta",
    orbits: int = 3,
    sats_per_orbit: int = 3,
    isl_shift: int = 0,
) -> WalkerShell:
    shell = MagicMock(spec=WalkerShell)
    shell.identifier = identifier
    shell.type = shell_type
    shell.amount_of_orbit_plane = orbits
    shell.amount_of_satellite_per_orbit_plane = sats_per_orbit
    shell.adjacent_inter_satellite_shifting = isl_shift
    return shell


def make_sso_shell(
    identifier: str = "sso-a", amount_of_satellite: int = 3
) -> DawnDuskSSOShell:
    shell = MagicMock(spec=DawnDuskSSOShell)
    shell.identifier = identifier
    shell.amount_of_satellite = amount_of_satellite
    return shell


def make_possible_link(
    terminal_a: OpticalLinkTerminal,
    terminal_b: OpticalLinkTerminal,
    score: float = 0.0,
) -> PossibleOpticalLink:
    possible = MagicMock(spec=PossibleOpticalLink)
    possible.terminal_a = terminal_a
    possible.terminal_b = terminal_b
    possible.selection_score = score
    possible.bidirectional_possible = True
    possible.constraint_a_to_b = make_constraint()
    possible.constraint_b_to_a = make_constraint()
    possible.estimated_duration = 30
    possible.temporary_unavailable = False
    possible.estimated_recover_time = None
    return possible


def make_constellation(shell, n_orbits: int, sats_per_orbit: int) -> list[Satellite]:
    satellites = []
    for i in range(n_orbits):
        for j in range(sats_per_orbit):
            obj_id = i * sats_per_orbit + j
            satellites.append(make_4_terminal_satellite(obj_id, obj_id, shell))
    return satellites


# Terminal accessors — match make_4_terminal_satellite order
def t_fwd(sat):
    return sat.optical_link_terminals[0]


def t_left(sat):
    return sat.optical_link_terminals[1]


def t_right(sat):
    return sat.optical_link_terminals[2]


def t_bwd(sat):
    return sat.optical_link_terminals[3]


# ===========================================================================
# Fakes for the two distinct geometry entry points
# ===========================================================================
#
# The addressing plan now calls two different functions at two different
# phases:
#
#   - compute_OISL_links_from_terminal_pools(terminals_group_1: list,
#     terminals_group_2: list, ...) -> list[PossibleOpticalLink]
#     Used once, during _select_static_terminals (selection/booking phase).
#     Takes pools, returns a ranked list.
#
#   - compute_OISL_constraint_for_known_pair(terminal_a, terminal_b, cache,
#     ...) -> PossibleOpticalLink | None
#     Used every tick, during _build_associations_from_grid (refresh phase).
#     Takes a single already-decided pair, returns a single result.
#
# Tests must patch whichever one the behavior under test actually lives in,
# and any test that runs get_link_associations end-to-end also needs
# _EciCache patched, since _build_associations_from_grid now instantiates
# one for real and calls .warm(...) on it.


def fake_pool_returns_first(terminals_group_1, terminals_group_2, **_):
    """Fake for compute_OISL_links_from_terminal_pools — list in, list out."""
    if terminals_group_1 and terminals_group_2:
        return [make_possible_link(terminals_group_1[0], terminals_group_2[0])]
    return []


def fake_pair_returns_link(terminal_a, terminal_b, cache=None, **_):
    """Fake for compute_OISL_constraint_for_known_pair — single pair in, single result out."""
    return make_possible_link(terminal_a, terminal_b)


@contextmanager
def patch_geometry(pool_side_effect=None, pair_side_effect=None):
    """
    Patches every external geometry call get_link_associations touches:
    the pool-based selection call, the single-pair refresh call, and the
    ECI cache warm-up (which would otherwise run real propagation against
    MagicMock satellites and fail).
    """
    with patch(
        f"{ADDRESSING_PLANS}.compute_OISL_links_from_terminal_pools",
        side_effect=pool_side_effect or fake_pool_returns_first,
    ), patch(
        f"{ADDRESSING_PLANS}.compute_OISL_constraint_for_known_pair",
        side_effect=pair_side_effect or fake_pair_returns_link,
    ), patch(
        f"{ADDRESSING_PLANS}._EciCache"
    ) as mock_cache_cls:
        mock_cache_cls.return_value.warm.return_value = None
        yield


# ===========================================================================
# _filter_by_orientation
# ===========================================================================


class TestFilterByOrientation:

    def test_keeps_matching_pair(self):
        t_a = make_terminal(InterSatelliteLinkOrientation.INTRA_PLANE_FORWARD)
        t_b = make_terminal(InterSatelliteLinkOrientation.INTRA_PLANE_BACKWARD)
        result = _filter_by_orientation(
            [make_possible_link(t_a, t_b)],
            {InterSatelliteLinkOrientation.INTRA_PLANE_FORWARD},
            {InterSatelliteLinkOrientation.INTRA_PLANE_BACKWARD},
        )
        assert len(result) == 1

    def test_removes_mismatched_terminal_a(self):
        t_a = make_terminal(InterSatelliteLinkOrientation.INTER_PLANE_LEFT)
        t_b = make_terminal(InterSatelliteLinkOrientation.INTRA_PLANE_BACKWARD)
        result = _filter_by_orientation(
            [make_possible_link(t_a, t_b)],
            {InterSatelliteLinkOrientation.INTRA_PLANE_FORWARD},
            {InterSatelliteLinkOrientation.INTRA_PLANE_BACKWARD},
        )
        assert result == []

    def test_removes_mismatched_terminal_b(self):
        t_a = make_terminal(InterSatelliteLinkOrientation.INTRA_PLANE_FORWARD)
        t_b = make_terminal(InterSatelliteLinkOrientation.INTER_PLANE_LEFT)
        result = _filter_by_orientation(
            [make_possible_link(t_a, t_b)],
            {InterSatelliteLinkOrientation.INTRA_PLANE_FORWARD},
            {InterSatelliteLinkOrientation.INTRA_PLANE_BACKWARD},
        )
        assert result == []

    def test_empty_candidates_returns_empty(self):
        result = _filter_by_orientation(
            [],
            {InterSatelliteLinkOrientation.INTRA_PLANE_FORWARD},
            {InterSatelliteLinkOrientation.INTRA_PLANE_BACKWARD},
        )
        assert result == []

    def test_filters_multiple_correctly(self):
        t_a1 = make_terminal(InterSatelliteLinkOrientation.INTRA_PLANE_FORWARD)
        t_b1 = make_terminal(InterSatelliteLinkOrientation.INTRA_PLANE_BACKWARD)
        t_a2 = make_terminal(InterSatelliteLinkOrientation.INTER_PLANE_LEFT)
        t_b2 = make_terminal(InterSatelliteLinkOrientation.INTER_PLANE_RIGHT)
        result = _filter_by_orientation(
            [make_possible_link(t_a1, t_b1), make_possible_link(t_a2, t_b2)],
            {InterSatelliteLinkOrientation.INTRA_PLANE_FORWARD},
            {InterSatelliteLinkOrientation.INTRA_PLANE_BACKWARD},
        )
        assert len(result) == 1
        assert result[0].terminal_a == t_a1


# ===========================================================================
# WalkerStaticAddressingPlan — grid building
# ===========================================================================


class TestWalkerStaticAddressingPlanGridBuilding:

    def test_delta_grid_built_at_init(self):
        with patch(
            f"{ADDRESSING_PLANS}.generate_walker_delta_constellation_grid",
            return_value=[],
        ) as mock_delta, patch(
            f"{ADDRESSING_PLANS}.generate_walker_star_constellation_grid",
            return_value=[],
        ) as mock_star:
            FullMeshWalkerDeltaStaticAddressingPlan(
                make_walker_shell(shell_type="delta", orbits=5, sats_per_orbit=4)
            )

        mock_delta.assert_called_once_with(
            number_orbits=5, number_satellites_per_orbit=4, isl_shift=0
        )
        mock_star.assert_not_called()

    def test_star_grid_built_at_init(self):
        with patch(
            f"{ADDRESSING_PLANS}.generate_walker_delta_constellation_grid",
            return_value=[],
        ) as mock_delta, patch(
            f"{ADDRESSING_PLANS}.generate_walker_star_constellation_grid",
            return_value=[],
        ) as mock_star:
            FullMeshWalkerStarStaticAddressingPlan(
                make_walker_shell(shell_type="star", orbits=4, sats_per_orbit=6)
            )

        mock_star.assert_called_once_with(
            number_orbits=4, number_satellites_per_orbit=6, isl_shift=0
        )
        mock_delta.assert_not_called()

    def test_isl_shift_passed_to_generator(self):
        with patch(
            f"{ADDRESSING_PLANS}.generate_walker_delta_constellation_grid",
            return_value=[],
        ) as mock_delta:
            FullMeshWalkerDeltaStaticAddressingPlan(make_walker_shell(isl_shift=3))
        assert mock_delta.call_args.kwargs["isl_shift"] == 3

    def test_grid_stored_as_instance_attribute(self):
        grid = [(0, 1, InterSatelliteLinkDirection.ORBITAL)]
        with patch(
            f"{ADDRESSING_PLANS}.generate_walker_delta_constellation_grid",
            return_value=grid,
        ):
            plan = FullMeshWalkerDeltaStaticAddressingPlan(make_walker_shell())
        assert plan.grid == grid

    def test_star_and_delta_produce_different_link_counts(self):
        delta_shell = make_walker_shell(shell_type="delta", orbits=3, sats_per_orbit=3)
        star_shell = make_walker_shell(shell_type="star", orbits=3, sats_per_orbit=3)

        plan_delta = FullMeshWalkerDeltaStaticAddressingPlan(delta_shell)
        plan_star = FullMeshWalkerStarStaticAddressingPlan(star_shell)

        with patch_geometry():
            result_delta = plan_delta.get_link_associations(
                make_constellation(delta_shell, 3, 3)
            )
            result_star = plan_star.get_link_associations(
                make_constellation(star_shell, 3, 3)
            )

        assert len(result_delta) > len(result_star)


# ===========================================================================
# WalkerStaticAddressingPlan — _build_associations_from_grid
# ===========================================================================


class TestWalkerBuildAssociationsOrbital:

    def _setup(self):
        shell = make_walker_shell()
        sat_a = make_4_terminal_satellite(0, 0, shell)
        sat_b = make_4_terminal_satellite(1, 1, shell)
        plan = FullMeshWalkerDeltaStaticAddressingPlan(
            shell, optical_link_model=ADVANCED
        )
        plan.grid = [(0, 1, InterSatelliteLinkDirection.ORBITAL)]
        return plan, sat_a, sat_b

    def test_returns_orbital_association(self):
        plan, sat_a, sat_b = self._setup()
        with patch_geometry():
            result = plan.get_link_associations([sat_a, sat_b])
        assert len(result) == 1
        assert result[0].direction == InterSatelliteLinkDirection.ORBITAL

    def test_pool_and_pair_calls_total_three(self):
        """
        Selection phase: 2 pool calls (case_1 FORWARD->BACKWARD,
        case_2 BACKWARD->FORWARD). Refresh phase: 1 pair call
        (single grid link). Total = 3.
        """
        plan, sat_a, sat_b = self._setup()
        call_log = []

        def fake_pool(terminals_group_1, terminals_group_2, **_):
            call_log.append("pool")
            return fake_pool_returns_first(terminals_group_1, terminals_group_2)

        def fake_pair(terminal_a, terminal_b, cache=None, **_):
            call_log.append("pair")
            return fake_pair_returns_link(terminal_a, terminal_b)

        with patch_geometry(pool_side_effect=fake_pool, pair_side_effect=fake_pair):
            plan.get_link_associations([sat_a, sat_b])

        assert call_log.count("pool") == 2
        assert call_log.count("pair") == 1

    def test_case_1_receives_forward_backward_pools(self):
        """Selection-phase behavior — patch the pool function directly."""
        plan, sat_a, sat_b = self._setup()
        first_call_args = []

        def fake_pool(terminals_group_1, terminals_group_2, **_):
            if not first_call_args:
                first_call_args.append(
                    (
                        [t.descriptor for t in terminals_group_1],
                        [t.descriptor for t in terminals_group_2],
                    )
                )
            return fake_pool_returns_first(terminals_group_1, terminals_group_2)

        with patch_geometry(pool_side_effect=fake_pool):
            plan.get_link_associations([sat_a, sat_b])

        g1_descs, g2_descs = first_call_args[0]
        assert InterSatelliteLinkOrientation.INTRA_PLANE_FORWARD in g1_descs
        assert InterSatelliteLinkOrientation.INTRA_PLANE_BACKWARD in g2_descs

    def test_case_2_receives_backward_forward_pools(self):
        """Selection-phase behavior — patch the pool function directly."""
        plan, sat_a, sat_b = self._setup()
        all_call_args = []

        def fake_pool(terminals_group_1, terminals_group_2, **_):
            all_call_args.append(
                (
                    [t.descriptor for t in terminals_group_1],
                    [t.descriptor for t in terminals_group_2],
                )
            )
            return fake_pool_returns_first(terminals_group_1, terminals_group_2)

        with patch_geometry(pool_side_effect=fake_pool):
            plan.get_link_associations([sat_a, sat_b])

        g1_descs, g2_descs = all_call_args[1]
        assert InterSatelliteLinkOrientation.INTRA_PLANE_BACKWARD in g1_descs
        assert InterSatelliteLinkOrientation.INTRA_PLANE_FORWARD in g2_descs

    def test_best_score_candidate_wins_across_cases(self):
        """Ranking happens in selection — patch the pool function (list-returning)."""
        plan, sat_a, sat_b = self._setup()
        t_winner = t_bwd(sat_a)
        t_winner_peer = t_fwd(sat_b)
        call_index = [0]

        def fake_pool(terminals_group_1, terminals_group_2, **_):
            idx = call_index[0]
            call_index[0] += 1
            if idx == 0:
                return [
                    make_possible_link(
                        terminals_group_1[0], terminals_group_2[0], score=10.0
                    )
                ]
            return [make_possible_link(t_winner, t_winner_peer, score=1.0)]

        with patch_geometry(pool_side_effect=fake_pool):
            result = plan.get_link_associations([sat_a, sat_b])

        assert result[0].terminal_a == t_winner
        assert result[0].terminal_b == t_winner_peer

    def test_link_is_none(self):
        plan, sat_a, sat_b = self._setup()
        with patch_geometry():
            result = plan.get_link_associations([sat_a, sat_b])
        assert result[0].link is None

    def test_constraints_propagated(self):
        """Constraint comes from the refresh phase — patch the pair function."""
        plan, sat_a, sat_b = self._setup()
        expected = make_constraint()
        expected.range_distance_km = 1234.0

        def fake_pair(terminal_a, terminal_b, cache=None, **_):
            p = make_possible_link(terminal_a, terminal_b)
            p.constraint_a_to_b = expected
            return p

        with patch_geometry(pair_side_effect=fake_pair):
            result = plan.get_link_associations([sat_a, sat_b])

        assert result[0].constraint_a_to_b == expected

    def test_no_candidates_emits_warning_and_skips(self):
        plan, sat_a, sat_b = self._setup()
        with patch(
            f"{ADDRESSING_PLANS}.compute_OISL_links_from_terminal_pools",
            return_value=[],
        ), patch(f"{ADDRESSING_PLANS}._EciCache"), pytest.warns(UserWarning):
            result = plan.get_link_associations([sat_a, sat_b])
        assert result == []

    def test_missing_satellite_emits_warning_and_skips(self):
        plan, sat_a, sat_b = self._setup()
        with pytest.warns(UserWarning), patch(
            f"{ADDRESSING_PLANS}.compute_OISL_links_from_terminal_pools",
            return_value=[],
        ), patch(f"{ADDRESSING_PLANS}._EciCache"):
            result = plan.get_link_associations([sat_b])  # sat_a (id=0) absent
        assert result == []

    def test_satellite_lookup_uses_object_id_not_topology_id(self):
        shell = make_walker_shell()
        plan = FullMeshWalkerDeltaStaticAddressingPlan(
            shell, optical_link_model=ADVANCED
        )
        plan.grid = [(10, 20, InterSatelliteLinkDirection.ORBITAL)]
        sat_a = make_4_terminal_satellite(object_id=10, topology_id=99, shell=shell)
        sat_b = make_4_terminal_satellite(object_id=20, topology_id=88, shell=shell)

        with patch_geometry():
            result = plan.get_link_associations([sat_a, sat_b])

        assert len(result) == 1
        assert result[0].satellite_a == sat_a
        assert result[0].satellite_b == sat_b


class TestWalkerBuildAssociationsAdjacent:

    def _setup(self):
        shell = make_walker_shell()
        sat_a = make_4_terminal_satellite(0, 0, shell)
        sat_b = make_4_terminal_satellite(1, 1, shell)
        plan = FullMeshWalkerDeltaStaticAddressingPlan(
            shell, optical_link_model=ADVANCED
        )
        plan.grid = [(0, 1, InterSatelliteLinkDirection.ADJACENT)]
        return plan, sat_a, sat_b

    def test_returns_adjacent_association(self):
        plan, sat_a, sat_b = self._setup()
        with patch_geometry():
            result = plan.get_link_associations([sat_a, sat_b])
        assert len(result) == 1
        assert result[0].direction == InterSatelliteLinkDirection.ADJACENT

    def test_pool_and_pair_calls_total_three(self):
        plan, sat_a, sat_b = self._setup()
        call_log = []

        def fake_pool(terminals_group_1, terminals_group_2, **_):
            call_log.append("pool")
            return fake_pool_returns_first(terminals_group_1, terminals_group_2)

        def fake_pair(terminal_a, terminal_b, cache=None, **_):
            call_log.append("pair")
            return fake_pair_returns_link(terminal_a, terminal_b)

        with patch_geometry(pool_side_effect=fake_pool, pair_side_effect=fake_pair):
            plan.get_link_associations([sat_a, sat_b])

        assert call_log.count("pool") == 4
        assert call_log.count("pair") == 1

    def test_case_1_receives_left_right_pools(self):
        plan, sat_a, sat_b = self._setup()
        first_call_args = []

        def fake_pool(terminals_group_1, terminals_group_2, **_):
            if not first_call_args:
                first_call_args.append(
                    (
                        [t.descriptor for t in terminals_group_1],
                        [t.descriptor for t in terminals_group_2],
                    )
                )
            return fake_pool_returns_first(terminals_group_1, terminals_group_2)

        with patch_geometry(pool_side_effect=fake_pool):
            plan.get_link_associations([sat_a, sat_b])

        g1_descs, g2_descs = first_call_args[0]
        assert InterSatelliteLinkOrientation.INTER_PLANE_LEFT in g1_descs
        assert InterSatelliteLinkOrientation.INTER_PLANE_RIGHT in g2_descs

    def test_case_2_receives_right_left_pools(self):
        """
        Case 2 passes destinations_left (LEFT from sat_b) as group_1
        and sources_right (RIGHT from sat_a) as group_2.
        """
        plan, sat_a, sat_b = self._setup()
        all_call_args = []

        def fake_pool(terminals_group_1, terminals_group_2, **_):
            all_call_args.append(
                (
                    [t.descriptor for t in terminals_group_1],
                    [t.descriptor for t in terminals_group_2],
                )
            )
            return fake_pool_returns_first(terminals_group_1, terminals_group_2)

        with patch_geometry(pool_side_effect=fake_pool):
            plan.get_link_associations([sat_a, sat_b])

        g1_descs, g2_descs = all_call_args[1]
        assert InterSatelliteLinkOrientation.INTER_PLANE_LEFT in g1_descs
        assert InterSatelliteLinkOrientation.INTER_PLANE_RIGHT in g2_descs

    def test_no_candidates_emits_warning_and_skips(self):
        plan, sat_a, sat_b = self._setup()
        with patch(
            f"{ADDRESSING_PLANS}.compute_OISL_links_from_terminal_pools",
            return_value=[],
        ), patch(f"{ADDRESSING_PLANS}._EciCache"), pytest.warns(UserWarning):
            result = plan.get_link_associations([sat_a, sat_b])
        assert result == []


class TestWalkerStaticTerminalSelection:

    def test_contested_terminal_falls_back_at_selection_time(self):
        """
        Fallback resolution happens once, during _select_static_terminals.
        This is pure selection-phase logic — patch the pool function only;
        _select_static_terminals never touches _EciCache directly.
        """
        shell = make_walker_shell()
        sat_a = make_4_terminal_satellite(0, 0, shell)
        sat_b = make_4_terminal_satellite(1, 1, shell)
        sat_c = make_4_terminal_satellite(2, 2, shell)

        plan = FullMeshWalkerDeltaStaticAddressingPlan(
            shell, optical_link_model=ADVANCED
        )
        plan.grid = [
            (0, 1, InterSatelliteLinkDirection.ADJACENT),
            (2, 1, InterSatelliteLinkDirection.ADJACENT),
        ]

        contested = t_left(sat_b)
        fallback = t_right(sat_b)

        def fake_pool(terminals_group_1, terminals_group_2, **_):
            if not terminals_group_1 or not terminals_group_2:
                return []
            results = [make_possible_link(terminals_group_1[0], contested, score=0.0)]
            if fallback in terminals_group_2:
                results.append(
                    make_possible_link(terminals_group_1[0], fallback, score=5.0)
                )
            return results

        satellite_lookup = {0: sat_a, 1: sat_b, 2: sat_c}

        with patch(
            f"{ADDRESSING_PLANS}.compute_OISL_links_from_terminal_pools",
            side_effect=fake_pool,
        ):
            plan._select_static_terminals(satellite_lookup)

        assigned_terminals_b = [t_b for _, t_b in plan._terminal_assignment.values()]
        assert assigned_terminals_b.count(contested) == 1
        assert fallback in assigned_terminals_b

    def test_terminal_assignment_is_stable_across_ticks(self):
        """Once selected, the same terminal pair is reused on every call."""
        shell = make_walker_shell()
        sat_a = make_4_terminal_satellite(0, 0, shell)
        sat_b = make_4_terminal_satellite(1, 1, shell)

        plan = FullMeshWalkerDeltaStaticAddressingPlan(
            shell, optical_link_model=ADVANCED
        )
        plan.grid = [(0, 1, InterSatelliteLinkDirection.ADJACENT)]

        with patch_geometry():
            result_1 = plan.get_link_associations([sat_a, sat_b])
            result_2 = plan.get_link_associations([sat_a, sat_b])

        assert (result_1[0].terminal_a, result_1[0].terminal_b) == (
            result_2[0].terminal_a,
            result_2[0].terminal_b,
        )

    def test_all_candidates_booked_raises_value_error(self):
        """When every candidate's terminals are booked, selection must warn and skip."""
        shell = make_walker_shell()
        sat_a = make_4_terminal_satellite(0, 0, shell)
        sat_b = make_4_terminal_satellite(1, 1, shell)
        sat_c = make_4_terminal_satellite(2, 2, shell)

        plan = FullMeshWalkerDeltaStaticAddressingPlan(
            shell, optical_link_model=ADVANCED
        )
        plan.grid = [
            (0, 1, InterSatelliteLinkDirection.ORBITAL),
            (2, 1, InterSatelliteLinkDirection.ORBITAL),
        ]

        only_terminal_a = t_fwd(sat_a)
        only_terminal_b = t_bwd(sat_b)

        def fake_pool(terminals_group_1, terminals_group_2, **_):
            # Always offer only the same contested pair — no fallback
            return [make_possible_link(only_terminal_a, only_terminal_b, score=0.0)]

        with patch_geometry(pool_side_effect=fake_pool):
            with pytest.warns(Warning) as record:
                plan.get_link_associations([sat_a, sat_b])

            assert len(record) >= 1

    def test_booked_terminals_emits_warning(self):
        """Falling back to the next candidate must emit a UserWarning."""
        shell = make_walker_shell()
        sat_a = make_4_terminal_satellite(0, 0, shell)
        sat_b = make_4_terminal_satellite(1, 1, shell)
        sat_c = make_4_terminal_satellite(2, 2, shell)

        plan = FullMeshWalkerDeltaStaticAddressingPlan(
            shell, optical_link_model=ADVANCED
        )
        plan.grid = [
            (0, 1, InterSatelliteLinkDirection.ORBITAL),
            (2, 1, InterSatelliteLinkDirection.ORBITAL),
        ]

        contested = t_bwd(sat_b)
        fallback = t_fwd(sat_b)

        def fake_pool(terminals_group_1, terminals_group_2, **_):
            return [
                make_possible_link(terminals_group_1[0], contested, score=0.0),
                make_possible_link(terminals_group_1[0], fallback, score=5.0),
            ]

        with patch_geometry(pool_side_effect=fake_pool):
            plan.get_link_associations([sat_a, sat_b, sat_c])


class TestWalkerUnknownDirection:

    def test_undefined_direction_raises_value_error(self):
        shell = make_walker_shell()
        sat_a = make_4_terminal_satellite(0, 0, shell)
        sat_b = make_4_terminal_satellite(1, 1, shell)
        plan = FullMeshWalkerDeltaStaticAddressingPlan(
            shell, optical_link_model=ADVANCED
        )
        plan.grid = [(0, 1, InterSatelliteLinkDirection.UNDEFINED)]

        with pytest.raises(ValueError):
            plan.get_link_associations([sat_a, sat_b])


# ===========================================================================
# SSODawnDuskStaticAddressingPlan
# ===========================================================================
#
# This plan still calls compute_OISL_links_from_terminal_pools directly —
# it wasn't part of the static-terminal-selection refactor, so these tests
# are unchanged.


class TestSSODawnDuskStaticAddressingPlanGridBuilding:

    def test_grid_built_at_init(self):
        with patch(
            f"{ADDRESSING_PLANS}.generate_sun_synchronous_constellation_grid",
            return_value=[],
        ) as mock_grid:
            SSODawnDuskStaticAddressingPlan(make_sso_shell(amount_of_satellite=7))
        mock_grid.assert_called_once_with(number_satellites_per_orbit=7)

    def test_grid_stored_as_instance_attribute(self):
        grid = [(0, 1, InterSatelliteLinkDirection.ORBITAL)]
        with patch(
            f"{ADDRESSING_PLANS}.generate_sun_synchronous_constellation_grid",
            return_value=grid,
        ):
            plan = SSODawnDuskStaticAddressingPlan(make_sso_shell())
        assert plan.grid == grid


class TestSSOBuildAssociationsOrbital:

    def _setup(self, n: int = 2):
        shell = make_sso_shell(amount_of_satellite=n)
        plan = SSODawnDuskStaticAddressingPlan(shell, optical_link_model=ADVANCED)
        plan.grid = [(0, 1, InterSatelliteLinkDirection.ORBITAL)]
        satellites = [make_4_terminal_satellite(i, i, shell) for i in range(n)]
        return plan, satellites

    def test_returns_orbital_association(self):
        plan, satellites = self._setup()
        with patch(
            f"{ADDRESSING_PLANS}.compute_OISL_links_from_terminal_pools",
            side_effect=fake_pool_returns_first,
        ):
            result = plan.get_link_associations(satellites)
        assert len(result) == 1
        assert result[0].direction == InterSatelliteLinkDirection.ORBITAL

    def test_two_pool_calls_per_pair(self):
        plan, satellites = self._setup()
        call_count = []

        def fake_pool(terminals_group_1, terminals_group_2, **_):
            call_count.append(1)
            return fake_pool_returns_first(terminals_group_1, terminals_group_2)

        with patch(
            f"{ADDRESSING_PLANS}.compute_OISL_links_from_terminal_pools",
            side_effect=fake_pool,
        ):
            plan.get_link_associations(satellites)

        assert sum(call_count) == 2

    def test_only_intra_plane_terminals_passed_to_pool(self):
        plan, satellites = self._setup()
        all_group_descriptors = []

        def fake_pool(terminals_group_1, terminals_group_2, **_):
            all_group_descriptors.extend(
                [t.descriptor for t in terminals_group_1 + terminals_group_2]
            )
            return fake_pool_returns_first(terminals_group_1, terminals_group_2)

        with patch(
            f"{ADDRESSING_PLANS}.compute_OISL_links_from_terminal_pools",
            side_effect=fake_pool,
        ):
            plan.get_link_associations(satellites)

        intra = {
            InterSatelliteLinkOrientation.INTRA_PLANE_FORWARD,
            InterSatelliteLinkOrientation.INTRA_PLANE_BACKWARD,
        }
        for desc in all_group_descriptors:
            assert desc in intra

    def test_non_orbital_direction_raises_not_implemented_error(self):
        plan, satellites = self._setup()
        plan.grid = [(0, 1, InterSatelliteLinkDirection.ADJACENT)]

        with pytest.raises(NotImplementedError):
            plan.get_link_associations(satellites)

    def test_undefined_direction_raises_not_implemented_error(self):
        plan, satellites = self._setup()
        plan.grid = [(0, 1, InterSatelliteLinkDirection.UNDEFINED)]

        with pytest.raises(NotImplementedError):
            plan.get_link_associations(satellites)

    def test_no_candidates_emits_warning_and_skips(self):
        plan, satellites = self._setup()
        with patch(
            f"{ADDRESSING_PLANS}.compute_OISL_links_from_terminal_pools",
            return_value=[],
        ), pytest.warns(UserWarning):
            result = plan.get_link_associations(satellites)
        assert result == []

    def test_missing_satellite_emits_warning_and_skips(self):
        plan, satellites = self._setup()
        with pytest.warns(UserWarning), patch(
            f"{ADDRESSING_PLANS}.compute_OISL_links_from_terminal_pools",
            return_value=[],
        ):
            result = plan.get_link_associations([satellites[0]])
        assert result == []

    def test_link_is_none(self):
        plan, satellites = self._setup()
        with patch(
            f"{ADDRESSING_PLANS}.compute_OISL_links_from_terminal_pools",
            side_effect=fake_pool_returns_first,
        ):
            result = plan.get_link_associations(satellites)
        assert result[0].link is None

    def test_constraints_propagated(self):
        plan, satellites = self._setup()
        expected = make_constraint()
        expected.range_distance_km = 999.0

        def fake_pool(terminals_group_1, terminals_group_2, **_):
            p = make_possible_link(terminals_group_1[0], terminals_group_2[0])
            p.constraint_a_to_b = expected
            return [p]

        with patch(
            f"{ADDRESSING_PLANS}.compute_OISL_links_from_terminal_pools",
            side_effect=fake_pool,
        ):
            result = plan.get_link_associations(satellites)

        assert result[0].constraint_a_to_b == expected

    def test_satellite_lookup_uses_object_id(self):
        shell = make_sso_shell()
        plan = SSODawnDuskStaticAddressingPlan(shell, optical_link_model=ADVANCED)
        plan.grid = [(10, 20, InterSatelliteLinkDirection.ORBITAL)]
        sat_a = make_4_terminal_satellite(object_id=10, topology_id=99, shell=shell)
        sat_b = make_4_terminal_satellite(object_id=20, topology_id=88, shell=shell)

        with patch(
            f"{ADDRESSING_PLANS}.compute_OISL_links_from_terminal_pools",
            side_effect=fake_pool_returns_first,
        ):
            result = plan.get_link_associations([sat_a, sat_b])

        assert len(result) == 1
        assert result[0].satellite_a == sat_a
        assert result[0].satellite_b == sat_b

    def test_all_candidates_booked_raises_warnings(self):
        shell = make_sso_shell()
        plan = SSODawnDuskStaticAddressingPlan(shell, optical_link_model=ADVANCED)
        sat_a = make_4_terminal_satellite(0, 0, shell)
        sat_b = make_4_terminal_satellite(1, 1, shell)
        plan.grid = [
            (0, 1, InterSatelliteLinkDirection.ORBITAL),
            (1, 0, InterSatelliteLinkDirection.ORBITAL),
        ]

        only_a = t_fwd(sat_a)
        only_b = t_bwd(sat_b)

        with patch(
            f"{ADDRESSING_PLANS}.compute_OISL_links_from_terminal_pools",
            return_value=[make_possible_link(only_a, only_b, score=0.0)],
        ):
            with pytest.warns(Warning) as record:
                plan.get_link_associations([sat_a, sat_b])

            assert len(record) >= 2

    def test_booked_fallback_emits_warning(self):
        shell = make_sso_shell()
        plan = SSODawnDuskStaticAddressingPlan(shell, optical_link_model=ADVANCED)
        sat_a = make_4_terminal_satellite(0, 0, shell)
        sat_b = make_4_terminal_satellite(1, 1, shell)
        sat_c = make_4_terminal_satellite(2, 2, shell)
        plan.grid = [
            (0, 1, InterSatelliteLinkDirection.ORBITAL),
            (2, 1, InterSatelliteLinkDirection.ORBITAL),
        ]

        contested = t_bwd(sat_b)
        fallback = t_fwd(sat_b)

        def fake_pool(terminals_group_1, terminals_group_2, **_):
            return [
                make_possible_link(terminals_group_1[0], contested, score=0.0),
                make_possible_link(terminals_group_1[0], fallback, score=5.0),
            ]

        with pytest.warns(UserWarning), patch(
            f"{ADDRESSING_PLANS}.compute_OISL_links_from_terminal_pools",
            side_effect=fake_pool,
        ):
            plan.get_link_associations([sat_a, sat_b, sat_c])
