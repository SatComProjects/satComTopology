import uuid
from unittest.mock import MagicMock, patch

import pytest

from sat_com_connectivity.inter_satellite_link_connectivity.addressing_plans import (
    WalkerStaticAddressingPlan,
    SSODawnDuskStaticAddressingPlan,
    _filter_by_orientation,
)
from sat_com_connectivity.inter_satellite_link_connectivity.models import (
    PossibleOpticalLink,
    OpticISLVisibilityConstraintResult,
)
from sat_com_model.models import (
    InterSatelliteLinkDirection,
    InterSatelliteLinkOrientation,
    WalkerShell,
    DawnDuskSSOShell,
    OpticalLinkTerminal,
    Satellite,
)

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
    )


def make_terminal(
    descriptor: InterSatelliteLinkOrientation = InterSatelliteLinkOrientation.INTRA_PLANE_FORWARD,
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


def fake_compute_returns_first(terminals_group_1, terminals_group_2, **_):
    """Simplest fake — returns one link using first terminal from each pool."""
    if terminals_group_1 and terminals_group_2:
        return [make_possible_link(terminals_group_1[0], terminals_group_2[0])]
    return []


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
            WalkerStaticAddressingPlan(
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
            WalkerStaticAddressingPlan(
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
            WalkerStaticAddressingPlan(make_walker_shell(isl_shift=3))
        assert mock_delta.call_args.kwargs["isl_shift"] == 3

    def test_grid_stored_as_instance_attribute(self):
        grid = [(0, 1, InterSatelliteLinkDirection.ORBITAL)]
        with patch(
            f"{ADDRESSING_PLANS}.generate_walker_delta_constellation_grid",
            return_value=grid,
        ):
            plan = WalkerStaticAddressingPlan(make_walker_shell())
        assert plan.grid == grid

    def test_star_and_delta_produce_different_link_counts(self):
        delta_shell = make_walker_shell(shell_type="delta", orbits=3, sats_per_orbit=3)
        star_shell = make_walker_shell(shell_type="star", orbits=3, sats_per_orbit=3)

        plan_delta = WalkerStaticAddressingPlan(delta_shell)
        plan_star = WalkerStaticAddressingPlan(star_shell)

        with patch(
            f"{ADDRESSING_PLANS}.compute_OISL_links_from_terminal_pools",
            side_effect=fake_compute_returns_first,
        ):
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
        plan = WalkerStaticAddressingPlan(shell)
        plan.grid = [(0, 1, InterSatelliteLinkDirection.ORBITAL)]
        return plan, sat_a, sat_b

    def test_returns_orbital_association(self):
        plan, sat_a, sat_b = self._setup()
        with patch(
            f"{ADDRESSING_PLANS}.compute_OISL_links_from_terminal_pools",
            side_effect=fake_compute_returns_first,
        ):
            result = plan.get_link_associations([sat_a, sat_b])
        assert len(result) == 1
        assert result[0].direction == InterSatelliteLinkDirection.ORBITAL

    def test_two_pool_calls_per_pair(self):
        """case_1 (FORWARD→BACKWARD) and case_2 (BACKWARD→FORWARD) both called."""
        plan, sat_a, sat_b = self._setup()
        call_count = []

        def fake_compute(terminals_group_1, terminals_group_2, **_):
            call_count.append(1)
            return fake_compute_returns_first(terminals_group_1, terminals_group_2)

        with patch(
            f"{ADDRESSING_PLANS}.compute_OISL_links_from_terminal_pools",
            side_effect=fake_compute,
        ):
            plan.get_link_associations([sat_a, sat_b])

        assert sum(call_count) == 2

    def test_case_1_receives_forward_backward_pools(self):
        """First pool call must receive FORWARD terminals as group_1, BACKWARD as group_2."""
        plan, sat_a, sat_b = self._setup()
        first_call_args = []

        def fake_compute(terminals_group_1, terminals_group_2, **_):
            if not first_call_args:
                first_call_args.append(
                    (
                        [t.descriptor for t in terminals_group_1],
                        [t.descriptor for t in terminals_group_2],
                    )
                )
            return fake_compute_returns_first(terminals_group_1, terminals_group_2)

        with patch(
            f"{ADDRESSING_PLANS}.compute_OISL_links_from_terminal_pools",
            side_effect=fake_compute,
        ):
            plan.get_link_associations([sat_a, sat_b])

        g1_descs, g2_descs = first_call_args[0]
        assert InterSatelliteLinkOrientation.INTRA_PLANE_FORWARD in g1_descs
        assert InterSatelliteLinkOrientation.INTRA_PLANE_BACKWARD in g2_descs

    def test_case_2_receives_backward_forward_pools(self):
        """Second pool call must receive BACKWARD terminals as group_1, FORWARD as group_2."""
        plan, sat_a, sat_b = self._setup()
        second_call_args = []

        def fake_compute(terminals_group_1, terminals_group_2, **_):
            second_call_args.append(
                (
                    [t.descriptor for t in terminals_group_1],
                    [t.descriptor for t in terminals_group_2],
                )
            )
            return fake_compute_returns_first(terminals_group_1, terminals_group_2)

        with patch(
            f"{ADDRESSING_PLANS}.compute_OISL_links_from_terminal_pools",
            side_effect=fake_compute,
        ):
            plan.get_link_associations([sat_a, sat_b])

        g1_descs, g2_descs = second_call_args[1]
        assert InterSatelliteLinkOrientation.INTRA_PLANE_BACKWARD in g1_descs
        assert InterSatelliteLinkOrientation.INTRA_PLANE_FORWARD in g2_descs

    def test_best_score_candidate_wins_across_cases(self):
        """Candidates from case_1 and case_2 are merged and the lowest score wins."""
        plan, sat_a, sat_b = self._setup()
        t_winner = t_bwd(sat_a)
        t_winner_peer = t_fwd(sat_b)
        call_index = [0]

        def fake_compute(terminals_group_1, terminals_group_2, **_):
            idx = call_index[0]
            call_index[0] += 1
            if idx == 0:
                return [
                    make_possible_link(
                        terminals_group_1[0], terminals_group_2[0], score=10.0
                    )
                ]
            else:
                return [make_possible_link(t_winner, t_winner_peer, score=1.0)]

        with patch(
            f"{ADDRESSING_PLANS}.compute_OISL_links_from_terminal_pools",
            side_effect=fake_compute,
        ):
            result = plan.get_link_associations([sat_a, sat_b])

        assert result[0].terminal_a == t_winner
        assert result[0].terminal_b == t_winner_peer

    def test_link_is_none(self):
        plan, sat_a, sat_b = self._setup()
        with patch(
            f"{ADDRESSING_PLANS}.compute_OISL_links_from_terminal_pools",
            side_effect=fake_compute_returns_first,
        ):
            result = plan.get_link_associations([sat_a, sat_b])
        assert result[0].link is None

    def test_constraints_propagated(self):
        plan, sat_a, sat_b = self._setup()
        expected = make_constraint()
        expected.range_distance_km = 1234.0

        def fake_compute(terminals_group_1, terminals_group_2, **_):
            p = make_possible_link(terminals_group_1[0], terminals_group_2[0])
            p.constraint_a_to_b = expected
            return [p]

        with patch(
            f"{ADDRESSING_PLANS}.compute_OISL_links_from_terminal_pools",
            side_effect=fake_compute,
        ):
            result = plan.get_link_associations([sat_a, sat_b])

        assert result[0].constraint_a_to_b == expected

    def test_no_candidates_emits_warning_and_skips(self):
        plan, sat_a, sat_b = self._setup()
        with patch(
            f"{ADDRESSING_PLANS}.compute_OISL_links_from_terminal_pools",
            return_value=[],
        ), pytest.warns(UserWarning):
            result = plan.get_link_associations([sat_a, sat_b])
        assert result == []

    def test_missing_satellite_emits_warning_and_skips(self):
        plan, sat_a, sat_b = self._setup()
        with pytest.warns(UserWarning), patch(
            f"{ADDRESSING_PLANS}.compute_OISL_links_from_terminal_pools",
            return_value=[],
        ):
            result = plan.get_link_associations([sat_b])  # sat_a (id=0) absent
        assert result == []

    def test_satellite_lookup_uses_object_id_not_topology_id(self):
        shell = make_walker_shell()
        plan = WalkerStaticAddressingPlan(shell)
        plan.grid = [(10, 20, InterSatelliteLinkDirection.ORBITAL)]
        sat_a = make_4_terminal_satellite(object_id=10, topology_id=99, shell=shell)
        sat_b = make_4_terminal_satellite(object_id=20, topology_id=88, shell=shell)

        with patch(
            f"{ADDRESSING_PLANS}.compute_OISL_links_from_terminal_pools",
            side_effect=fake_compute_returns_first,
        ):
            result = plan.get_link_associations([sat_a, sat_b])

        assert len(result) == 1
        assert result[0].satellite_a == sat_a
        assert result[0].satellite_b == sat_b


class TestWalkerBuildAssociationsAdjacent:

    def _setup(self):
        shell = make_walker_shell()
        sat_a = make_4_terminal_satellite(0, 0, shell)
        sat_b = make_4_terminal_satellite(1, 1, shell)
        plan = WalkerStaticAddressingPlan(shell)
        plan.grid = [(0, 1, InterSatelliteLinkDirection.ADJACENT)]
        return plan, sat_a, sat_b

    def test_returns_adjacent_association(self):
        plan, sat_a, sat_b = self._setup()
        with patch(
            f"{ADDRESSING_PLANS}.compute_OISL_links_from_terminal_pools",
            side_effect=fake_compute_returns_first,
        ):
            result = plan.get_link_associations([sat_a, sat_b])
        assert len(result) == 1
        assert result[0].direction == InterSatelliteLinkDirection.ADJACENT

    def test_two_pool_calls_per_pair(self):
        plan, sat_a, sat_b = self._setup()
        call_count = []

        def fake_compute(terminals_group_1, terminals_group_2, **_):
            call_count.append(1)
            return fake_compute_returns_first(terminals_group_1, terminals_group_2)

        with patch(
            f"{ADDRESSING_PLANS}.compute_OISL_links_from_terminal_pools",
            side_effect=fake_compute,
        ):
            plan.get_link_associations([sat_a, sat_b])

        assert sum(call_count) == 2

    def test_case_1_receives_left_right_pools(self):
        plan, sat_a, sat_b = self._setup()
        first_call_args = []

        def fake_compute(terminals_group_1, terminals_group_2, **_):
            if not first_call_args:
                first_call_args.append(
                    (
                        [t.descriptor for t in terminals_group_1],
                        [t.descriptor for t in terminals_group_2],
                    )
                )
            return fake_compute_returns_first(terminals_group_1, terminals_group_2)

        with patch(
            f"{ADDRESSING_PLANS}.compute_OISL_links_from_terminal_pools",
            side_effect=fake_compute,
        ):
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

        def fake_compute(terminals_group_1, terminals_group_2, **_):
            all_call_args.append(
                (
                    [t.descriptor for t in terminals_group_1],
                    [t.descriptor for t in terminals_group_2],
                )
            )
            return fake_compute_returns_first(terminals_group_1, terminals_group_2)

        with patch(
            f"{ADDRESSING_PLANS}.compute_OISL_links_from_terminal_pools",
            side_effect=fake_compute,
        ):
            plan.get_link_associations([sat_a, sat_b])

        g1_descs, g2_descs = all_call_args[1]
        assert InterSatelliteLinkOrientation.INTER_PLANE_LEFT in g1_descs
        assert InterSatelliteLinkOrientation.INTER_PLANE_RIGHT in g2_descs

    def test_no_candidates_emits_warning_and_skips(self):
        plan, sat_a, sat_b = self._setup()
        with patch(
            f"{ADDRESSING_PLANS}.compute_OISL_links_from_terminal_pools",
            return_value=[],
        ), pytest.warns(UserWarning):
            result = plan.get_link_associations([sat_a, sat_b])
        assert result == []


class TestWalkerBookedTerminals:

    def test_booked_terminal_falls_back_to_next_candidate(self):
        """
        Pole-crossing scenario: two pairs compete for the same terminal.
        The second pair must fall back to its next ranked candidate.
        """
        shell = make_walker_shell()
        sat_a = make_4_terminal_satellite(0, 0, shell)
        sat_b = make_4_terminal_satellite(1, 1, shell)
        sat_c = make_4_terminal_satellite(2, 2, shell)

        plan = WalkerStaticAddressingPlan(shell)
        plan.grid = [
            (0, 1, InterSatelliteLinkDirection.ADJACENT),
            (2, 1, InterSatelliteLinkDirection.ADJACENT),
        ]

        contested = t_left(sat_b)
        fallback = t_right(sat_b)
        t_a_right = t_right(sat_a)
        t_c_left = t_left(sat_c)

        call_index = [0]

        def fake_compute(terminals_group_1, terminals_group_2, **_):
            call_index[0] += 1
            if not terminals_group_1 or not terminals_group_2:
                return []
            # First two calls (pair 0,1): return contested as best, fallback as second
            if call_index[0] <= 2:
                results = [
                    make_possible_link(terminals_group_1[0], contested, score=0.0)
                ]
                if fallback in terminals_group_2:
                    results.append(
                        make_possible_link(terminals_group_1[0], fallback, score=5.0)
                    )
                return results
            # Next two calls (pair 2,1): also want contested — must fall back
            return [
                make_possible_link(terminals_group_1[0], contested, score=0.0),
                make_possible_link(terminals_group_1[0], fallback, score=5.0),
            ]

        with patch(
            f"{ADDRESSING_PLANS}.compute_OISL_links_from_terminal_pools",
            side_effect=fake_compute,
        ), pytest.warns(UserWarning):
            result = plan.get_link_associations([sat_a, sat_b, sat_c])

        assert len(result) == 2
        terminal_b_usage = [a.terminal_b for a in result]
        assert terminal_b_usage.count(contested) == 1  # only assigned once

    def test_all_candidates_booked_raises_value_error(self):
        """When every candidate's terminals are booked a ValueError must be raised."""
        shell = make_walker_shell()
        sat_a = make_4_terminal_satellite(0, 0, shell)
        sat_b = make_4_terminal_satellite(1, 1, shell)
        sat_c = make_4_terminal_satellite(2, 2, shell)

        plan = WalkerStaticAddressingPlan(shell)
        plan.grid = [
            (0, 1, InterSatelliteLinkDirection.ORBITAL),
            (2, 1, InterSatelliteLinkDirection.ORBITAL),
        ]

        only_terminal_a = t_fwd(sat_a)
        only_terminal_b = t_bwd(sat_b)

        def fake_compute(terminals_group_1, terminals_group_2, **_):
            # Always offer only the same contested pair — no fallback
            return [make_possible_link(only_terminal_a, only_terminal_b, score=0.0)]

        with patch(
            f"{ADDRESSING_PLANS}.compute_OISL_links_from_terminal_pools",
            side_effect=fake_compute,
        ):
            with pytest.raises(ValueError):
                plan.get_link_associations([sat_a, sat_b, sat_c])

    def test_booked_terminals_emits_warning(self):
        """Falling back to the next candidate must emit a UserWarning."""
        shell = make_walker_shell()
        sat_a = make_4_terminal_satellite(0, 0, shell)
        sat_b = make_4_terminal_satellite(1, 1, shell)
        sat_c = make_4_terminal_satellite(2, 2, shell)

        plan = WalkerStaticAddressingPlan(shell)
        plan.grid = [
            (0, 1, InterSatelliteLinkDirection.ORBITAL),
            (2, 1, InterSatelliteLinkDirection.ORBITAL),
        ]

        contested = t_bwd(sat_b)
        fallback = t_fwd(sat_b)

        def fake_compute(terminals_group_1, terminals_group_2, **_):
            return [
                make_possible_link(terminals_group_1[0], contested, score=0.0),
                make_possible_link(terminals_group_1[0], fallback, score=5.0),
            ]

        with pytest.warns(UserWarning):
            with patch(
                f"{ADDRESSING_PLANS}.compute_OISL_links_from_terminal_pools",
                side_effect=fake_compute,
            ):
                plan.get_link_associations([sat_a, sat_b, sat_c])


class TestWalkerUnknownDirection:

    def test_undefined_direction_raises_value_error(self):
        shell = make_walker_shell()
        sat_a = make_4_terminal_satellite(0, 0, shell)
        sat_b = make_4_terminal_satellite(1, 1, shell)
        plan = WalkerStaticAddressingPlan(shell)
        plan.grid = [(0, 1, InterSatelliteLinkDirection.UNDEFINED)]

        with pytest.raises(ValueError):
            plan.get_link_associations([sat_a, sat_b])


# ===========================================================================
# SSODawnDuskStaticAddressingPlan
# ===========================================================================


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
        plan = SSODawnDuskStaticAddressingPlan(shell)
        plan.grid = [(0, 1, InterSatelliteLinkDirection.ORBITAL)]
        satellites = [make_4_terminal_satellite(i, i, shell) for i in range(n)]
        return plan, satellites

    def test_returns_orbital_association(self):
        plan, satellites = self._setup()
        with patch(
            f"{ADDRESSING_PLANS}.compute_OISL_links_from_terminal_pools",
            side_effect=fake_compute_returns_first,
        ):
            result = plan.get_link_associations(satellites)
        assert len(result) == 1
        assert result[0].direction == InterSatelliteLinkDirection.ORBITAL

    def test_two_pool_calls_per_pair(self):
        plan, satellites = self._setup()
        call_count = []

        def fake_compute(terminals_group_1, terminals_group_2, **_):
            call_count.append(1)
            return fake_compute_returns_first(terminals_group_1, terminals_group_2)

        with patch(
            f"{ADDRESSING_PLANS}.compute_OISL_links_from_terminal_pools",
            side_effect=fake_compute,
        ):
            plan.get_link_associations(satellites)

        assert sum(call_count) == 2

    def test_only_intra_plane_terminals_passed_to_pool(self):
        plan, satellites = self._setup()
        all_group_descriptors = []

        def fake_compute(terminals_group_1, terminals_group_2, **_):
            all_group_descriptors.extend(
                [t.descriptor for t in terminals_group_1 + terminals_group_2]
            )
            return fake_compute_returns_first(terminals_group_1, terminals_group_2)

        with patch(
            f"{ADDRESSING_PLANS}.compute_OISL_links_from_terminal_pools",
            side_effect=fake_compute,
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
            side_effect=fake_compute_returns_first,
        ):
            result = plan.get_link_associations(satellites)
        assert result[0].link is None

    def test_constraints_propagated(self):
        plan, satellites = self._setup()
        expected = make_constraint()
        expected.range_distance_km = 999.0

        def fake_compute(terminals_group_1, terminals_group_2, **_):
            p = make_possible_link(terminals_group_1[0], terminals_group_2[0])
            p.constraint_a_to_b = expected
            return [p]

        with patch(
            f"{ADDRESSING_PLANS}.compute_OISL_links_from_terminal_pools",
            side_effect=fake_compute,
        ):
            result = plan.get_link_associations(satellites)

        assert result[0].constraint_a_to_b == expected

    def test_satellite_lookup_uses_object_id(self):
        shell = make_sso_shell()
        plan = SSODawnDuskStaticAddressingPlan(shell)
        plan.grid = [(10, 20, InterSatelliteLinkDirection.ORBITAL)]
        sat_a = make_4_terminal_satellite(object_id=10, topology_id=99, shell=shell)
        sat_b = make_4_terminal_satellite(object_id=20, topology_id=88, shell=shell)

        with patch(
            f"{ADDRESSING_PLANS}.compute_OISL_links_from_terminal_pools",
            side_effect=fake_compute_returns_first,
        ):
            result = plan.get_link_associations([sat_a, sat_b])

        assert len(result) == 1
        assert result[0].satellite_a == sat_a
        assert result[0].satellite_b == sat_b

    def test_all_candidates_booked_raises_value_error(self):
        shell = make_sso_shell()
        plan = SSODawnDuskStaticAddressingPlan(shell)
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
            with pytest.raises(ValueError):
                plan.get_link_associations([sat_a, sat_b])

    def test_booked_fallback_emits_warning(self):
        shell = make_sso_shell()
        plan = SSODawnDuskStaticAddressingPlan(shell)
        sat_a = make_4_terminal_satellite(0, 0, shell)
        sat_b = make_4_terminal_satellite(1, 1, shell)
        sat_c = make_4_terminal_satellite(2, 2, shell)
        plan.grid = [
            (0, 1, InterSatelliteLinkDirection.ORBITAL),
            (2, 1, InterSatelliteLinkDirection.ORBITAL),
        ]

        contested = t_bwd(sat_b)
        fallback = t_fwd(sat_b)

        def fake_compute(terminals_group_1, terminals_group_2, **_):
            return [
                make_possible_link(terminals_group_1[0], contested, score=0.0),
                make_possible_link(terminals_group_1[0], fallback, score=5.0),
            ]

        with pytest.warns(UserWarning), patch(
            f"{ADDRESSING_PLANS}.compute_OISL_links_from_terminal_pools",
            side_effect=fake_compute,
        ):
            plan.get_link_associations([sat_a, sat_b, sat_c])
