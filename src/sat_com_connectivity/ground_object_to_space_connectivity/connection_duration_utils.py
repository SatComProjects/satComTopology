import datetime
import logging
import math

import numpy as np

from sat_com_connectivity.utils import (
    get_elevation_angle,
    latitude_longitude_altitude_to_x_y_z,
)
from sat_com_model.constants import (
    KM_TO_METER,
    OMEGA_EARTH,
    GMST_RATE_DEG_PER_DAY,
    GMST_J2000_DEG,
    SECONDS_PER_DAY,
)
from sat_com_model.models import GroundObject, Satellite


def _gmst(t: datetime.datetime) -> float:
    """Approximate Greenwich Mean Sidereal Time (radians)."""
    # J2000.0 epoch
    j2000 = datetime.datetime(2000, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
    if t.tzinfo is None:
        t = t.replace(tzinfo=datetime.timezone.utc)
    d = (t - j2000).total_seconds() / SECONDS_PER_DAY
    # IAU 1982 approximation
    theta = math.radians(GMST_J2000_DEG + GMST_RATE_DEG_PER_DAY * d) % (2 * math.pi)
    return theta


def _ecef_to_eci(r_ecef: np.ndarray, gmst: float) -> np.ndarray:
    """Rotate ECEF → ECI via GMST."""
    c, s = math.cos(gmst), math.sin(gmst)
    R = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
    return R @ r_ecef


def _elevation_rate(
    r_sat_eci: np.ndarray,
    v_sat_eci: np.ndarray,
    r_gnd_eci: np.ndarray,
) -> tuple[float, float]:
    """
    Returns (elevation_deg, elevation_rate_deg_per_s) from ECI state vectors.

    Uses:
        ρ     = r_sat - r_gnd              (topocentric ECI vector)
        ρ_dot = v_sat - v_gnd             (v_gnd = ω_E × r_gnd)
        ẑ     = r_gnd / |r_gnd|           (local zenith in ECI)

        sin(el)   = dot(ρ, ẑ) / |ρ|
        d(el)/dt  = [dot(ρ_dot, ẑ)|ρ| - dot(ρ, ẑ) dot(ρ, ρ_dot)/|ρ|] / (|ρ|² cos(el))
    """
    omega = np.array([0.0, 0.0, OMEGA_EARTH])
    v_gnd = np.cross(omega, r_gnd_eci)

    rho = r_sat_eci - r_gnd_eci
    rho_dot = v_sat_eci - v_gnd

    rho_norm = np.linalg.norm(rho)
    z_hat = r_gnd_eci / np.linalg.norm(r_gnd_eci)

    sin_el = np.dot(rho, z_hat) / rho_norm
    sin_el = np.clip(sin_el, -1.0, 1.0)
    el_rad = math.asin(sin_el)
    cos_el = math.cos(el_rad)

    if abs(cos_el) < 1e-9:  # satellite at zenith — rate undefined
        return math.degrees(el_rad), 0.0

    numerator = (
        np.dot(rho_dot, z_hat) * rho_norm
        - np.dot(rho, z_hat) * np.dot(rho, rho_dot) / rho_norm
    )
    d_el_dt = numerator / (rho_norm**2 * cos_el)  # rad/s

    return math.degrees(el_rad), math.degrees(d_el_dt)


def estimate_time_until_disconnection(
    ground_object: GroundObject,
    satellite: Satellite,
    tol: float = 1,
    max_time: float = 3600.0,
) -> float:
    """
    Estimate the time remaining until the satellite drops below minimum_elevation
    as seen from the ground station.

    Parameters
    ----------
    minimum_elevation : float
        Minimum elevation angle in degrees.
    tol : float
        Convergence tolerance in seconds.
    max_time : float
        Search horizon in seconds.

    Returns
    -------
    float
        Time until disconnection in seconds, in [0, max_time].
        :param max_time:
        :param tol:
        :param minimum_elevation:
        :param satellite:
        :param ground_object:
    """
    minimum_elevation = ground_object.ground_object_domain.elevation_above_horizon

    now = satellite.get_movement_model().get_datetime()

    gnd_lat, gnd_lon, gnd_alt = (
        ground_object.get_coordinates().to_latitude_longitude_altitude()
    )

    # Ground station ECEF (km) — WGS72, consistent with SGP4/TLE frame
    r_gnd_ecef = (
        np.array(latitude_longitude_altitude_to_x_y_z(gnd_lat, gnd_lon, gnd_alt))
        / KM_TO_METER
    )

    def _gnd_eci_at(delta_t: float) -> np.ndarray:
        return _ecef_to_eci(
            r_gnd_ecef, _gmst(now + datetime.timedelta(seconds=delta_t))
        )

    def elev_at(delta_t: float) -> float:
        spatial_position = (
            satellite.get_movement_model().get_longitude_latitude_altitude(delta_t)
        )

        return get_elevation_angle(
            sat_coordinates=(
                spatial_position.latitude,
                spatial_position.longitude,
                spatial_position.altitude,
            ),
            gnd_coordinates=(gnd_lat, gnd_lon, gnd_alt),
        )

    def elev_rate_at(delta_t: float) -> float:
        """
        Elevation rate (deg/s) from ECI state vectors — used only for the
        Newton-Raphson derivative, not for the elevation value itself.
        """
        r_sat = np.array(
            satellite.movement_model.get_position_earth_general_inertial(delta_t)
        )
        v_sat = np.array(
            satellite.movement_model.get_velocity_earth_general_inertial(delta_t)
        )
        _, rate = _elevation_rate(r_sat, v_sat, _gnd_eci_at(delta_t))
        return rate

    def elev_and_rate_at(delta_t: float) -> tuple[float, float]:
        return elev_at(delta_t), elev_rate_at(delta_t)

    # Check current elevation
    current_elev, current_rate = elev_and_rate_at(0.0)
    if current_elev < minimum_elevation:
        raise ValueError(
            f"Satellite {satellite.satellite_name} is already below minimum elevation "
            f"of {minimum_elevation}° (current: {current_elev:.2f}°)."
        )

    # Smart initial estimate from elevation rate
    if current_rate < 0:
        t_guess = min((current_elev - minimum_elevation) / abs(current_rate), max_time)
    else:
        t_guess = max_time
        for t_scan in range(60, int(max_time) + 1, 60):
            e, r = elev_and_rate_at(float(t_scan))
            if e < minimum_elevation:
                t_guess = float(t_scan)
                break
            if r < 0:
                t_guess = min(t_scan + (e - minimum_elevation) / abs(r), max_time)
                break

    if t_guess >= max_time and elev_at(max_time) > minimum_elevation:
        logging.warning(
            f"Satellite {satellite.satellite_name} stays above {minimum_elevation}° "
            f"for at least {max_time}s; returning {max_time}s."
        )
        return max_time

    # Build bracket around t_guess
    t_low = max(0.0, t_guess - 300.0)
    t_high = min(t_guess + 300.0, max_time)

    while elev_at(t_low) < minimum_elevation and t_low > 0.0:
        t_low = max(0.0, t_low - 60.0)
    while elev_at(t_high) > minimum_elevation and t_high < max_time:
        t_high = min(t_high + 120.0, max_time)

    if elev_at(t_high) > minimum_elevation:
        logging.warning(
            f"Satellite {satellite.satellite_name} stays above {minimum_elevation}° "
            f"for at least {max_time}s; returning {max_time}s."
        )
        return max_time

    # Newton-Raphson with bisection fallback
    t = t_guess
    for _ in range(30):
        e, de_dt = elev_and_rate_at(t)

        dt = -(e - minimum_elevation) / de_dt if abs(de_dt) > 1e-9 else 0.0
        t_new = t + dt

        # Clamp to bracket if Newton escapes
        if not (t_low < t_new < t_high):
            t_new = 0.5 * (t_low + t_high)

        if e > minimum_elevation:
            t_low = t
        else:
            t_high = t

        t = t_new
        if abs(dt) < tol:
            break

    return t
