"""
Tests for the simulation-wide satellite state cache (satellite_state_cache.py).

The cache is shared by every ground object, every shell addressing plan and
every phase of the inter-satellite strategies, so the things that matter are:
  - entries are dropped as soon as the simulation time moves,
  - a cache is only ever used with its own finite-difference dt,
  - shared arrays cannot be modified in place,
  - every consumer of a simulation really gets the same instance.
"""

import datetime
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from sat_com_connectivity.ground_object_to_space_connectivity.visibility_angle_utils import (
    get_visible_satellites,
)
from sat_com_connectivity.inter_satellite_link_connectivity.optical_helpers import (
    compute_OISL_feasibility_for_terminal_pair,
    compute_OISL_links_from_terminal_pools,
)
from sat_com_connectivity.inter_satellite_link_connectivity.strategies import (
    InterShellSSOPriorityConnectivity,
)
from sat_com_connectivity.satellite_state_cache import (
    EciCache,
    SatelliteStateCache,
)
from sat_com_model.models import OpticalLinkTerminal, Satellite, SpatialPosition
from sat_com_connectivity.utils import satellites_to_ecef

STRATEGIES = "sat_com_connectivity.inter_satellite_link_connectivity.strategies"

T0 = datetime.datetime(2026, 1, 1, 0, 0, 0)


class FakeClock:
    def __init__(self, now=T0):
        self.now = now


class FakeMovementModel:
    """Straight-line motion driven by a shared clock, counting every query."""

    def __init__(self, clock, position_km, velocity_km_s, lat_lon_alt):
        self.clock = clock
        self.position_km = np.array(position_km, dtype=float)
        self.velocity_km_s = np.array(velocity_km_s, dtype=float)
        self.lat_lon_alt = lat_lon_alt
        self.eci_calls = 0
        self.geodetic_calls = 0

    def _elapsed(self):
        return (self.clock.now - T0).total_seconds()

    def get_datetime(self):
        return self.clock.now

    def get_position_earth_general_inertial(self, delta_t=0.0):
        self.eci_calls += 1
        return self.position_km + self.velocity_km_s * self._elapsed()

    def get_velocity_earth_general_inertial(self, delta_t=0.0):
        return self.velocity_km_s

    def get_longitude_latitude_altitude(self, delta_t=0.0):
        self.geodetic_calls += 1
        lat, lon, alt = self.lat_lon_alt
        return SpatialPosition(
            latitude=lat, longitude=lon + 0.1 * self._elapsed(), altitude=alt
        )


def make_satellite(topology_id, movement_model):
    sat = MagicMock(spec=Satellite)
    sat.topology_uniq_id = topology_id
    sat.get_movement_model.return_value = movement_model
    sat.get_coordinates.side_effect = movement_model.get_longitude_latitude_altitude
    return sat


def make_terminal(host_satellite):
    terminal = MagicMock(spec=OpticalLinkTerminal)
    terminal.host_satellite = host_satellite
    terminal.azimuth_angle_configuration = 0.0
    terminal.elevation_angle_configuration = -180.0
    cfg = MagicMock()
    cfg.min_elevation_degrees = -90.0
    cfg.max_elevation_degrees = 90.0
    cfg.max_azimuth_degrees = 180.0
    cfg.maximum_range_distance_km = 1_000_000.0
    cfg.maximum_angular_velocity_degree_per_second = 1_000.0
    cfg.minimum_contact_duration_seconds = 0
    terminal.terminal_configuration = cfg
    return terminal


def make_pair(clock):
    mm_a = FakeMovementModel(
        clock, (7000.0, 0.0, 0.0), (0.0, 7.5, 0.2), (10.0, 20.0, 550_000.0)
    )
    mm_b = FakeMovementModel(
        clock, (6500.0, 2000.0, 300.0), (-1.0, 7.0, -0.3), (12.0, 25.0, 550_000.0)
    )
    return make_satellite(1, mm_a), make_satellite(2, mm_b)


