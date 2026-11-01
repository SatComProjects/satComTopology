import datetime
from unittest.mock import MagicMock, patch

import pytest

from sat_com_trajectopy.orbital_models import PyOrbitalModel
from sat_com_model.models import SpatialPosition

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FAKE_TLE = {
    "satellite_name": "TEST-SAT",
    "line1": "1 25544U 98067A   24001.00000000  .00000000  00000-0  00000-0 0  9999",
    "line2": "2 25544  51.6400   0.0000 0001000   0.0000   0.0000 15.50000000000000",
}

FAKE_LON_LAT_ALT_KM = (-4.74, 42.75, 550.0)  # lon, lat, alt in km
FAKE_POSITION_ECI_KM = (6500.0, 1000.0, 1000.0)  # km
FAKE_VELOCITY_ECI_KMS = (-1.0, 7.0, 0.5)  # km/s


def make_model(now: datetime.datetime = None) -> tuple[PyOrbitalModel, MagicMock]:
    """Return (model, mock_orbital_object) with clock fixed at `now`."""
    if now is None:
        now = datetime.datetime(2024, 1, 1, 12, 0, 0)

    clock = MagicMock()
    clock.get_current_time.return_value = now

    with patch("sat_com_trajectopy.orbital_models.Orbital") as MockOrbital:
        mock_orb = MagicMock()
        MockOrbital.return_value = mock_orb

        mock_orb.get_lonlatalt.return_value = FAKE_LON_LAT_ALT_KM
        mock_orb.get_position.return_value = (
            FAKE_POSITION_ECI_KM,
            FAKE_VELOCITY_ECI_KMS,
        )

        model = PyOrbitalModel(tle=FAKE_TLE, time_manager=clock)
        model.orbital_object = mock_orb

    return model, mock_orb


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------


class TestPyOrbitalModelInit:

    def test_satellite_name_set_from_tle(self):
        model, _ = make_model()
        assert model.satellite_name == "TEST-SAT"

    def test_line1_set_from_tle(self):
        model, _ = make_model()
        assert model.line1 == FAKE_TLE["line1"]

    def test_line2_set_from_tle(self):
        model, _ = make_model()
        assert model.line2 == FAKE_TLE["line2"]

    def test_caches_are_empty_dicts_on_creation(self):
        model, _ = make_model()
        assert model._lonlatalt_cache == {}
        assert model._eci_cache == {}


# ---------------------------------------------------------------------------
# get_datetime
# ---------------------------------------------------------------------------


class TestGetDatetime:

    def test_returns_clock_current_time(self):
        now = datetime.datetime(2024, 6, 15, 8, 30, 0)
        model, _ = make_model(now)
        assert model.get_datetime() == now

    def test_returns_datetime_instance(self):
        model, _ = make_model()
        assert isinstance(model.get_datetime(), datetime.datetime)


# ---------------------------------------------------------------------------
# get_longitude_latitude_altitude
# ---------------------------------------------------------------------------


