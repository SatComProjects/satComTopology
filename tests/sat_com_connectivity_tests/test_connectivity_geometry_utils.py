"""
Tests for sat_com_connectivity.utils: the single geodetic -> cartesian
conversion (WGS72 ellipsoid), the zenith fix, the deprecated aliases left in
sat_com_trajectopy.angle_utils, and the WGS72 constants of the constellation
generation.
"""

import datetime
import math
import warnings
from unittest.mock import MagicMock

import numpy as np
import pytest
from pyorbital import astronomy
from pyorbital.orbital import Orbital
from sgp4.api import WGS72, Satrec

import sat_com_trajectopy.angle_utils as deprecated_angle_utils
from sat_com_connectivity import utils
from sat_com_connectivity.ground_object_to_space_connectivity.visibility_angle_utils import (
    get_visible_satellites,
)
from sat_com_constellation.utils import generate_sso_dawn_dusk
from sat_com_constellation.walker_constellation.walker_propagation import (
    generate_two_line_elements,
)
from sat_com_model.constants import MU_KM3_S2, RE_KM, WGS72_A, WGS72_E2
from sat_com_model.models import Satellite, SpatialPosition

# ---------------------------------------------------------------------------
# Geodetic -> cartesian
# ---------------------------------------------------------------------------


def test_reference_points_of_the_ellipsoid():
    a_m = WGS72_A * 1000
    b_m = a_m * math.sqrt(1 - WGS72_E2)

    np.testing.assert_allclose(
        utils.latitude_longitude_altitude_to_x_y_z(0.0, 0.0, 0.0),
        (a_m, 0.0, 0.0),
        atol=1e-6,
    )
    np.testing.assert_allclose(
        utils.latitude_longitude_altitude_to_x_y_z(90.0, 0.0, 0.0),
        (0.0, 0.0, b_m),
        atol=1e-6,
    )
    np.testing.assert_allclose(
        utils.latitude_longitude_altitude_to_x_y_z(0.0, 90.0, 1000.0),
        (0.0, a_m + 1000.0, 0.0),
        atol=1e-6,
    )


def test_satellite_position_matches_sgp4():
    """
    Satellite lat/lon/alt come from pyorbital. Converting them back must give
    the SGP4 position (rotated to the Earth frame). The former sphere model was
    ~23 km off; the ellipsoid is within a meter.
    """
    tles = generate_two_line_elements("T", 4, 5, 1, 70.0, 15.0)
    for k, tle in enumerate(tles):
        orbital = Orbital("S", line1=tle.line1, line2=tle.line2)
        t = datetime.datetime(2026, 1, 1) + datetime.timedelta(minutes=11 * k)

        lon, lat, alt_km = orbital.get_lonlatalt(t)
        (x, y, z), _ = orbital.get_position(t, normalize=False)
        gmst = astronomy.gmst(t)
        expected_m = (
            np.array(
                [
                    x * math.cos(gmst) + y * math.sin(gmst),
                    -x * math.sin(gmst) + y * math.cos(gmst),
                    z,
                ]
            )
            * 1000
        )

        actual_m = np.array(
            utils.latitude_longitude_altitude_to_x_y_z(
                float(lat), float(lon), float(alt_km) * 1000
            )
        )
        assert np.linalg.norm(actual_m - expected_m) < 1.0


# ---------------------------------------------------------------------------
# Zenith
# ---------------------------------------------------------------------------

GROUND = (10.0, 20.0, 0.0)
SATELLITE_AT_ZENITH = (10.0, 20.0, 550_000.0)


def test_scalar_elevation_at_zenith_is_90_degrees():
    elevation, distance_m = utils.get_elevation_angle_and_distance(
        SATELLITE_AT_ZENITH, GROUND
    )
    assert elevation == pytest.approx(90.0)
    assert distance_m == pytest.approx(550_000.0)