def make_ground_object(lat, lon, min_elevation=0.0):
    ground_object = MagicMock()
    ground_object.get_coordinates.return_value = SpatialPosition(
        latitude=lat, longitude=lon, altitude=0.0
    )
    ground_object.ground_object_domain.elevation_above_horizon = min_elevation
    return ground_object


# ---------------------------------------------------------------------------
# EciCache
# ---------------------------------------------------------------------------


class TestEciCache:

    def test_satellite_propagated_once_per_time_step(self):
        clock = FakeClock()
        sat_a, _ = make_pair(clock)
        cache = EciCache(dt=1.0)

        cache.get(sat_a)
        cache.get_dt(sat_a)
        cache.get_lvlh_frames(sat_a)
        cache.get_lvlh_frames_dt(sat_a)
        cache.warm([sat_a])

        assert sat_a.get_movement_model().eci_calls == 1

    def test_time_change_drops_every_entry(self):
        clock = FakeClock()
        sat_a, _ = make_pair(clock)
        cache = EciCache(dt=1.0)

        position_t0, _ = cache.get(sat_a)
        clock.now = T0 + datetime.timedelta(seconds=10)
        position_t10, _ = cache.get(sat_a)

        assert sat_a.get_movement_model().eci_calls == 2
        assert not np.array_equal(position_t0, position_t10)
        assert len(cache) == 1

    def test_dt_state_is_linear_propagation(self):
        clock = FakeClock()
        sat_a, _ = make_pair(clock)
        cache = EciCache(dt=2.0)

        position, velocity = cache.get(sat_a)
        position_dt, velocity_dt = cache.get_dt(sat_a)

        np.testing.assert_array_equal(position_dt, position + velocity * 2.0)
        np.testing.assert_array_equal(velocity_dt, velocity)

    def test_warm_keeps_frames_already_computed(self):
        clock = FakeClock()
        sat_a, sat_b = make_pair(clock)
        cache = EciCache(dt=1.0)

        frame_a = cache.get_lvlh_frames(sat_a)
        cache.warm([sat_a, sat_b])

        assert cache.get_lvlh_frames(sat_a) is frame_a
        assert len(cache) == 2

    def test_cached_arrays_are_read_only(self):
        clock = FakeClock()
        sat_a, _ = make_pair(clock)
        cache = EciCache(dt=1.0)
        cache.warm([sat_a])

        arrays = [
            *cache.get(sat_a),
            *cache.get_dt(sat_a),
            cache.get_lvlh_frames(sat_a),
            cache.get_lvlh_frames_dt(sat_a),
        ]
        for array in arrays:
            with pytest.raises(ValueError):
                array[0] = 0.0

    def test_invalidate_drops_entries_even_if_time_did_not_move(self):
        clock = FakeClock()
        sat_a, _ = make_pair(clock)
        cache = EciCache(dt=1.0)

        cache.get(sat_a)
        cache.invalidate()
        cache.get(sat_a)

        assert sat_a.get_movement_model().eci_calls == 2


# ---------------------------------------------------------------------------
# Using a cache from the OISL helpers
# ---------------------------------------------------------------------------


