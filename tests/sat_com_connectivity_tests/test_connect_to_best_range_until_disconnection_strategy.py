from unittest.mock import MagicMock, patch

import pytest

from sat_com_connectivity.ground_object_to_space_connectivity.models import (
    GroundToSpaceConnection,
)
from sat_com_connectivity.ground_object_to_space_connectivity.strategies import (
    ConnectToBestRangeUntilDisconnectionStrategy,
)
from sat_com_model.models import (
    GroundToSpaceLink,
    GroundObjectDomain,
)
from tests.sat_com_connectivity_tests.utils import (
    make_fake_satellite,
    make_fake_ground_object,
)


@pytest.fixture
def strategy():
    mock_distance_model = MagicMock()
    return ConnectToBestRangeUntilDisconnectionStrategy(
        distance_model=mock_distance_model
    )


def test_valid_existing_link(strategy):
    mock_distance_model = strategy.distance_model

    ground_object = make_fake_ground_object()
    satellite = make_fake_satellite()

    link = GroundToSpaceLink(source=ground_object, destination=satellite)
    ground_object.links.append(link)

    mock_distance_model.get_ground_distance_km.return_value = 800

    result = strategy.compute_ground_object_connection_strategy(
        ground_object, [satellite]
    )
    # No new ground link and no obsolete links
    assert len(result.new_ground_object_connections) == 0
    assert len(result.obsolete_links) == 0


@patch(
    "sat_com_connectivity.ground_object_to_space_connectivity.visibility_angle_utils.get_elevation_angle_and_distance"
)
@patch(
    "sat_com_connectivity.ground_object_to_space_connectivity.strategies.estimate_time_until_disconnection"
)
def test_obsolete_link_then_connect_to_closest_satellite(
    mock_get_elevation_angle,
    mock_estimate_time_until_disconnection,
    strategy,
):
    mock_get_elevation_angle.return_value = 45
    mock_estimate_time_until_disconnection.return_value = (300, 1_000_000.0)

    mock_distance_model = strategy.distance_model

    strategy.distance_model.get_3d_distance_meters.return_value = 800_000

    # Setup ground object and satellites
    ground_object = make_fake_ground_object()
    obsolete_sat = make_fake_satellite()
    obsolete_sat.topology_uniq_id = 1

    candidate_sat_1 = make_fake_satellite()
    candidate_sat_1.topology_uniq_id = 2

    candidate_sat_2 = make_fake_satellite()
    candidate_sat_2.topology_uniq_id = 3

    # Existing link to obsolete satellite
    link = GroundToSpaceLink(
        source=ground_object,
        destination=obsolete_sat,
    )
    ground_object.links = [link]

    # Distance too large → link becomes obsolete
    mock_distance_model.get_ground_distance_km.return_value = 1500

    # Both candidate satellites are in range
    mock_distance_model.spatial_position_on_ground_in_range.return_value = [
        candidate_sat_1,
        candidate_sat_2,
    ]

    # Closest one is candidate_sat_2
    mock_distance_model.k_closest.return_value = [candidate_sat_2]

    result = strategy.compute_ground_object_connection_strategy(
        ground_object, [obsolete_sat, candidate_sat_1, candidate_sat_2]
    )

    assert len(result.obsolete_links) == 1
    assert result.obsolete_links[0] == link

    assert len(result.new_ground_object_connections) == 1
    assert result.new_ground_object_connections[0].satellite == candidate_sat_2


@patch(
    "sat_com_connectivity.ground_object_to_space_connectivity.visibility_angle_utils.get_elevation_angle_and_distance"
)
@patch(
    "sat_com_connectivity.ground_object_to_space_connectivity.strategies.estimate_time_until_disconnection"
)
def test_no_links_and_no_visible_satellites(
    mock_get_elevation_angle, mock_estimate_time_until_disconnection, strategy
):
    mock_distance_model = strategy.distance_model

    mock_get_elevation_angle.return_value = 45
    mock_estimate_time_until_disconnection.return_value = (300, 1_000_000.0)

    ground_object = make_fake_ground_object()
    ground_object.links = []

    satellite = make_fake_satellite()

    mock_distance_model.spatial_position_on_ground_in_range.return_value = []
    mock_get_elevation_angle.get_3d_distance_meters.return_value = 800_000

    result = strategy.compute_ground_object_connection_strategy(
        ground_object, [satellite]
    )

    assert result.obsolete_links == []
    assert result.new_ground_object_connections == []


