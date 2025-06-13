from unittest.mock import MagicMock, patch

from sat_com_connectivity.ground_object_to_space_connectivity.visibility_angle_utils import (
    get_visible_satellites,
    VisibleSatellite,
    get_best_satellites_among_visible_satellites,
    check_and_update_elevation_if_satellite_is_visible,
)
from sat_com_model.models import Satellite, GroundObject, GroundToSpaceLink
from tests.sat_com_connectivity_tests.utils import (
    make_fake_ground_object,
    make_fake_satellite,
)


@patch(
    "sat_com_connectivity.ground_object_to_space_connectivity.visibility_angle_utils.get_elevation_angle"
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
    "sat_com_connectivity.ground_object_to_space_connectivity.visibility_angle_utils.get_elevation_angle"
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


@patch(
    "sat_com_connectivity.ground_object_to_space_connectivity.visibility_angle_utils.get_visible_satellites"
)
def test_get_best_satellites_among_visible_satellites_returns_highest(mock_get_visible):
    ground_object = make_fake_ground_object()
    sat1 = make_fake_satellite()
    sat2 = make_fake_satellite()
    sat3 = make_fake_satellite()

    sat1.topology_uniq_id = 1
    sat2.topology_uniq_id = 2
    sat3.topology_uniq_id = 3

    mock_get_visible.return_value = [
        VisibleSatellite(satellite=sat1, elevation_above_horizon=10),
        VisibleSatellite(satellite=sat2, elevation_above_horizon=45),  # Best
        VisibleSatellite(satellite=sat3, elevation_above_horizon=30),
    ]

    result = get_best_satellites_among_visible_satellites(
        ground_object, [sat1, sat2, sat3]
    )

    assert result is not None
    assert isinstance(result, VisibleSatellite)
    assert result.satellite.topology_uniq_id == 2
    assert result.elevation_above_horizon == 45


@patch(
    "sat_com_connectivity.ground_object_to_space_connectivity.visibility_angle_utils.get_visible_satellites"
)
def test_get_best_satellites_among_visible_satellites_returns_none_if_no_visible(
    mock_get_visible,
):
    ground_object = make_fake_ground_object()
    mock_get_visible.return_value = []

    result = get_best_satellites_among_visible_satellites(ground_object, [])

    assert result is None


@patch(
    "sat_com_connectivity.ground_object_to_space_connectivity.visibility_angle_utils.get_elevation_angle"
)
def test_satellite_visible_elevation_above_threshold(mock_get_elevation_angle):
    ground_object = make_fake_ground_object()
    satellite = make_fake_satellite()

    link = GroundToSpaceLink(source=ground_object, destination=satellite)

    mock_get_elevation_angle.return_value = 40  # Above threshold (25 by default)

    result = check_and_update_elevation_if_satellite_is_visible(link)

    assert result is True
    assert link.elevation_above_horizon_angle == 40


@patch(
    "sat_com_connectivity.ground_object_to_space_connectivity.visibility_angle_utils.get_elevation_angle"
)
def test_satellite_not_visible_elevation_below_threshold(mock_get_elevation_angle):
    ground_object = make_fake_ground_object()
    satellite = make_fake_satellite()

    link = GroundToSpaceLink(source=ground_object, destination=satellite)

    mock_get_elevation_angle.return_value = 15  # Below threshold (25 by default)

    result = check_and_update_elevation_if_satellite_is_visible(link)

    assert result is False
    assert link.elevation_above_horizon_angle is None  # Should not be set