class TestOpticalHelpersUseTheGivenCache:

    def test_empty_cache_is_used_not_replaced(self):
        """An empty EciCache has len() == 0: it must not be treated as missing."""
        clock = FakeClock()
        sat_a, sat_b = make_pair(clock)
        cache = EciCache(dt=1.0)
        assert len(cache) == 0

        compute_OISL_feasibility_for_terminal_pair(
            satellite_a=sat_a,
            terminal_a=make_terminal(sat_a),
            satellite_b=sat_b,
            terminal_b=make_terminal(sat_b),
            angular_velocity_dt_seconds=1.0,
            _cache=cache,
        )

        assert len(cache) == 2

    def test_cache_with_other_dt_is_refused(self):
        clock = FakeClock()
        sat_a, sat_b = make_pair(clock)

        with pytest.raises(ValueError, match="dt"):
            compute_OISL_feasibility_for_terminal_pair(
                satellite_a=sat_a,
                terminal_a=make_terminal(sat_a),
                satellite_b=sat_b,
                terminal_b=make_terminal(sat_b),
                angular_velocity_dt_seconds=1.0,
                _cache=EciCache(dt=0.0),
            )

        with pytest.raises(ValueError, match="dt"):
            compute_OISL_links_from_terminal_pools(
                terminals_group_1=[make_terminal(sat_a)],
                terminals_group_2=[make_terminal(sat_b)],
                angular_velocity_dt_seconds=1.0,
                cache=EciCache(dt=5.0),
            )

    def test_shared_cache_gives_same_result_as_private_cache(self):
        clock = FakeClock()
        sat_a, sat_b = make_pair(clock)
        term_a, term_b = make_terminal(sat_a), make_terminal(sat_b)

        private = compute_OISL_feasibility_for_terminal_pair(
            sat_a, term_a, sat_b, term_b, angular_velocity_dt_seconds=1.0
        )
        shared_cache = SatelliteStateCache().eci(1.0)
        shared_cache.warm([sat_a, sat_b])
        shared = compute_OISL_feasibility_for_terminal_pair(
            sat_a, term_a, sat_b, term_b, 1.0, _cache=shared_cache
        )

        assert private.constraint_a_to_b == shared.constraint_a_to_b
        assert private.constraint_b_to_a == shared.constraint_b_to_a
        assert private.constraint_a_to_b.angular_velocity_rate_degree_per_second != 0


# ---------------------------------------------------------------------------
# SatelliteStateCache
# ---------------------------------------------------------------------------


class TestSatelliteStateCache:

    def test_one_eci_cache_per_dt(self):
        state_cache = SatelliteStateCache()

        assert state_cache.eci(1.0) is state_cache.eci(1)
        assert state_cache.eci(1.0) is not state_cache.eci(2.0)
        assert state_cache.eci(2.0).dt == 2.0

    def test_ground_ecef_matches_direct_computation(self):
        clock = FakeClock()
        satellites = list(make_pair(clock))

        cached = SatelliteStateCache().ground_ecef(satellites)

        np.testing.assert_array_equal(cached, satellites_to_ecef(satellites))
        with pytest.raises(ValueError):
            cached[0, 0] = 0.0

    def test_ground_ecef_computed_once_for_every_ground_object(self):
        clock = FakeClock()
        satellites = list(make_pair(clock))
        state_cache = SatelliteStateCache()

        for lat in range(-60, 61, 10):
            get_visible_satellites(
                satellites, make_ground_object(lat, 21.0), state_cache=state_cache
            )

        for sat in satellites:
            assert sat.get_movement_model().geodetic_calls == 1

    def test_ground_visibility_identical_with_and_without_cache(self):
        clock = FakeClock()
        satellites = list(make_pair(clock))
        ground_object = make_ground_object(11.0, 22.0, min_elevation=10.0)

        expected = get_visible_satellites(satellites, ground_object)
        actual = get_visible_satellites(
            satellites, ground_object, state_cache=SatelliteStateCache()
        )

        assert expected
        assert [(v.satellite, v.elevation_above_horizon) for v in actual] == [
            (v.satellite, v.elevation_above_horizon) for v in expected
        ]

    def test_ground_ecef_recomputed_when_time_moves(self):
        clock = FakeClock()
        satellites = list(make_pair(clock))
        state_cache = SatelliteStateCache()

        before = state_cache.ground_ecef(satellites)
        clock.now = T0 + datetime.timedelta(seconds=30)
        after = state_cache.ground_ecef(satellites)

        assert not np.array_equal(before, after)
        np.testing.assert_array_equal(after, satellites_to_ecef(satellites))

    def test_invalidate_drops_eci_and_ground_entries(self):
        clock = FakeClock()
        satellites = list(make_pair(clock))
        state_cache = SatelliteStateCache()
        state_cache.eci(1.0).warm(satellites)
        state_cache.ground_ecef(satellites)

        state_cache.invalidate()
        state_cache.eci(1.0).get(satellites[0])
        state_cache.ground_ecef(satellites)

        assert satellites[0].get_movement_model().eci_calls == 2
        assert satellites[0].get_movement_model().geodetic_calls == 2


