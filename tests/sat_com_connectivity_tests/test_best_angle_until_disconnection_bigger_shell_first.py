from unittest.mock import MagicMock, patch


from sat_com_connectivity.ground_object_to_space_connectivity.strategies import (
    ConnectToBestAngleUntilDisconnectionPreferBiggerShellStrategy,
)
from sat_com_model.models import (
    GroundToSpaceLink,
)
from tests.sat_com_connectivity_tests.utils import (
    make_fake_ground_object,
    make_fake_satellite,
    make_fake_satellite_big_low_inclination_shell,
    make_fake_satellite_small_close_polar_shell,
)


@patch(
    "sat_com_connectivity.ground_object_to_space_connectivity.visibility_angle_utils.get_elevation_angle"
)
def test_keep_existing_link(mock_get_elevation_angle_visibility_angle):
    strategy = ConnectToBestAngleUntilDisconnectionPreferBiggerShellStrategy()
    ground_object = make_fake_ground_object()
    satellite = make_fake_satellite_big_low_inclination_shell()

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
def test_obsolete_link_then_pick_best(
    mock_get_elevation_angle, mock_get_visible_satellites
):
    strategy = ConnectToBestAngleUntilDisconnectionPreferBiggerShellStrategy()
    ground_object = make_fake_ground_object()
    sat_old = make_fake_satellite_big_low_inclination_shell()
    sat_new1 = make_fake_satellite_big_low_inclination_shell()
    sat_new2 = make_fake_satellite_big_low_inclination_shell()

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
    "sat_com_connectivity.ground_object_to_space_connectivity.strategies.get_visible_satellites"
)
@patch(
    "sat_com_connectivity.ground_object_to_space_connectivity.visibility_angle_utils.get_elevation_angle"
)
def test_no_visible_satellites(mock_get_elevation_angle, mock_get_visible_satellites):
    strategy = ConnectToBestAngleUntilDisconnectionPreferBiggerShellStrategy()
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
def test_best_satellite_has_highest_elevation(mock_get_visible_satellites):
    strategy = ConnectToBestAngleUntilDisconnectionPreferBiggerShellStrategy()
    ground_object = make_fake_ground_object()

    sat1 = make_fake_satellite_big_low_inclination_shell()
    sat2 = make_fake_satellite_big_low_inclination_shell()
    sat3 = make_fake_satellite_big_low_inclination_shell()

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


def test_that_if_two_shells_exists_ground_station_selects_bigger_shell():
    strategy = ConnectToBestAngleUntilDisconnectionPreferBiggerShellStrategy()
    ground_object = make_fake_ground_object()

    # Create satellites from two different shells
    sat_small_shell = make_fake_satellite_small_close_polar_shell()

    sat_big_shell = make_fake_satellite_big_low_inclination_shell()

    # Both satellites are visible, but the one from the bigger shell has slightly lower elevation
    with patch(
        "sat_com_connectivity.ground_object_to_space_connectivity.strategies.get_visible_satellites"
    ) as mock_get_visible_satellites:
        mock_get_visible_satellites.return_value = [
            MagicMock(satellite=sat_small_shell, elevation_above_horizon=50),
            MagicMock(
                satellite=sat_big_shell, elevation_above_horizon=45
            ),  # Lower elevation
        ]

        result = strategy.compute_ground_object_connection_strategy(
            ground_object, [sat_small_shell, sat_big_shell]
        )

        assert len(result.obsolete_links) == 0
        assert len(result.new_ground_object_connections) == 1
        # Ensure the satellite from the bigger shell is selected despite lower elevation
        assert result.new_ground_object_connections[0].satellite == sat_big_shell
        assert (
            result.new_ground_object_connections[0].connection_info[
                "elevation_above_horizon"
            ]
            == 45
        )


def test_that_if_only_lower_shell_is_visible_it_gets_selected():
    strategy = ConnectToBestAngleUntilDisconnectionPreferBiggerShellStrategy()
    ground_object = make_fake_ground_object()

    # Create satellites from two different shells
    sat_small_shell = make_fake_satellite_small_close_polar_shell()

    sat_big_shell = make_fake_satellite_big_low_inclination_shell()

    # Only the small shell satellite is visible
    with patch(
        "sat_com_connectivity.ground_object_to_space_connectivity.strategies.get_visible_satellites"
    ) as mock_get_visible_satellites:
        mock_get_visible_satellites.return_value = [
            MagicMock(satellite=sat_small_shell, elevation_above_horizon=50),
            # Big shell satellite not visible
        ]

        result = strategy.compute_ground_object_connection_strategy(
            ground_object, [sat_small_shell, sat_big_shell]
        )

        assert len(result.obsolete_links) == 0
        assert len(result.new_ground_object_connections) == 1
        # Ensure the only visible satellite is selected
        assert result.new_ground_object_connections[0].satellite == sat_small_shell
        assert (
            result.new_ground_object_connections[0].connection_info[
                "elevation_above_horizon"
            ]
            == 50
        )
