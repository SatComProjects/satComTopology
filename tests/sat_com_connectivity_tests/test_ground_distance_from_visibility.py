"""
The ground-to-satellite distance is a by-product of the elevation computation:
both come from the same ground-to-satellite vector. These tests check that the
strategies reuse it instead of computing a distance a second time, and that the
distance-only (range) strategies are flagged as deprecated.
"""

import warnings
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from sat_com_connectivity.ground_object_to_space_connectivity.ground_connection_strategy_registry import (
    GROUND_TO_SPACE_CONNECTION_STRATEGY_REGISTRY,
)
from sat_com_connectivity.ground_object_to_space_connectivity.visibility_angle_utils import (
    VisibleSatellite,
)
from sat_com_connectivity.utils import (
    compute_elevations,
    compute_elevations_and_distances,
    get_elevation_angle,
    get_elevation_angle_and_distance,
    ground_to_up_vector,
    latitude_longitude_altitude_to_x_y_z,
)
from tests.sat_com_connectivity_tests.utils import (
    make_fake_ground_object,
    make_fake_satellite_with_low_shell,
)

STRATEGIES = "sat_com_connectivity.ground_object_to_space_connectivity.strategies"

VISIBILITY_STRATEGIES = [
    "best-angle-until-disconnection-ordered",
    "best-angle-until-disconnection",
    "everything-visible",
    "best-angle-ordered",
    "best-angle",
    "best-angle-until-disconnection-prefer-bigger-shell",
    "best-angle-until-disconnection-prefer-lower-shell",
]

DEPRECATED_RANGE_STRATEGIES = [
    "everything-in-range",
    "best-range-until-disconnection-ordered",
    "best-range-until-disconnection",
]

SATELLITE = (55.0, 10.0, 550_000.0)  # lat, lon, alt [m]
GROUND = (48.0, 2.0, 0.0)


# ---------------------------------------------------------------------------
# Geometry: one vector, two results
# ---------------------------------------------------------------------------


def test_scalar_elevation_and_distance_come_from_the_same_vector():
    elevation, distance_m = get_elevation_angle_and_distance(SATELLITE, GROUND)

    expected_distance_m = np.linalg.norm(
        np.array(latitude_longitude_altitude_to_x_y_z(*SATELLITE))
        - np.array(latitude_longitude_altitude_to_x_y_z(*GROUND))
    )
    assert elevation == get_elevation_angle(SATELLITE, GROUND)
    assert distance_m == expected_distance_m


def test_vectorised_elevations_and_distances_match_scalar_path():
    satellites = [SATELLITE, (40.0, 5.0, 560_000.0), (60.0, -3.0, 540_000.0)]
    sat_ecef = np.array([latitude_longitude_altitude_to_x_y_z(*s) for s in satellites])
    gnd_ecef = np.array(latitude_longitude_altitude_to_x_y_z(*GROUND))
    up = ground_to_up_vector(GROUND)

    elevations, distances_m = compute_elevations_and_distances(sat_ecef, gnd_ecef, up)

    np.testing.assert_array_equal(
        elevations, compute_elevations(sat_ecef, gnd_ecef, up)
    )
    for satellite, elevation, distance_m in zip(satellites, elevations, distances_m):
        scalar_elevation, scalar_distance_m = get_elevation_angle_and_distance(
            satellite, GROUND
        )
        assert elevation == pytest.approx(scalar_elevation, abs=1e-9)
        assert distance_m == pytest.approx(scalar_distance_m, rel=1e-12)


# ---------------------------------------------------------------------------
# Strategies reuse the visibility distance
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("strategy_name", VISIBILITY_STRATEGIES)
def test_new_connection_uses_the_visibility_distance(strategy_name):
    strategy = GROUND_TO_SPACE_CONNECTION_STRATEGY_REGISTRY[strategy_name]()
    ground_object = make_fake_ground_object()
    satellite = make_fake_satellite_with_low_shell()
    visible = VisibleSatellite(
        satellite=satellite, elevation_above_horizon=45.0, distance_km=987.6
    )

    with patch(f"{STRATEGIES}.get_visible_satellites", return_value=[visible]):
        result = strategy.compute_ground_object_connection_strategy(
            ground_object, [satellite]
        )

    assert len(result.new_ground_object_connections) == 1
    constraints = result.new_ground_object_connections[0].ground_to_space_constraints
    assert constraints.distance_km == 987.6
    assert constraints.elevation_angle_above_horizon == 45.0


@pytest.mark.parametrize("strategy_name", VISIBILITY_STRATEGIES)
def test_visibility_strategies_never_use_the_distance_model(strategy_name):
    distance_model = MagicMock()
    strategy = GROUND_TO_SPACE_CONNECTION_STRATEGY_REGISTRY[strategy_name](
        distance_model=distance_model
    )
    satellite = make_fake_satellite_with_low_shell()
    visible = VisibleSatellite(
        satellite=satellite, elevation_above_horizon=45.0, distance_km=987.6
    )

    with patch(f"{STRATEGIES}.get_visible_satellites", return_value=[visible]):
        strategy.compute_ground_object_connection_strategy(
            make_fake_ground_object(), [satellite]
        )

    assert distance_model.method_calls == []


# ---------------------------------------------------------------------------
# Deprecation of the distance-only strategies
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("strategy_name", DEPRECATED_RANGE_STRATEGIES)
def test_range_strategies_warn_once(strategy_name):
    strategy_cls = GROUND_TO_SPACE_CONNECTION_STRATEGY_REGISTRY[strategy_name]
    assert strategy_cls.description.startswith("[DEPRECATED]")

    strategy = strategy_cls(distance_model=MagicMock())
    strategy.distance_model.spatial_position_on_ground_in_range.return_value = []

    with pytest.warns(FutureWarning, match=strategy_name):
        strategy.compute_ground_object_connection_strategy(
            make_fake_ground_object(), []
        )
    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        strategy.compute_ground_object_connection_strategy(
            make_fake_ground_object(), []
        )


@pytest.mark.parametrize("strategy_name", VISIBILITY_STRATEGIES)
def test_visibility_strategies_are_not_deprecated(strategy_name):
    strategy_cls = GROUND_TO_SPACE_CONNECTION_STRATEGY_REGISTRY[strategy_name]
    assert strategy_cls.deprecation_message is None
    assert not strategy_cls.description.startswith("[DEPRECATED]")


# ---------------------------------------------------------------------------
# The simulation stores the distance from the first tick of a link
# ---------------------------------------------------------------------------


def test_new_ground_links_store_their_distance_at_creation():
    from sat_com_application.simulation_manager import SimulationManager
    from sat_com_model.models import GroundStation, Simulation

    manager = SimulationManager(simulation=Simulation())
    satellite = make_fake_satellite_with_low_shell()
    satellite.topology_uniq_id = 10
    ground_station = GroundStation(topology_uniq_id=11, object_id=1, label="GS")

    link = manager.create_and_add_ground_station_link_connection(
        satellite=satellite,
        ground_station=ground_station,
        elevation_above_horizon_angle=30.0,
        distance_km=1_234.5,
    )

    assert link.distance_km == 1_234.5
