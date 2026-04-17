from unittest.mock import MagicMock, patch

import pytest

from sat_com_connectivity.ground_object_to_space_connectivity.strategies import (
    ConnectToBestRangeUntilDisconnectionStrategy,
    ConnectToBestAngleUntilDisconnectionStrategy,
)
from sat_com_model.models import (
    GroundToSpaceLink,
    GroundObjectDomain,
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
    "sat_com_connectivity.ground_object_to_space_connectivity.strategies.get_visible_satellites"
)
@patch(
    "sat_com_connectivity.ground_object_to_space_connectivity.visibility_angle_utils.get_elevation_angle"
)
@patch(
    "sat_com_connectivity.ground_object_to_space_connectivity.strategies.estimate_time_until_disconnection"
)
def test_obsolete_link_then_pick_best(
    mock_estimate_time_until_disconnection,
    mock_get_elevation_angle,
    mock_get_visible_satellites,
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

    mock_estimate_time_until_disconnection.return_value = 300

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
    assert conn.ground_to_space_constraints.elevation_angle_above_horizon == 40


@patch(
    "sat_com_connectivity.ground_object_to_space_connectivity.strategies.get_visible_satellites"
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
    "sat_com_connectivity.ground_object_to_space_connectivity.strategies.get_visible_satellites"
)
@patch(
    "sat_com_connectivity.ground_object_to_space_connectivity.visibility_angle_utils.get_elevation_angle"
)
@patch(
    "sat_com_connectivity.ground_object_to_space_connectivity.strategies.estimate_time_until_disconnection"
)
def test_best_satellite_has_highest_elevation(
    mock_estimate_time_until_disconnection,
    mock_get_elevation_angle,
    mock_get_visible_satellites,
):
    strategy = ConnectToBestAngleUntilDisconnectionStrategy()
    ground_object = make_fake_ground_object()

    sat1 = make_fake_satellite()
    sat2 = make_fake_satellite()
    sat3 = make_fake_satellite()

    mock_estimate_time_until_disconnection.return_value = 300

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
        result.new_ground_object_connections[
            0
        ].ground_to_space_constraints.elevation_angle_above_horizon
        == 45
    )


@patch(
    "sat_com_connectivity.ground_object_to_space_connectivity.strategies.get_visible_satellites"
)
@patch(
    "sat_com_connectivity.ground_object_to_space_connectivity.strategies.estimate_time_until_disconnection"
)
def test_white_list_empty_uses_best_angle(
    mock_estimate_time_until_disconnection,
    mock_get_visible_satellites,
):
    """Test that when white list is empty, best angle strategy is used (no priority)"""
    strategy = ConnectToBestAngleUntilDisconnectionStrategy()
    ground_object = make_fake_ground_object()

    # Set empty white list
    ground_object.ground_object_domain.shells_whitelist = []

    sat1 = make_fake_satellite()
    sat2 = make_fake_satellite()
    sat3 = make_fake_satellite()

    mock_estimate_time_until_disconnection.return_value = 300

    mock_get_visible_satellites.return_value = [
        MagicMock(satellite=sat1, elevation_above_horizon=20),
        MagicMock(satellite=sat2, elevation_above_horizon=45),
        MagicMock(satellite=sat3, elevation_above_horizon=35),
    ]
    ground_object.links = []

    result = strategy.compute_ground_object_connection_strategy(
        ground_object, [sat1, sat2, sat3]
    )

    # Should pick sat2 with highest elevation
    assert len(result.new_ground_object_connections) == 1
    assert result.new_ground_object_connections[0].satellite == sat2


@patch(
    "sat_com_connectivity.ground_object_to_space_connectivity.strategies.get_visible_satellites"
)
@patch(
    "sat_com_connectivity.ground_object_to_space_connectivity.strategies.estimate_time_until_disconnection"
)
def test_white_list_filters_satellites_by_shell_identifier(
    mock_estimate_time_until_disconnection,
    mock_get_visible_satellites,
):
    """Test that white list filters satellites by shell identifier"""
    strategy = ConnectToBestAngleUntilDisconnectionStrategy()
    ground_object = make_fake_ground_object()

    # Create satellites with different shell identifiers
    shell1 = MagicMock(identifier="Shell-A")
    shell2 = MagicMock(identifier="Shell-B")

    sat1 = make_fake_satellite()
    sat1.shell = shell1

    sat2 = make_fake_satellite()
    sat2.shell = shell1

    sat3 = make_fake_satellite()
    sat3.shell = shell2

    # Set white list to only Shell-A
    ground_object.ground_object_domain.shells_whitelist = ["Shell-A"]

    mock_estimate_time_until_disconnection.return_value = 300

    # All satellites are visible, but white list should filter to Shell-A only
    mock_get_visible_satellites.return_value = [
        MagicMock(satellite=sat1, elevation_above_horizon=30),
        MagicMock(satellite=sat2, elevation_above_horizon=25),  # Best in Shell-A
        MagicMock(
            satellite=sat3, elevation_above_horizon=50
        ),  # Best overall but in Shell-B
    ]
    ground_object.links = []

    result = strategy.compute_ground_object_connection_strategy(
        ground_object, [sat1, sat2, sat3]
    )

    # Should pick sat1 (best in Shell-A), not sat3 (best overall but different shell)
    assert len(result.new_ground_object_connections) == 1
    assert result.new_ground_object_connections[0].satellite == sat1
    assert (
        result.new_ground_object_connections[0].satellite.shell.identifier == "Shell-A"
    )


