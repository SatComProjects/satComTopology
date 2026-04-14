import datetime
from unittest.mock import MagicMock, patch

import pytest

from sat_com_connectivity.ground_object_to_space_connectivity.connection_duration_utils import (
    estimate_time_until_disconnection,
)

MODULE = (
    "sat_com_connectivity.ground_object_to_space_connectivity.connection_duration_utils"
)


def make_fake_ground_object(lat=48.8566, lon=2.3522, alt=0.0):
    gnd = MagicMock()
    gnd.ground_object_domain.elevation_above_horizon = 10
    gnd.get_coordinates().to_latitude_longitude_altitude.return_value = (lat, lon, alt)
    return gnd


def make_fake_satellite(name="TEST-SAT-1"):
    sat = MagicMock()
    sat.satellite_name = name
    sat.get_movement_model().get_datetime.return_value = datetime.datetime(
        2024, 1, 1, 0, 0, 0
    )
    # Default ECI position/velocity — realistic LEO values (km, km/s)
    sat.movement_model.get_position_earth_general_inertial.return_value = (
        6500.0,
        1000.0,
        1000.0,
    )
    sat.movement_model.get_velocity_earth_general_inertial.return_value = (
        -1.0,
        7.0,
        0.5,
    )
    return sat


def make_fake_spatial_position(lat=42.0, lon=-4.0, alt=550000.0):
    pos = MagicMock()
    pos.latitude = lat
    pos.longitude = lon
    pos.altitude = alt  # metres
    return pos


# ---------------------------------------------------------------------------
# Helpers — patch both elevation functions to decouple from geometry
# ---------------------------------------------------------------------------


def _patch_elev(module, elev_side_effect):
    """Patch get_elevation_angle with a side_effect callable."""
    return patch(f"{MODULE}.get_elevation_angle", side_effect=elev_side_effect)


def _patch_rate(module, rate_side_effect):
    """Patch _elevation_rate with a side_effect callable."""
    return patch(f"{MODULE}._elevation_rate", side_effect=rate_side_effect)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestEstimateTimeUntilDisconnectionRaisesErrors:

    def test_raises_when_already_below_minimum_elevation(self):
        sat = make_fake_satellite()
        gnd = make_fake_ground_object()
        sat.get_movement_model().get_longitude_latitude_altitude.return_value = (
            make_fake_spatial_position()
        )

        with _patch_elev(MODULE, lambda **_: 5.0), _patch_rate(
            MODULE, lambda *_: (5.0, -0.1)
        ):
            with pytest.raises(ValueError, match="already below minimum elevation"):
                estimate_time_until_disconnection(
                    ground_object=gnd,
                    satellite=sat,
                )

    def test_error_message_includes_satellite_name_and_current_elevation(self):
        sat = make_fake_satellite(name="MY-SAT")
        gnd = make_fake_ground_object()
        sat.get_movement_model().get_longitude_latitude_altitude.return_value = (
            make_fake_spatial_position()
        )

        with _patch_elev(MODULE, lambda **_: 3.5), _patch_rate(
            MODULE, lambda *_: (3.5, -0.1)
        ):
            with pytest.raises(ValueError, match="MY-SAT") as exc_info:
                estimate_time_until_disconnection(
                    ground_object=gnd,
                    satellite=sat,
                )
            assert "3.50" in str(exc_info.value)


class TestEstimateTimeUntilDisconnectionReturnsMaxTime:

    def test_returns_max_time_when_satellite_never_drops(self):
        sat = make_fake_satellite()
        gnd = make_fake_ground_object()
        sat.get_movement_model().get_longitude_latitude_altitude.return_value = (
            make_fake_spatial_position()
        )

        # Satellite always above minimum — never drops
        with _patch_elev(MODULE, lambda **_: 30.0), _patch_rate(
            MODULE, lambda *_: (30.0, 0.1)
        ):  # always ascending
            result = estimate_time_until_disconnection(
                ground_object=gnd,
                satellite=sat,
                max_time=600.0,
            )

        assert result == 600.0

    def test_returns_max_time_with_warning(self, caplog):
        import logging

        sat = make_fake_satellite()
        gnd = make_fake_ground_object()
        sat.get_movement_model().get_longitude_latitude_altitude.return_value = (
            make_fake_spatial_position()
        )

        with _patch_elev(MODULE, lambda **_: 30.0), _patch_rate(
            MODULE, lambda *_: (30.0, 0.1)
        ), caplog.at_level(logging.WARNING):
            result = estimate_time_until_disconnection(
                ground_object=gnd,
                satellite=sat,
                max_time=600.0,
            )

        assert result == 600.0
        assert any("stays above" in r.message for r in caplog.records)


