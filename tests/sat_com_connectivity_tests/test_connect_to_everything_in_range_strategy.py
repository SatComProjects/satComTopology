from unittest.mock import MagicMock

from sat_com_connectivity.ground_object_to_space_connectivity.strategies import (
    ConnectToEverythingInRangeStrategy,
)
from sat_com_model.models import GroundToSpaceLink
from tests.sat_com_connectivity_tests.utils import (
    make_fake_ground_object,
    make_fake_satellite,
)


def test_connect_to_everything_in_range_strategy():
    mock_distance_model = MagicMock()

    strategy = ConnectToEverythingInRangeStrategy(distance_model=mock_distance_model)

    ground_object = make_fake_ground_object()
    ground_object.ground_object_domain.maximum_satellite_range_distance = 1000

    sat_in_range_1 = make_fake_satellite()
    sat_in_range_1.topology_uniq_id = 101

    sat_in_range_2 = make_fake_satellite()
    sat_in_range_2.topology_uniq_id = 102

    sat_out_of_range = make_fake_satellite()
    sat_out_of_range.topology_uniq_id = 103

    # Existing link to be removed
    existing_link = GroundToSpaceLink(
        source=ground_object, destination=sat_out_of_range
    )
    ground_object.links = [existing_link]

    # Simulate only 2 satellites are in range
    mock_distance_model.spatial_position_in_range.return_value = [
        type("VisibleSatellite", (), {"satellite": sat_in_range_1}),
        type("VisibleSatellite", (), {"satellite": sat_in_range_2}),
    ]

    result = strategy.compute_ground_object_connection_strategy(
        ground_object, [sat_in_range_1, sat_in_range_2, sat_out_of_range]
    )

    # Assert existing link is marked as obsolete
    assert len(result.obsolete_links) == 1
    assert result.obsolete_links[0] == existing_link

    # Assert new connections are created only for satellites in range
    new_connections = result.new_ground_object_connections
    assert len(new_connections) == 2

    connected_ids = {conn.satellite.topology_uniq_id for conn in new_connections}
    assert connected_ids == {101, 102}

    # Connection info should be empty dicts
    for conn in new_connections:
        assert conn.connection_info == {}