@patch(
    "sat_com_connectivity.ground_object_to_space_connectivity.visibility_angle_utils.get_elevation_angle_and_distance"
)
@patch(
    "sat_com_connectivity.ground_object_to_space_connectivity.strategies.estimate_time_until_disconnection"
)
def test_k_closest_returns_non_satellite(
    mock_get_elevation_angle, mock_estimate_time_until_disconnection, strategy
):
    mock_distance_model = strategy.distance_model

    mock_get_elevation_angle.return_value = 45
    mock_estimate_time_until_disconnection.return_value = (300, 1_000_000.0)
    mock_get_elevation_angle.get_3d_distance_meters.return_value = 800_000

    ground_object = make_fake_ground_object()
    satellite = make_fake_satellite()
    ground_object.links = []

    mock_distance_model.spatial_position_on_ground_in_range.return_value = [satellite]
    mock_distance_model.k_closest.return_value = [MagicMock()]  # Not a Satellite

    with pytest.raises(TypeError, match="Expected Satellite"):
        strategy.compute_ground_object_connection_strategy(ground_object, [satellite])


@patch(
    "sat_com_connectivity.ground_object_to_space_connectivity.visibility_angle_utils.get_elevation_angle_and_distance"
)
@patch(
    "sat_com_connectivity.ground_object_to_space_connectivity.strategies.estimate_time_until_disconnection"
)
def test_white_list_empty_uses_closest_satellite(
    mock_estimate_time_until_disconnection,
    mock_get_elevation_angle,
    strategy,
):
    """Test that when white list is empty, closest range strategy is used (no priority)"""
    mock_distance_model = strategy.distance_model

    mock_get_elevation_angle.return_value = (45, 1_000_000.0)
    mock_estimate_time_until_disconnection.return_value = 300
    mock_distance_model.get_3d_distance_meters.return_value = 800_000

    ground_object = make_fake_ground_object()
    ground_object.ground_object_domain.shells_whitelist = []

    sat1 = make_fake_satellite()
    sat2 = make_fake_satellite()
    sat3 = make_fake_satellite()

    ground_object.links = []

    # All satellites in range
    mock_distance_model.spatial_position_on_ground_in_range.return_value = [
        sat1,
        sat2,
        sat3,
    ]

    # Closest one is sat2
    mock_distance_model.k_closest.return_value = [sat2]

    result = strategy.compute_ground_object_connection_strategy(
        ground_object, [sat1, sat2, sat3]
    )

    # Should pick sat2 (closest)
    assert len(result.new_ground_object_connections) == 1
    assert result.new_ground_object_connections[0].satellite == sat2


@patch(
    "sat_com_connectivity.ground_object_to_space_connectivity.visibility_angle_utils.get_elevation_angle_and_distance"
)
@patch(
    "sat_com_connectivity.ground_object_to_space_connectivity.strategies.estimate_time_until_disconnection"
)
def test_white_list_filters_satellites_by_shell_for_range(
    mock_estimate_time_until_disconnection,
    mock_get_elevation_angle,
    strategy,
):
    """Test that white list filters satellites by shell identifier for range strategy"""
    mock_distance_model = strategy.distance_model

    mock_get_elevation_angle.return_value = (45, 1_000_000.0)
    mock_estimate_time_until_disconnection.return_value = 300
    mock_distance_model.get_3d_distance_meters.return_value = 800_000

    ground_object = make_fake_ground_object()

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

    ground_object.links = []

    # All satellites in range
    mock_distance_model.spatial_position_on_ground_in_range.return_value = [
        sat1,
        sat2,
        sat3,
    ]

    # Closest in Shell-A is sat2
    mock_distance_model.k_closest.return_value = [sat2]

    result = strategy.compute_ground_object_connection_strategy(
        ground_object, [sat1, sat2, sat3]
    )

    # Should pick sat2 (closest in Shell-A), not sat3
    assert len(result.new_ground_object_connections) == 1
    assert result.new_ground_object_connections[0].satellite == sat2