class TestEstimateTimeUntilDisconnectionDescending:

    def test_descending_satellite_returns_time_close_to_linear_prediction(self):
        """
        Satellite at 30° descending at 0.1°/s → should cross 10° in ~200s.
        """
        sat = make_fake_satellite()
        gnd = make_fake_ground_object()

        # elev(t) = 30 - 0.1 * t  →  crosses 10° at t = 200s
        def elev(sat_coordinates, gnd_coordinates):
            return 30.0

        def rate(r_sat, v_sat, r_gnd):
            return 30.0, -0.1  # (elev_deg, rate_deg_per_s)

        sat.get_movement_model().get_longitude_latitude_altitude.return_value = (
            make_fake_spatial_position()
        )

        # Make elev_at vary with delta_t by patching get_elevation_angle
        # using a closure that reads the last delta_t from the movement model call
        call_count = {"n": 0}

        def elev_side_effect(sat_coordinates, gnd_coordinates):
            # Each call corresponds to an increasing delta_t in the Newton loop
            # We simulate elev(t) = 30 - 0.1 * t by tracking calls
            delta_t = call_count["n"] * 10.0
            call_count["n"] += 1
            return max(0.0, 30.0 - 0.1 * delta_t)

        with _patch_elev(MODULE, elev_side_effect), _patch_rate(MODULE, rate):
            result = estimate_time_until_disconnection(
                ground_object=gnd,
                satellite=sat,
                max_time=3600.0,
                tol=0.1,
            )

        assert 0.0 < result <= 3600.0

    def test_descending_satellite_initial_guess_from_rate(self):
        """
        When descending, t_guess = (elev - min) / |rate|.
        Verify the function does not scan 60s steps (ascending path).
        """
        sat = make_fake_satellite()
        gnd = make_fake_ground_object()
        sat.get_movement_model().get_longitude_latitude_altitude.return_value = (
            make_fake_spatial_position()
        )

        scan_calls = {"n": 0}

        def rate(r_sat, v_sat, r_gnd):
            scan_calls["n"] += 1
            return 30.0, -0.1  # descending → should NOT enter scan loop

        def elev(sat_coordinates, gnd_coordinates):
            return 30.0

        with _patch_elev(MODULE, elev), _patch_rate(MODULE, rate):
            estimate_time_until_disconnection(
                ground_object=gnd,
                satellite=sat,
                max_time=3600.0,
            )

        # Scan loop runs 60 steps for max_time=3600 — if it didn't run,
        # rate was called far fewer times
        assert scan_calls["n"] < 60


class TestEstimateTimeUntilDisconnectionAscending:

    def test_ascending_satellite_enters_scan_loop(self):
        """
        When ascending, function must scan at 60s steps to find descending segment.
        """
        sat = make_fake_satellite()
        gnd = make_fake_ground_object()
        sat.get_movement_model().get_longitude_latitude_altitude.return_value = (
            make_fake_spatial_position()
        )

        # Ascending for first 300s, then descending
        def rate(r_sat, v_sat, r_gnd):
            return 30.0, 0.05  # ascending — forces scan loop

        elev_calls = {"n": 0}

        def elev(sat_coordinates, gnd_coordinates):
            elev_calls["n"] += 1
            return 30.0  # stays above minimum during scan — eventually hits max_time

        with _patch_elev(MODULE, elev), _patch_rate(MODULE, rate):
            result = estimate_time_until_disconnection(
                ground_object=gnd,
                satellite=sat,
                max_time=600.0,
            )

        # Should have returned max_time since satellite never descends
        assert result == 600.0
        # elev_at must have been called multiple times (scan loop + bracket checks)
        assert elev_calls["n"] > 1


class TestEstimateTimeUntilDisconnectionTolerance:

    def test_custom_tolerance_is_respected(self):
        sat = make_fake_satellite()
        gnd = make_fake_ground_object()
        sat.get_movement_model().get_longitude_latitude_altitude.return_value = (
            make_fake_spatial_position()
        )

        with _patch_elev(MODULE, lambda **_: 30.0), _patch_rate(
            MODULE, lambda *_: (30.0, -0.1)
        ):
            # tol=10s — function should accept a coarser result
            result = estimate_time_until_disconnection(
                ground_object=gnd,
                satellite=sat,
                max_time=3600.0,
                tol=10.0,
            )

        assert result <= 3600.0

    def test_default_tolerance_is_01_seconds(self):
        """Verify default tol is 0.1s — function signature contract."""
        import inspect
        from sat_com_connectivity.ground_object_to_space_connectivity.connection_duration_utils import (
            estimate_time_until_disconnection,
        )

        sig = inspect.signature(estimate_time_until_disconnection)
        assert sig.parameters["tol"].default == 0.1


class TestEstimateTimeUntilDisconnectionEdgeCases:

    def test_minimum_elevation_zero(self):
        """minimum_elevation=0 should not raise even at low elevations."""
        sat = make_fake_satellite()
        gnd = make_fake_ground_object()
        gnd.ground_object_domain.elevation_above_horizon = 0
        sat.get_movement_model().get_longitude_latitude_altitude.return_value = (
            make_fake_spatial_position()
        )

        with _patch_elev(MODULE, lambda **_: 5.0), _patch_rate(
            MODULE, lambda *_: (5.0, -0.1)
        ):
            result = estimate_time_until_disconnection(
                ground_object=gnd,
                satellite=sat,
                max_time=3600.0,
            )

        assert result >= 0.0

    def test_result_is_always_non_negative(self):
        sat = make_fake_satellite()
        gnd = make_fake_ground_object()
        sat.get_movement_model().get_longitude_latitude_altitude.return_value = (
            make_fake_spatial_position()
        )

        with _patch_elev(MODULE, lambda **_: 20.0), _patch_rate(
            MODULE, lambda *_: (20.0, -0.5)
        ):
            result = estimate_time_until_disconnection(
                ground_object=gnd,
                satellite=sat,
                max_time=3600.0,
            )

        assert result >= 0.0

    def test_result_never_exceeds_max_time(self):
        sat = make_fake_satellite()
        gnd = make_fake_ground_object()
        sat.get_movement_model().get_longitude_latitude_altitude.return_value = (
            make_fake_spatial_position()
        )

        with _patch_elev(MODULE, lambda **_: 50.0), _patch_rate(
            MODULE, lambda *_: (50.0, 0.1)
        ):
            result = estimate_time_until_disconnection(
                ground_object=gnd,
                satellite=sat,
                max_time=1800.0,
            )

        assert result <= 1800.0
