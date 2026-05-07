from unittest.mock import MagicMock

import pytest

from sat_com_connectivity.ground_object_to_space_connectivity.models import (
    GroundToSpaceConnection,
)
from sat_com_connectivity.ground_object_to_space_connectivity.strategies import (
    ConnectToBestRangeUntilDisconnectionStrategy,
)
from sat_com_model.models import (
    GroundToSpaceLink,
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


def test_obsolete_link_then_connect_to_closest_satellite(strategy):
    mock_distance_model = strategy.distance_model

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


def test_no_links_and_no_visible_satellites(strategy):
    mock_distance_model = strategy.distance_model

    ground_object = make_fake_ground_object()
    ground_object.links = []

    satellite = make_fake_satellite()

    mock_distance_model.spatial_position_on_ground_in_range.return_value = []

    result = strategy.compute_ground_object_connection_strategy(
        ground_object, [satellite]
    )

    assert result.obsolete_links == []
    assert result.new_ground_object_connections == []


def test_k_closest_returns_non_satellite(strategy):
    mock_distance_model = strategy.distance_model

    ground_object = make_fake_ground_object()
    satellite = make_fake_satellite()
    ground_object.links = []

    mock_distance_model.spatial_position_on_ground_in_range.return_value = [satellite]
    mock_distance_model.k_closest.return_value = [MagicMock()]  # Not a Satellite

    with pytest.raises(TypeError, match="Expected Satellite"):
        strategy.compute_ground_object_connection_strategy(ground_object, [satellite])
