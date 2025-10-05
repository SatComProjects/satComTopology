from sat_com_connectivity.ground_object_to_space_connectivity.utils import (
    get_best_visible_satellite_with_biggest_shell,
)
from sat_com_connectivity.ground_object_to_space_connectivity.visibility_angle_utils import (
    VisibleSatellite,
)
from tests.sat_com_connectivity_tests.utils import (
    make_fake_satellite_big_low_inclination_shell,
    make_fake_satellite_small_close_polar_shell,
    make_fake_ground_object,
)


def test_get_best_visible_satellite_with_biggest_shell():

    sat1 = make_fake_satellite_big_low_inclination_shell()  # Shell size 24
    sat2 = make_fake_satellite_big_low_inclination_shell()  # Shell size 24
    sat3 = make_fake_satellite_small_close_polar_shell()  # Shell size 12
    sat4 = make_fake_satellite_small_close_polar_shell()  # Shell size 12
    sat5 = make_fake_satellite_small_close_polar_shell()  # Shell size 12

    visible_sat1 = VisibleSatellite(satellite=sat1, elevation_above_horizon=20)
    visible_sat2 = VisibleSatellite(
        satellite=sat2, elevation_above_horizon=45
    )  # Best in big shell
    visible_sat3 = VisibleSatellite(satellite=sat3, elevation_above_horizon=35)
    visible_sat4 = VisibleSatellite(
        satellite=sat4, elevation_above_horizon=50
    )  # Best in small shell
    visible_sat5 = VisibleSatellite(satellite=sat5, elevation_above_horizon=30)

    visible_satellites = [
        visible_sat1,
        visible_sat2,
        visible_sat3,
        visible_sat4,
        visible_sat5,
    ]

    result = get_best_visible_satellite_with_biggest_shell(visible_satellites)

    assert result is not None
    assert isinstance(result, VisibleSatellite)
    assert result.satellite.topology_uniq_id == sat2.topology_uniq_id
    assert result.elevation_above_horizon == 45


def test_assert_that_if_only_small_shell_is_visible_it_returns_best_satellite():
    sat1 = make_fake_satellite_small_close_polar_shell()  # Shell size 12
    sat2 = make_fake_satellite_small_close_polar_shell()  # Shell size 12
    sat3 = make_fake_satellite_small_close_polar_shell()  # Shell size 12

    visible_sat1 = VisibleSatellite(satellite=sat1, elevation_above_horizon=20)
    visible_sat2 = VisibleSatellite(
        satellite=sat2, elevation_above_horizon=45
    )  # Best in small shell
    visible_sat3 = VisibleSatellite(satellite=sat3, elevation_above_horizon=35)

    visible_satellites = [visible_sat1, visible_sat2, visible_sat3]

    result = get_best_visible_satellite_with_biggest_shell(visible_satellites)

    assert result is not None
    assert isinstance(result, VisibleSatellite)
    assert result.satellite.topology_uniq_id == sat2.topology_uniq_id
    assert result.elevation_above_horizon == 45


def test_assert_that_if_only_big_shell_is_visible_it_returns_best_satellite():
    sat1 = make_fake_satellite_big_low_inclination_shell()  # Shell size 24
    sat2 = make_fake_satellite_big_low_inclination_shell()  # Shell size 24
    sat3 = make_fake_satellite_big_low_inclination_shell()  # Shell size 24

    visible_sat1 = VisibleSatellite(satellite=sat1, elevation_above_horizon=20)
    visible_sat2 = VisibleSatellite(
        satellite=sat2, elevation_above_horizon=45
    )  # Best in big shell
    visible_sat3 = VisibleSatellite(satellite=sat3, elevation_above_horizon=35)

    visible_satellites = [visible_sat1, visible_sat2, visible_sat3]

    result = get_best_visible_satellite_with_biggest_shell(visible_satellites)

    assert result is not None
    assert isinstance(result, VisibleSatellite)
    assert result.satellite.topology_uniq_id == sat2.topology_uniq_id
    assert result.elevation_above_horizon == 45
