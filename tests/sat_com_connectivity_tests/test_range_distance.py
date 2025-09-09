from unittest.mock import MagicMock

from sat_com_connectivity.ground_object_to_space_connectivity.range_distance_utils import (
    check_and_update_distance_if_satellite_is_in_range,
)
from sat_com_model.models import GroundToSpaceLink
from tests.sat_com_connectivity_tests.utils import (
    make_fake_ground_object,
    make_fake_satellite,
)


def test_satellite_in_range():
    ground_object = make_fake_ground_object()
    satellite = make_fake_satellite()
    link = GroundToSpaceLink(source=ground_object, destination=satellite)

    mock_distance_model = MagicMock()
    mock_distance_model.get_ground_distance_km.return_value = (
        800  # Within 1000 km range
    )

    result = check_and_update_distance_if_satellite_is_in_range(
        link, mock_distance_model
    )

    assert result is True
    mock_distance_model.get_ground_distance_km.assert_called_once_with(
        ground_object.spatial_position, satellite.spatial_position
    )


def test_satellite_out_of_range():
    ground_object = make_fake_ground_object()
    satellite = make_fake_satellite()
    link = GroundToSpaceLink(source=ground_object, destination=satellite)

    mock_distance_model = MagicMock()
    mock_distance_model.get_ground_distance_km.return_value = (
        1500  # Outside 1000 km range
    )

    result = check_and_update_distance_if_satellite_is_in_range(
        link, mock_distance_model
    )

    assert result is False
    mock_distance_model.get_ground_distance_km.assert_called_once_with(
        ground_object.spatial_position, satellite.spatial_position
    )