class TestGetLongitudeLatitudeAltitude:

    def test_returns_spatial_position_instance(self):
        model, _ = make_model()
        result = model.get_longitude_latitude_altitude()
        assert isinstance(result, SpatialPosition)

    def test_altitude_is_converted_from_km_to_metres(self):
        model, _ = make_model()
        result = model.get_longitude_latitude_altitude()
        assert result.altitude == pytest.approx(FAKE_LON_LAT_ALT_KM[2] * 1000.0)

    def test_altitude_is_not_in_km(self):
        model, _ = make_model()
        result = model.get_longitude_latitude_altitude()
        assert result.altitude != pytest.approx(FAKE_LON_LAT_ALT_KM[2])

    def test_longitude_is_preserved(self):
        model, _ = make_model()
        result = model.get_longitude_latitude_altitude()
        assert result.longitude == pytest.approx(FAKE_LON_LAT_ALT_KM[0])

    def test_latitude_is_preserved(self):
        model, _ = make_model()
        result = model.get_longitude_latitude_altitude()
        assert result.latitude == pytest.approx(FAKE_LON_LAT_ALT_KM[1])

    def test_altitude_is_positive_for_leo_satellite(self):
        model, _ = make_model()
        result = model.get_longitude_latitude_altitude()
        assert result.altitude > 0

    def test_altitude_is_above_earth_surface_in_metres(self):
        model, _ = make_model()
        result = model.get_longitude_latitude_altitude()
        assert 200_000 < result.altitude < 2_000_000

    def test_future_query_returns_correct_altitude_in_metres(self):
        future_alt_km = 551.0
        model, mock_orb = make_model()
        mock_orb.get_lonlatalt.return_value = (-4.0, 42.0, future_alt_km)
        result = model.get_longitude_latitude_altitude(delta_t=60.0)
        assert result.altitude == pytest.approx(future_alt_km * 1000.0)

    # --- Cache behaviour (new dict cache) ---

    def test_cache_hit_avoids_second_sgp4_call(self):
        model, mock_orb = make_model()
        model.get_longitude_latitude_altitude()
        model.get_longitude_latitude_altitude()
        mock_orb.get_lonlatalt.assert_called_once()

    def test_future_query_populates_cache(self):
        """Any absolute time is now cached, including future offsets."""
        model, mock_orb = make_model()
        model.get_longitude_latitude_altitude(delta_t=60.0)
        assert len(model._lonlatalt_cache) == 1
        mock_orb.get_lonlatalt.assert_called_once()

        # second call at the same future time must hit the cache
        model.get_longitude_latitude_altitude(delta_t=60.0)
        mock_orb.get_lonlatalt.assert_called_once()

    def test_different_delta_t_are_cached_independently(self):
        model, mock_orb = make_model()
        model.get_longitude_latitude_altitude(delta_t=0.0)
        model.get_longitude_latitude_altitude(delta_t=60.0)
        assert mock_orb.get_lonlatalt.call_count == 2
        assert len(model._lonlatalt_cache) == 2

    def test_cache_purged_when_clock_advances_past_entry(self):
        now = datetime.datetime(2024, 1, 1, 12, 0, 0)
        model, mock_orb = make_model(now)

        model.get_longitude_latitude_altitude()  # cached at `now`
        assert len(model._lonlatalt_cache) == 1

        # Advance clock past the cached time → entry must be purged
        model.clock.get_current_time.return_value = now + datetime.timedelta(seconds=1)
        model.get_longitude_latitude_altitude()

        assert mock_orb.get_lonlatalt.call_count == 2
        # only the new time remains
        assert len(model._lonlatalt_cache) == 1
        assert now not in model._lonlatalt_cache


# ---------------------------------------------------------------------------
# get_position / get_velocity ECI
# ---------------------------------------------------------------------------


class TestGetPositionEarthGeneralInertial:

    def test_returns_tuple_of_three_floats(self):
        model, _ = make_model()
        result = model.get_position_earth_general_inertial()
        assert len(result) == 3
        assert all(isinstance(v, (float, int)) for v in result)

    def test_position_values_are_in_km_not_metres(self):
        model, _ = make_model()
        result = model.get_position_earth_general_inertial()
        magnitude = sum(v**2 for v in result) ** 0.5
        assert (
            6000 < magnitude < 8000
        ), f"ECI position magnitude {magnitude:.1f} is not in km range [6000, 8000]"

    def test_position_matches_sgp4_output(self):
        model, _ = make_model()
        result = model.get_position_earth_general_inertial()
        assert result == pytest.approx(FAKE_POSITION_ECI_KM)

    def test_future_query_propagates_and_caches(self):
        model, mock_orb = make_model()
        model.get_position_earth_general_inertial(delta_t=120.0)
        mock_orb.get_position.assert_called_once()
        assert len(model._eci_cache) == 1

        # same future time → cache hit
        model.get_position_earth_general_inertial(delta_t=120.0)
        mock_orb.get_position.assert_called_once()

    def test_cache_hit_avoids_second_sgp4_call(self):
        model, mock_orb = make_model()
        model.get_position_earth_general_inertial()
        model.get_position_earth_general_inertial()
        mock_orb.get_position.assert_called_once()

    def test_position_call_populates_velocity_in_same_cache_entry(self):
        model, _ = make_model()
        model.get_position_earth_general_inertial()
        # velocity must be available from the same cache entry
        vel = model.get_velocity_earth_general_inertial()
        assert vel == pytest.approx(FAKE_VELOCITY_ECI_KMS)


