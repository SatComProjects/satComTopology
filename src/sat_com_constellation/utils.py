import math
from datetime import datetime, timezone

import astropy.units as u
from astropy.coordinates import (
    solar_system_ephemeris,
    get_body_barycentric,
    CartesianRepresentation,
    GCRS,
)
from astropy.time import Time
from pydantic import BaseModel
from sgp4.api import Satrec, WGS72
from sgp4.api import jday
from sgp4.exporter import export_tle

from sat_com_model.constants import J2, MU_KM3_S2, RE_KM


class TwoLineElement(BaseModel):
    satellite_name: str
    line1: str
    line2: str


def _get_sun_ra_deg_high_precision(t: Time) -> float:
    """
    Return the Sun's geocentric right ascension in degrees using the
    high-precision JPL DE432s ephemeris via astropy.

    This is significantly more accurate than get_sun() which uses a
    low-precision analytical model (~1 arcminute error). The JPL ephemeris
    is accurate to sub-arcsecond level.
    """
    with solar_system_ephemeris.set("de432s"):
        # Get barycentric positions of Earth and Sun
        earth_bary = get_body_barycentric("earth", t)
        sun_bary = get_body_barycentric("sun", t)

    # Geocentric position of the Sun (barycentric Sun - barycentric Earth)
    sun_gcrs_cartesian = CartesianRepresentation(sun_bary.xyz - earth_bary.xyz)

    # Convert to GCRS (Geocentric Celestial Reference System = equatorial frame)
    sun_gcrs = GCRS(sun_gcrs_cartesian, obstime=t)

    return sun_gcrs.ra.to(u.deg).value


def generate_sso_dawn_dusk(
    constellation_name: str,
    number_of_satellites: int,
    altitude_km: float,
    epoch: datetime,
    eccentricity: float = 0.00001,
    argument_of_perigee_degree: float = 0.0,
) -> list[TwoLineElement]:
    """
    Generate a dawn-dusk Sun-synchronous orbit (SSO) constellation aligned
    with the Earth terminator at the specified epoch.

    The orbit is constructed such that the ascending node occurs at
    18:00 local solar time (dusk). RAAN is solved from the Sun's right
    ascension using a high-precision JPL ephemeris.

    Parameters
    ----------
    constellation_name : str
        Name prefix for each satellite.
    number_of_satellites : int
        Number of satellites evenly distributed in the single orbital plane.
    altitude_km : float
        Orbital altitude above Earth's surface (km).
    epoch : datetime
        Epoch at which orbital elements are defined and alignment is enforced.
        Timezone-naive datetimes are assumed to be UTC.
    eccentricity : float, optional
        Orbital eccentricity (default near-circular).
    argument_of_perigee_degree : float, optional
        Argument of perigee (degrees).

    Returns
    -------
    list[TwoLineElement]
        Generated TLEs aligned with the dawn-dusk terminator.

    Raises
    ------
    ValueError
        If no Sun-synchronous solution exists for the given altitude.
    """

    # --- Normalize epoch to UTC ---
    if epoch.tzinfo is not None:
        epoch_utc = epoch.astimezone(timezone.utc).replace(tzinfo=None)
    else:
        epoch_utc = epoch

    # --- Earth constants (WGS72, consistent with SGP4) ---
    mu = MU_KM3_S2  # km^3/s^2
    Re = RE_KM  # km

    # --- Orbital geometry ---
    a = Re + altitude_km  # semi-major axis (km)
    e = eccentricity

    # Mean motion (rad/s), then converted to rad/min for sgp4init
    n_rad_s = math.sqrt(mu / a**3)
    mean_motion_rad_min = n_rad_s * 60.0  # rad/s → rad/min

    # --- SSO inclination from J2 nodal precession condition ---
    # Required precession: one full revolution per tropical year
    omega_dot_required = 2.0 * math.pi / (365.2422 * 86400.0)  # rad/s

    # First-order J2 nodal precession: dΩ/dt = -3/2 * J2 * (Re/a)^2 * n * cos(i) / (1-e^2)^2
    # Solving for cos(i):
    cos_i = (-2.0 * omega_dot_required * a**2 * (1.0 - e**2) ** 2) / (
        3.0 * J2 * Re**2 * n_rad_s
    )

    if abs(cos_i) > 1.0:
        raise ValueError(
            f"No Sun-synchronous solution exists for altitude={altitude_km} km. "
            f"Try a lower altitude (typically below ~6000 km)."
        )

    inclination_rad = math.acos(cos_i)

    # --- SGP4 epoch: days since 1949 December 31 00:00 UT (= JD 2433281.5) ---
    jd, fr = jday(
        epoch_utc.year,
        epoch_utc.month,
        epoch_utc.day,
        epoch_utc.hour,
        epoch_utc.minute,
        epoch_utc.second,
    )
    sgp4_epoch = (jd + fr) - 2433281.5

    # --- RAAN aligned to LTAN = 18:00 (dusk terminator) ---
    # Formula: RAAN = RA_sun + 15° × (LTAN - 12h)
    # At LTAN=18h: RAAN = RA_sun + 90°, placing the ascending node on the dusk terminator.
    t = Time(epoch_utc, scale="utc")
    sun_ra_deg = _get_sun_ra_deg_high_precision(t)
    ltan_hours = 18.0
    raan_deg = (sun_ra_deg + 15.0 * (ltan_hours - 12.0)) % 360.0

    # --- Generate one satellite per slot, evenly spaced in mean anomaly ---
    two_line_elements = []

    for sat_index in range(number_of_satellites):

        mean_anomaly_deg = (sat_index * 360.0 / number_of_satellites) % 360.0

        sat_sgp4 = Satrec()
        sat_sgp4.sgp4init(
            WGS72,
            "i",  # operation mode
            sat_index + 1,  # satellite number
            sgp4_epoch,  # days since 1949-12-31 00:00 UT
            0.0,  # bstar drag term
            0.0,  # ndot (first derivative of mean motion)
            0.0,  # nddot (second derivative of mean motion)
            eccentricity,  # eccentricity
            math.radians(argument_of_perigee_degree),  # argument of perigee (rad)
            inclination_rad,  # inclination (rad)
            math.radians(mean_anomaly_deg),  # mean anomaly (rad)
            mean_motion_rad_min,  # mean motion (rad/min)
            math.radians(raan_deg),  # RAAN (rad)
        )

        line1, line2 = export_tle(sat_sgp4)

        # Patch the international designator field (columns 9-16, 0-indexed)
        # while preserving the classification character at index 7.
        tle_line1 = line1[:9] + "00000ABC " + line1[18:]
        tle_line1 = tle_line1[:68] + str(calculate_tle_line_checksum(tle_line1[:68]))

        two_line_elements.append(
            TwoLineElement(
                satellite_name=f"{constellation_name} {sat_index}",
                line1=tle_line1,
                line2=line2,
            )
        )

    return two_line_elements


def calculate_tle_line_checksum(tle_line_without_checksum):
    if len(tle_line_without_checksum) != 68:
        raise ValueError("Must have exactly 68 characters")
    s = 0
    for i in range(len(tle_line_without_checksum)):
        if tle_line_without_checksum[i].isnumeric():
            s += int(tle_line_without_checksum[i])
        if tle_line_without_checksum[i] == "-":
            s += 1
    return s % 10
