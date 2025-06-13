import pytest
from unittest.mock import MagicMock, patch

from sat_com_connectivity.ground_object_connectivity.visibility_angle import (
    get_visible_satellites,
    VisibleSatellite,
)
from sat_com_model.models import Satellite, GroundObject


@patch(
    "sat_com_connectivity.ground_object_connectivity.visibility_angle.get_elevation_angle"
)
def test_get_visible_satellites_filters_correctly(mock_get_elevation_angle):
    sat1 = MagicMock(spec=Satellite)
    sat2 = MagicMock(spec=Satellite)
    ground = MagicMock()

    ground_domain_mock = MagicMock()
    ground_domain_mock.elevation_above_horizon = 10
    ground.ground_object_domain = ground_domain_mock

    sat1.get_coordinates.return_value.to_latitude_longitude_altitude.return_value = (
        0,
        0,
        0,
    )
    sat2.get_coordinates.return_value.to_latitude_longitude_altitude.return_value = (
        0,
        0,
        0,
    )
    ground.get_coordinates.return_value.to_latitude_longitude_altitude.return_value = (
        0,
        0,
        0,
    )

    mock_get_elevation_angle.side_effect = [15, 5]  # sat1 passes, sat2 doesn't

    result = get_visible_satellites([sat1, sat2], ground)

    assert len(result) == 1
    assert isinstance(result[0], VisibleSatellite)
    assert result[0].satellite == sat1
    assert result[0].elevation_above_horizon == 15


@patch(
    "sat_com_connectivity.ground_object_connectivity.visibility_angle.get_elevation_angle"
)
def test_get_visible_satellites_all_below_threshold(mock_get_elevation_angle):
    # Create mocks
    sat = MagicMock(spec=Satellite)
    ground = MagicMock(spec=GroundObject)

    # Set up return values
    sat.get_coordinates.return_value.to_latitude_longitude_altitude.return_value = (
        0,
        0,
        0,
    )
    ground.get_coordinates.return_value.to_latitude_longitude_altitude.return_value = (
        0,
        0,
        0,
    )

    # Fix: assign a mock ground_object_domain explicitly
    ground_domain_mock = MagicMock()
    ground_domain_mock.elevation_above_horizon = 30
    ground.ground_object_domain = ground_domain_mock

    # Elevation angle is below the threshold
    mock_get_elevation_angle.return_value = 25

    result = get_visible_satellites([sat], ground)

    assert result == []