class TestGetVelocityEarthGeneralInertial:

    def test_returns_tuple_of_three_floats(self):
        model, _ = make_model()
        result = model.get_velocity_earth_general_inertial()
        assert len(result) == 3
        assert all(isinstance(v, (float, int)) for v in result)

    def test_velocity_values_are_in_km_per_second_not_metres(self):
        model, _ = make_model()
        result = model.get_velocity_earth_general_inertial()
        magnitude = sum(v**2 for v in result) ** 0.5
        assert (
            1 < magnitude < 12
        ), f"ECI velocity magnitude {magnitude:.3f} is not in km/s range [1, 12]"

    def test_velocity_matches_sgp4_output(self):
        model, _ = make_model()
        result = model.get_velocity_earth_general_inertial()
        assert result == pytest.approx(FAKE_VELOCITY_ECI_KMS)

    def test_velocity_uses_cache_populated_by_position_call(self):
        model, mock_orb = make_model()
        model.get_position_earth_general_inertial()
        mock_orb.get_position.reset_mock()
        model.get_velocity_earth_general_inertial()
        mock_orb.get_position.assert_not_called()

    def test_future_query_populates_cache(self):
        model, mock_orb = make_model()
        model.get_velocity_earth_general_inertial(delta_t=60.0)
        assert len(model._eci_cache) == 1
        mock_orb.get_position.assert_called_once()

        model.get_velocity_earth_general_inertial(delta_t=60.0)
        mock_orb.get_position.assert_called_once()  # still once


# ---------------------------------------------------------------------------
# is_ascending
# ---------------------------------------------------------------------------


class TestIsAscending:

    def test_ascending_when_z_velocity_positive(self):
        model, mock_orb = make_model()
        mock_orb.get_position.return_value = (
            FAKE_POSITION_ECI_KM,
            (0.0, 0.0, 1.0),
        )
        assert model.is_ascending() is True

    def test_descending_when_z_velocity_negative(self):
        model, mock_orb = make_model()
        mock_orb.get_position.return_value = (
            FAKE_POSITION_ECI_KM,
            (0.0, 0.0, -1.0),
        )
        assert model.is_ascending() is False

    def test_returns_bool(self):
        model, _ = make_model()
        assert isinstance(model.is_ascending(), bool)


# ---------------------------------------------------------------------------
# Cross-cache independence & helpers
# ---------------------------------------------------------------------------


class TestCacheIndependence:

    def test_lonlatalt_cache_and_eci_cache_are_independent(self):
        model, mock_orb = make_model()

        model.get_longitude_latitude_altitude()
        lonlatalt_calls = mock_orb.get_lonlatalt.call_count

        model.get_position_earth_general_inertial()

        model.get_longitude_latitude_altitude()  # must still hit lonlatalt cache
        assert mock_orb.get_lonlatalt.call_count == lonlatalt_calls

    def test_eci_cache_not_polluted_by_lonlatalt_call(self):
        model, _ = make_model()
        model.get_longitude_latitude_altitude()
        assert model._eci_cache == {}

    def test_clear_caches(self):
        model, _ = make_model()
        model.get_longitude_latitude_altitude()
        model.get_position_earth_general_inertial()
        assert len(model._lonlatalt_cache) == 1
        assert len(model._eci_cache) == 1

        model.clear_caches()
        assert model._lonlatalt_cache == {}
        assert model._eci_cache == {}

    def test_cache_stats(self):
        model, _ = make_model()
        assert model.cache_stats() == {"lonlatalt": 0, "eci": 0}

        model.get_longitude_latitude_altitude()
        model.get_position_earth_general_inertial(delta_t=10.0)
        stats = model.cache_stats()
        assert stats["lonlatalt"] == 1
        assert stats["eci"] == 1


class TestPurgeOnClockAdvance:

    def test_future_entry_survives_until_clock_passes_it(self):
        now = datetime.datetime(2024, 1, 1, 12, 0, 0)
        model, mock_orb = make_model(now)

        # cache a point 60 s in the future
        model.get_position_earth_general_inertial(delta_t=60.0)
        future_t = now + datetime.timedelta(seconds=60)
        assert future_t in model._eci_cache

        # advance clock by 30 s — future entry must still be present
        model.clock.get_current_time.return_value = now + datetime.timedelta(seconds=30)
        model.get_position_earth_general_inertial(delta_t=0.0)  # triggers purge
        assert future_t in model._eci_cache
        assert len(model._eci_cache) == 2  # now + future

        # advance past the future entry
        model.clock.get_current_time.return_value = now + datetime.timedelta(seconds=61)
        model.get_position_earth_general_inertial(delta_t=0.0)
        assert future_t not in model._eci_cache