def test_vectorised_elevation_at_zenith_is_90_degrees():
    sat_ecef = np.array(
        [utils.latitude_longitude_altitude_to_x_y_z(*SATELLITE_AT_ZENITH)]
    )
    gnd_ecef = np.array(utils.latitude_longitude_altitude_to_x_y_z(*GROUND))

    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        elevations, _ = utils.compute_elevations_and_distances(
            sat_ecef, gnd_ecef, utils.ground_to_up_vector(GROUND)
        )

    assert elevations[0] == pytest.approx(90.0)


def test_satellite_at_zenith_is_visible():
    satellite = MagicMock(spec=Satellite)
    satellite.get_coordinates.return_value = SpatialPosition(
        latitude=SATELLITE_AT_ZENITH[0],
        longitude=SATELLITE_AT_ZENITH[1],
        altitude=SATELLITE_AT_ZENITH[2],
    )
    ground_object = MagicMock()
    ground_object.get_coordinates.return_value = SpatialPosition(
        latitude=GROUND[0], longitude=GROUND[1], altitude=GROUND[2]
    )
    ground_object.ground_object_domain.elevation_above_horizon = 25.0

    visible = get_visible_satellites([satellite], ground_object)

    assert len(visible) == 1
    assert visible[0].elevation_above_horizon == pytest.approx(90.0)


# ---------------------------------------------------------------------------
# Deprecated aliases in sat_com_trajectopy
# ---------------------------------------------------------------------------

ALIAS_CALLS = {
    "latitude_longitude_altitude_to_x_y_z": (48.0, 2.0, 100.0),
    "get_elevation_angle": ((55.0, 10.0, 550_000.0), (48.0, 2.0, 0.0)),
    "get_elevation_angle_and_distance": ((55.0, 10.0, 550_000.0), (48.0, 2.0, 0.0)),
    "ground_to_up_vector": ((48.0, 2.0, 0.0),),
    "compute_elevations": (
        np.array([[7_000_000.0, 0.0, 0.0]]),
        np.array([6_378_135.0, 0.0, 0.0]),
        np.array([1.0, 0.0, 0.0]),
    ),
    "compute_elevations_and_distances": (
        np.array([[7_000_000.0, 0.0, 0.0]]),
        np.array([6_378_135.0, 0.0, 0.0]),
        np.array([1.0, 0.0, 0.0]),
    ),
    "satellites_to_ecef": ([],),
}


@pytest.mark.parametrize("name", sorted(ALIAS_CALLS))
def test_trajectopy_alias_warns_and_returns_the_moved_result(name):
    args = ALIAS_CALLS[name]

    with pytest.warns(FutureWarning, match=f"sat_com_connectivity.utils.{name}"):
        result = getattr(deprecated_angle_utils, name)(*args)

    expected = getattr(utils, name)(*args)
    if isinstance(expected, tuple):
        for r, e in zip(result, expected):
            np.testing.assert_array_equal(r, e)
    else:
        np.testing.assert_array_equal(result, expected)


def test_every_moved_function_has_an_alias():
    moved = {
        name
        for name, value in vars(utils).items()
        if callable(value) and getattr(value, "__module__", None) == utils.__name__
    }
    assert moved == set(ALIAS_CALLS)


# ---------------------------------------------------------------------------
# Constellation generation uses the WGS72 constants of SGP4
# ---------------------------------------------------------------------------


def test_sso_mean_motion_uses_wgs72_constants():
    altitude_km = 500.0
    tles = generate_sso_dawn_dusk(
        constellation_name="SSO",
        number_of_satellites=2,
        epoch=datetime.datetime(2026, 1, 1),
        altitude_km=altitude_km,
    )
    satellite = Satrec.twoline2rv(tles[0].line1, tles[0].line2, WGS72)

    expected_rad_per_min = math.sqrt(MU_KM3_S2 / (RE_KM + altitude_km) ** 3) * 60.0
    expected_rev_per_day = expected_rad_per_min * 1440 / (2 * math.pi)
    actual_rev_per_day = satellite.no_kozai * 1440 / (2 * math.pi)

    # TLE precision is 1e-8 rev/day; WGS84 constants would be ~1.4e-5 off.
    assert actual_rev_per_day == pytest.approx(expected_rev_per_day, abs=1e-7)
