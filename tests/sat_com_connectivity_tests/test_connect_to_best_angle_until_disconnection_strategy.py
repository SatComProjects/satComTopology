from unittest.mock import MagicMock, patch

import pytest

from sat_com_connectivity.ground_object_to_space_connectivity.strategies import (
    ConnectToBestRangeUntilDisconnectionStrategy,
    ConnectToBestAngleUntilDisconnectionStrategy,
)
from sat_com_model.models import (
    GroundToSpaceLink,
)
from tests.sat_com_connectivity_tests.utils import (
    make_fake_ground_object,
    make_fake_satellite,
)


@pytest.fixture
def strategy():
    mock_distance_model = MagicMock()
    return ConnectToBestRangeUntilDisconnectionStrategy(
        distance_model=mock_distance_model
    )


@patch(
    "sat_com_connectivity.ground_object_to_space_connectivity.visibility_angle_utils.get_elevation_angle"
)
def test_keep_existing_link(mock_get_elevation_angle_visibility_angle):
    strategy = ConnectToBestAngleUntilDisconnectionStrategy()
    ground_object = make_fake_ground_object()
    satellite = make_fake_satellite()

    link = GroundToSpaceLink(source=ground_object, destination=satellite)
    ground_object.links = [link]

    mock_get_elevation_angle_visibility_angle.return_value = 30  # Above threshold

    result = strategy.compute_ground_object_connection_strategy(
        ground_object, [satellite]
    )

    assert result.obsolete_links == []
    assert result.new_ground_object_connections == []  # No need to create new
    assert link.elevation_above_horizon_angle == 30


@patch(
    "sat_com_connectivity.ground_object_to_space_connectivity.visibility_angle_utils.get_visible_satellites"
)
@patch(
    "sat_com_connectivity.ground_object_to_space_connectivity.visibility_angle_utils.get_elevation_angle"
)
def test_obsolete_link_then_pick_best(
    mock_get_elevation_angle, mock_get_visible_satellites
):
    strategy = ConnectToBestAngleUntilDisconnectionStrategy()
    ground_object = make_fake_ground_object()
    sat_old = make_fake_satellite()
    sat_new1 = make_fake_satellite()
    sat_new2 = make_fake_satellite()

    sat_new1.satellite_name = "New1"
    sat_new2.satellite_name = "New2"

    link = GroundToSpaceLink(source=ground_object, destination=sat_old)
    ground_object.links = [link]

    # Old link is invalid (elevation too low)
    mock_get_elevation_angle.return_value = 10

    mock_get_visible_satellites.return_value = [
        MagicMock(satellite=sat_new1, elevation_above_horizon=30),
        MagicMock(satellite=sat_new2, elevation_above_horizon=40),  # Best one
    ]

    result = strategy.compute_ground_object_connection_strategy(
        ground_object, [sat_old, sat_new1, sat_new2]
    )

    assert result.obsolete_links == [link]
    assert len(result.new_ground_object_connections) == 1
    conn = result.new_ground_object_connections[0]
    assert conn.satellite == sat_new2
    assert conn.connection_info["elevation_above_horizon"] == 40


@patch(
    "sat_com_connectivity.ground_object_to_space_connectivity.visibility_angle_utils.get_visible_satellites"
)
@patch(
    "sat_com_connectivity.ground_object_to_space_connectivity.visibility_angle_utils.get_elevation_angle"
)
def test_no_visible_satellites(mock_get_elevation_angle, mock_get_visible_satellites):
    strategy = ConnectToBestAngleUntilDisconnectionStrategy()
    ground_object = make_fake_ground_object()
    satellite = make_fake_satellite()

    link = GroundToSpaceLink(source=ground_object, destination=satellite)
    ground_object.links = [link]

    mock_get_elevation_angle.return_value = 10  # Invalid link
    mock_get_visible_satellites.return_value = []  # Nothing visible

    result = strategy.compute_ground_object_connection_strategy(
        ground_object, [satellite]
    )

    assert result.obsolete_links == [link]
    assert result.new_ground_object_connections == []


@patch(
    "sat_com_connectivity.ground_object_to_space_connectivity.visibility_angle_utils.get_visible_satellites"
)
@patch(
    "sat_com_connectivity.ground_object_to_space_connectivity.visibility_angle_utils.get_elevation_angle"
)
def test_best_satellite_has_highest_elevation(
    mock_get_elevation_angle, mock_get_visible_satellites
):
    strategy = ConnectToBestAngleUntilDisconnectionStrategy()
    ground_object = make_fake_ground_object()

    sat1 = make_fake_satellite()
    sat2 = make_fake_satellite()
    sat3 = make_fake_satellite()

    mock_get_visible_satellites.return_value = [
        MagicMock(satellite=sat1, elevation_above_horizon=20),
        MagicMock(satellite=sat2, elevation_above_horizon=45),
        MagicMock(satellite=sat3, elevation_above_horizon=35),
    ]
    ground_object.links = []  # No links to start

    result = strategy.compute_ground_object_connection_strategy(
        ground_object, [sat1, sat2, sat3]
    )

    assert len(result.obsolete_links) == 0
    assert len(result.new_ground_object_connections) == 1
    assert result.new_ground_object_connections[0].satellite == sat2
    assert (
        result.new_ground_object_connections[0].connection_info[
            "elevation_above_horizon"
        ]
        == 45
    )