@patch(
    "sat_com_connectivity.ground_object_to_space_connectivity.visibility_angle_utils.get_elevation_angle_and_distance"
)
@patch(
    "sat_com_connectivity.ground_object_to_space_connectivity.strategies.estimate_time_until_disconnection"
)
def test_white_list_ordered_priority_for_range(
    mock_estimate_time_until_disconnection,
    mock_get_elevation_angle,
    strategy,
):
    """Test that white list respects order priority for range strategy"""
    mock_distance_model = strategy.distance_model

    mock_get_elevation_angle.return_value = (45, 1_000_000.0)
    mock_estimate_time_until_disconnection.return_value = 300
    mock_distance_model.get_3d_distance_meters.return_value = 800_000

    ground_object = make_fake_ground_object()

    shell1 = MagicMock(identifier="First-Shell")
    shell2 = MagicMock(identifier="Second-Shell")

    sat1 = make_fake_satellite()
    sat1.shell = shell1

    sat2 = make_fake_satellite()
    sat2.shell = shell2

    # Set white list order: First-Shell, then Second-Shell
    ground_object.ground_object_domain.shells_whitelist = [
        "First-Shell",
        "Second-Shell",
    ]

    ground_object.links = []

    # All satellites in range
    mock_distance_model.spatial_position_on_ground_in_range.return_value = [
        sat1,
        sat2,
    ]

    # Closest in First-Shell is sat1
    mock_distance_model.k_closest.return_value = [sat1]

    result = strategy.compute_ground_object_connection_strategy(
        ground_object, [sat1, sat2]
    )

    # Should pick sat1 from First-Shell (higher priority)
    assert len(result.new_ground_object_connections) == 1
    assert result.new_ground_object_connections[0].satellite == sat1


@patch(
    "sat_com_connectivity.ground_object_to_space_connectivity.visibility_angle_utils.get_elevation_angle_and_distance"
)
@patch(
    "sat_com_connectivity.ground_object_to_space_connectivity.strategies.estimate_time_until_disconnection"
)
def test_white_list_fallback_to_next_shell_for_range(
    mock_estimate_time_until_disconnection,
    mock_get_elevation_angle,
    strategy,
):
    """Test fallback to next shell when first has no satellites in range"""
    mock_distance_model = strategy.distance_model

    mock_get_elevation_angle.return_value = (45, 1_000_000.0)
    mock_estimate_time_until_disconnection.return_value = 300
    mock_distance_model.get_3d_distance_meters.return_value = 800_000

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

    ground_object.links = []

    # Only satellites from Available-Shell are in range
    mock_distance_model.spatial_position_on_ground_in_range.return_value = [
        sat2a,
        sat2b,
    ]

    # Closest in Available-Shell is sat2a
    mock_distance_model.k_closest.return_value = [sat2a]

    result = strategy.compute_ground_object_connection_strategy(
        ground_object, [sat2a, sat2b]
    )

    # Should pick sat2a from Available-Shell (fallback)
    assert len(result.new_ground_object_connections) == 1
    assert result.new_ground_object_connections[0].satellite == sat2a


@patch(
    "sat_com_connectivity.ground_object_to_space_connectivity.visibility_angle_utils.get_elevation_angle_and_distance"
)
@patch(
    "sat_com_connectivity.ground_object_to_space_connectivity.strategies.estimate_time_until_disconnection"
)
def test_white_list_no_matching_shells_for_range(
    mock_estimate_time_until_disconnection,
    mock_get_elevation_angle,
    strategy,
):
    """Test that no connection is made if no satellites match white list shells"""
    mock_distance_model = strategy.distance_model

    mock_get_elevation_angle.return_value = (45, 1_000_000.0)
    mock_estimate_time_until_disconnection.return_value = 300
    mock_distance_model.get_3d_distance_meters.return_value = 800_000

    ground_object = make_fake_ground_object()

    shell1 = MagicMock(identifier="Other-Shell")

    sat1 = make_fake_satellite()
    sat1.shell = shell1

    # Set white list to non-existent shells
    ground_object.ground_object_domain.shells_whitelist = ["Non-Existent-Shell"]

    ground_object.links = []

    # Satellite in range but doesn't match white list
    mock_distance_model.spatial_position_on_ground_in_range.return_value = [sat1]
    mock_distance_model.k_closest.return_value = None

    result = strategy.compute_ground_object_connection_strategy(ground_object, [sat1])

    # Should not make connection
    assert len(result.new_ground_object_connections) == 0