@patch(
    "sat_com_connectivity.ground_object_to_space_connectivity.strategies.get_visible_satellites"
)
@patch(
    "sat_com_connectivity.ground_object_to_space_connectivity.strategies.estimate_time_until_disconnection"
)
def test_white_list_ordered_priority(
    mock_estimate_time_until_disconnection,
    mock_get_visible_satellites,
):
    """Test that white list respects the order priority - first shell with visible satellites is used"""
    strategy = ConnectToBestAngleUntilDisconnectionStrategy()
    ground_object = make_fake_ground_object()

    shell1 = MagicMock(identifier="First-Shell")
    shell2 = MagicMock(identifier="Second-Shell")

    sat1 = make_fake_satellite()
    sat1.shell = shell1

    sat2 = make_fake_satellite()
    sat2.shell = shell2

    # Set white list with order: First-Shell, then Second-Shell
    ground_object.ground_object_domain.shells_whitelist = [
        "First-Shell",
        "Second-Shell",
    ]

    mock_estimate_time_until_disconnection.return_value = 300

    mock_get_visible_satellites.return_value = [
        MagicMock(satellite=sat1, elevation_above_horizon=25),
        MagicMock(
            satellite=sat2, elevation_above_horizon=50
        ),  # Higher elevation but lower priority
    ]
    ground_object.links = []

    result = strategy.compute_ground_object_connection_strategy(
        ground_object, [sat1, sat2]
    )

    # Should pick sat1 from First-Shell despite lower elevation
    assert len(result.new_ground_object_connections) == 1
    assert result.new_ground_object_connections[0].satellite == sat1


@patch(
    "sat_com_connectivity.ground_object_to_space_connectivity.strategies.get_visible_satellites"
)
@patch(
    "sat_com_connectivity.ground_object_to_space_connectivity.strategies.estimate_time_until_disconnection"
)
def test_white_list_fallback_to_next_shell(
    mock_estimate_time_until_disconnection,
    mock_get_visible_satellites,
):
    """Test that if first shell has no visible satellites, fallback to next shell in white list"""
    strategy = ConnectToBestAngleUntilDisconnectionStrategy()
    ground_object = make_fake_ground_object()

    shell1 = MagicMock(identifier="Empty-Shell")
    shell2 = MagicMock(identifier="Available-Shell")

    sat2a = make_fake_satellite()
    sat2a.shell = shell2

    sat2b = make_fake_satellite()
    sat2b.shell = shell2

    # Set white list: Empty-Shell first, then Available-Shell
    ground_object.ground_object_domain.shells_whitelist = [
        "Empty-Shell",
        "Available-Shell",
    ]

    mock_estimate_time_until_disconnection.return_value = 300

    # Only satellites from Available-Shell are visible
    mock_get_visible_satellites.return_value = [
        MagicMock(satellite=sat2a, elevation_above_horizon=30),
        MagicMock(
            satellite=sat2b, elevation_above_horizon=40
        ),  # Best in Available-Shell
    ]
    ground_object.links = []

    result = strategy.compute_ground_object_connection_strategy(
        ground_object, [sat2a, sat2b]
    )

    # Should pick sat2b from Available-Shell (fallback from Empty-Shell)
    assert len(result.new_ground_object_connections) == 1
    assert result.new_ground_object_connections[0].satellite == sat2b


@patch(
    "sat_com_connectivity.ground_object_to_space_connectivity.strategies.get_visible_satellites"
)
@patch(
    "sat_com_connectivity.ground_object_to_space_connectivity.strategies.estimate_time_until_disconnection"
)
def test_white_list_no_matching_shells(
    mock_estimate_time_until_disconnection,
    mock_get_visible_satellites,
):
    """Test that if no satellites match white list shells, no connection is made"""
    strategy = ConnectToBestAngleUntilDisconnectionStrategy()
    ground_object = make_fake_ground_object()

    shell1 = MagicMock(identifier="Other-Shell")

    sat1 = make_fake_satellite()
    sat1.shell = shell1

    # Set white list to shells that don't exist in visible satellites
    ground_object.ground_object_domain.shells_whitelist = ["Non-Existent-Shell"]

    mock_estimate_time_until_disconnection.return_value = 300

    mock_get_visible_satellites.return_value = [
        MagicMock(satellite=sat1, elevation_above_horizon=45),
    ]
    ground_object.links = []

    result = strategy.compute_ground_object_connection_strategy(ground_object, [sat1])

    # Should not make connection since no satellites match white list
    assert len(result.new_ground_object_connections) == 0
