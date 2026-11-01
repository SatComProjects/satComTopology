from unittest.mock import patch, MagicMock

from sat_com_connectivity.ground_object_to_space_connectivity.strategies import (
    ConnectToTheBestAngleStrategy,
)
from sat_com_model.models import GroundToSpaceLink
from tests.sat_com_connectivity_tests.utils import (
    make_fake_satellite,
    make_fake_ground_object,
)


@patch(
    "sat_com_connectivity.ground_object_to_space_connectivity.strategies.get_visible_satellites"
)
@patch(
    "sat_com_connectivity.ground_object_to_space_connectivity.strategies.estimate_time_until_disconnection"
)
def test_connect_to_the_best_angle_strategy(
    mock_estimate_time_until_disconnection, mock_get_visible_satellites
):
    # Setup strategy and fake objects
    strategy = ConnectToTheBestAngleStrategy(distance_model=MagicMock())

    strategy.distance_model.get_3d_distance_meters.return_value = 800_000

    ground_object = make_fake_ground_object()

    satellite_1 = make_fake_satellite()
    satellite_1.topology_uniq_id = 101

    satellite_2 = make_fake_satellite()
    satellite_2.topology_uniq_id = 102

    satellite_3 = make_fake_satellite()
    satellite_3.topology_uniq_id = 103

    mock_estimate_time_until_disconnection.return_value = 300

    # Add existing link that should be removed
    old_link = GroundToSpaceLink(source=ground_object, destination=satellite_1)
    ground_object.links = [old_link]

    # Only satellite_2 and satellite_3 are visible
    mock_get_visible_satellites.return_value = [
        # Mocked visible satellite objects have `.satellite` and `.elevation`
        type(
            "VisibleSatellite",
            (),
            {
                "satellite": satellite_2,
                "elevation_above_horizon": 45.0,
                "distance_km": 1_000.0,
            },
        ),
        type(
            "VisibleSatellite",
            (),
            {
                "satellite": satellite_3,
                "elevation_above_horizon": 60.0,
                "distance_km": 1_000.0,
            },
        ),
    ]

    result = strategy.compute_ground_object_connection_strategy(
        ground_object, [satellite_1, satellite_2, satellite_3]
    )

    # Assert old links are marked obsolete
    assert len(result.obsolete_links) == 1
    assert result.obsolete_links[0] == old_link

    # Assert new links are created only for best visible satellites
    added_connections = result.new_ground_object_connections
    assert len(added_connections) == 1

    sats_in_added = {conn.satellite.topology_uniq_id for conn in added_connections}
    assert sats_in_added == {103}

    # Check elevation is correctly passed
    for conn in added_connections:
        if conn.satellite.topology_uniq_id == 103:
            assert (
                conn.ground_to_space_constraints.elevation_angle_above_horizon == 60.0
            )


@patch(
    "sat_com_connectivity.ground_object_to_space_connectivity.strategies.get_visible_satellites"
)
@patch(
    "sat_com_connectivity.ground_object_to_space_connectivity.strategies.estimate_time_until_disconnection"
)
def test_that_new_satellite_is_picked_even_if_the_former_one_is_still_visible(
    mock_estimate_time_until_disconnection,
    mock_get_visible_satellites,
):
    strategy = ConnectToTheBestAngleStrategy(distance_model=MagicMock())

    ground_object = make_fake_ground_object()

    sat_old = make_fake_satellite()
    sat_old.topology_uniq_id = 1

    sat_new1 = make_fake_satellite()
    sat_new1.topology_uniq_id = 2

    sat_new2 = make_fake_satellite()
    sat_new2.topology_uniq_id = 3

    link = GroundToSpaceLink(source=ground_object, destination=sat_old)
    ground_object.links = [link]

    mock_estimate_time_until_disconnection.return_value = 300
    strategy.distance_model.get_3d_distance_meters.return_value = 800_000

    mock_get_visible_satellites.return_value = [
        type(
            "VisibleSatellite",
            (),
            {
                "satellite": sat_old,
                "elevation_above_horizon": 40,
                "distance_km": 1_000.0,
            },
        ),  # Worst angle
        type(
            "VisibleSatellite",
            (),
            {
                "satellite": sat_new1,
                "elevation_above_horizon": 30,
                "distance_km": 1_000.0,
            },
        ),
        type(
            "VisibleSatellite",
            (),
            {
                "satellite": sat_new2,
                "elevation_above_horizon": 50,
                "distance_km": 1_000.0,
            },
        ),  # Best one
    ]

    result = strategy.compute_ground_object_connection_strategy(
        ground_object, [sat_old, sat_new1, sat_new2]
    )

    assert result.obsolete_links == [link]
    assert len(result.new_ground_object_connections) == 1
    conn = result.new_ground_object_connections[0]
    assert conn.satellite == sat_new2
    assert conn.ground_to_space_constraints.elevation_angle_above_horizon == 50


@patch(
    "sat_com_connectivity.ground_object_to_space_connectivity.strategies.get_visible_satellites"
)
@patch(
    "sat_com_connectivity.ground_object_to_space_connectivity.strategies.estimate_time_until_disconnection"
)
def test_that_old_satellite_is_picked_even_if_the_former_one_is_still_visible_and_still_has_the_best_angle(
    mock_estimate_time_until_disconnection,
    mock_get_visible_satellites,
):
    strategy = ConnectToTheBestAngleStrategy(distance_model=MagicMock())

    ground_object = make_fake_ground_object()

    sat_old = make_fake_satellite()
    sat_old.topology_uniq_id = 1

    sat_new1 = make_fake_satellite()
    sat_new1.topology_uniq_id = 2

    sat_new2 = make_fake_satellite()
    sat_new2.topology_uniq_id = 3

    link = GroundToSpaceLink(source=ground_object, destination=sat_old)
    ground_object.links = [link]

    mock_estimate_time_until_disconnection.return_value = 300

    strategy.distance_model.get_3d_distance_meters.return_value = 800_000

    mock_get_visible_satellites.return_value = [
        type(
            "VisibleSatellite",
            (),
            {
                "satellite": sat_old,
                "elevation_above_horizon": 60,
                "distance_km": 1_000.0,
            },
        ),  # Worst angle
        type(
            "VisibleSatellite",
            (),
            {
                "satellite": sat_new1,
                "elevation_above_horizon": 30,
                "distance_km": 1_000.0,
            },
        ),
        type(
            "VisibleSatellite",
            (),
            {
                "satellite": sat_new2,
                "elevation_above_horizon": 50,
                "distance_km": 1_000.0,
            },
        ),  # Best one
    ]

    result = strategy.compute_ground_object_connection_strategy(
        ground_object, [sat_old, sat_new1, sat_new2]
    )

    assert result.obsolete_links == [link]
    assert len(result.new_ground_object_connections) == 1
    conn = result.new_ground_object_connections[0]
    assert conn.satellite == sat_old
    assert conn.ground_to_space_constraints.elevation_angle_above_horizon == 60