# ---------------------------------------------------------------------------
# One cache for the whole inter-satellite strategy
# ---------------------------------------------------------------------------


class TestInterSatelliteStrategySharesOneCache:

    def test_every_phase_and_plan_gets_the_same_cache(self):
        state_cache = SatelliteStateCache()
        plan_a = MagicMock()
        plan_a.get_link_associations.return_value = []
        plan_b = MagicMock()
        plan_b.get_link_associations.return_value = []
        shell_a, shell_b = MagicMock(), MagicMock()

        # One SSO terminal and one Walker terminal so phase 1 reaches the pool.
        from sat_com_model.models import DawnDuskSSOShell, WalkerShell
        from sat_com_model.models import InterSatelliteLinkOrientation

        sats = []
        for topology_id, shell_cls in ((1, DawnDuskSSOShell), (2, WalkerShell)):
            sat = MagicMock(spec=Satellite)
            sat.topology_uniq_id = topology_id
            sat.shell = MagicMock(spec=shell_cls)
            terminal = MagicMock(spec=OpticalLinkTerminal)
            terminal.link = None
            terminal.host_satellite = sat
            terminal.orientation_possibilities = [
                InterSatelliteLinkOrientation.INTER_SHELL_FORWARD
            ]
            sat.optical_link_terminals = [terminal]
            sats.append(sat)

        strategy = InterShellSSOPriorityConnectivity(
            satellites=sats,
            shell_and_plans=[(shell_a, plan_a), (shell_b, plan_b)],
            state_cache=state_cache,
        )

        with patch(
            f"{STRATEGIES}.compute_OISL_links_from_terminal_pools_filtered",
            return_value=[],
        ) as pool:
            strategy.compute_strategy()

        assert pool.call_args.kwargs["cache"] is state_cache.eci(1.0)
        for plan in (plan_a, plan_b):
            assert plan.get_link_associations.call_args.kwargs["state_cache"] is (
                state_cache
            )

    def test_without_injected_cache_both_phases_still_share_one(self):
        plan = MagicMock()
        plan.get_link_associations.return_value = []
        strategy = InterShellSSOPriorityConnectivity(
            satellites=[], shell_and_plans=[(MagicMock(), plan)]
        )

        strategy.compute_strategy()

        used = plan.get_link_associations.call_args.kwargs["state_cache"]
        assert isinstance(used, SatelliteStateCache)


# ---------------------------------------------------------------------------
# One cache for the whole simulation
# ---------------------------------------------------------------------------


def test_simulation_shares_one_cache_between_ground_and_isl():
    from sat_com_builder.configuration_manager import BaseConfigurationManager
    from tests.sat_com_topology_tests.test_multiple_satellite_configuration import (
        make_basic_4_isl_satellite_installation_intershell_authorized_on_adjacent,
        make_small_single_walker_shell,
    )

    simulation_property = make_small_single_walker_shell(
        make_basic_4_isl_satellite_installation_intershell_authorized_on_adjacent()
    )
    simulation_manager = BaseConfigurationManager(
        simulation_property=simulation_property
    ).load_simulation()

    shared = simulation_manager.satellite_state_cache
    assert isinstance(shared, SatelliteStateCache)
    assert simulation_manager.inter_satellite_link_connection_strategy.state_cache is (
        shared
    )
    for strategy in simulation_manager.ground_to_space_connection_strategies.values():
        assert strategy.state_cache is shared

    links_before = len(simulation_manager.get_inter_satellites_links())
    simulation_manager.time_manager.tick(seconds=30)
    assert len(simulation_manager.get_inter_satellites_links()) == links_before
