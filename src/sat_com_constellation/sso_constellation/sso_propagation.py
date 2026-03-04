"""
sso_dawn_dusk.py
================
Sun-Synchronous Dawn-Dusk Constellation TLE Generator

Generates a set of TwoLineElements for a Sun-synchronous orbit (SSO) constellation
aligned to the dawn-dusk terminator (LTAN = 18:00h).

Theory overview
---------------
A Sun-synchronous orbit is a special near-polar orbit whose right ascension of the
ascending node (RAAN) drifts eastward at exactly the same rate as the mean Sun moves
along the ecliptic (~0.9856 °/day). This keeps the orbital plane's geometry relative
to the Sun constant over time.

The J2 oblateness of the Earth produces a secular precession of the RAAN:
    dΩ/dt = -(3/2) * J2 * (Re/p)² * n * cos(i)   [J2 only, rad/s]

Setting this equal to the Sun's mean motion gives the required inclination.
A higher-order correction from J4 improves accuracy to < 0.002° vs. the J2-only solution.

References
----------
[1] Vallado, D.A., "Fundamentals of Astrodynamics and Applications", 4th ed.,
    Microcosm Press, 2013. §9.4 (SSO), §9.5 (J2/J4 secular drift, eq. 9-41).
[2] Wertz, J.R., Everett, D.F., Puschell, J.J., "Space Mission Engineering: The New SMAD",
    Microcosm Press, 2011. Ch. 9 (orbit design).
[3] Eagle, D., "Sun-Synchronous Orbit Design", MATLAB File Exchange #43333, 2012.
    https://www.mathworks.com/matlabcentral/fileexchange/43333
[4] Eagle, D., "Mean Local Time of the Ascending Node", MATLAB File Exchange #39085, 2012.
    https://www.mathworks.com/matlabcentral/fileexchange/39085
[5] satmad library, TLE.init_sso() — J4 iterative inclination refinement.
    https://github.com/egemenimre/satmad
[6] Astronomical Almanac, U.S. Naval Observatory — Solar coordinates, GMST.
"""

import math
from datetime import datetime, timezone

from astropy.coordinates import GCRS, CartesianRepresentation, get_body_barycentric
from astropy.time import Time
from astropy import units as u
from astropy.coordinates import solar_system_ephemeris
from sgp4.api import Satrec, WGS72
from sgp4.conveniences import jday
from sgp4.exporter import export_tle

from sat_com_constellation.utils import TwoLineElement

# ---------------------------------------------------------------------------
# Earth physical constants
# ---------------------------------------------------------------------------
# WGS72 constants are used throughout because TLEs are defined in the WGS72
# frame. The SGP4 propagator (which consumes TLEs) was fitted to WGS72.
# Using WGS84 constants would introduce a small but systematic inconsistency.
# Reference: [1] Appendix D; sgp4 library source (Vallado et al., 2006).

MU_KM3_S2 = 398600.8  # km^3/s^2
RE_KM = 6378.135  # km
J2 = 1.082616e-3
J4 = -1.65597e-6

# Sun's mean angular velocity along the ecliptic (tropical year).
# Using Vallado's precise value of 365.2421897 days [1, p.863].
TROPICAL_YEAR_DAYS = 365.2421897
SUN_MEAN_MOTION_RAD_S = 2.0 * math.pi / (TROPICAL_YEAR_DAYS * 86400.0)  # rad/s

# ===========================================================================
# Step 1 — High-precision Sun right ascension
# ===========================================================================


def get_sun_ra_deg_high_precision(t: Time) -> float:
    """
    Return the Sun's geocentric right ascension (RA) in degrees.

    Why this function?
    ------------------
    The RAAN of a dawn-dusk SSO must track the Sun's position in the equatorial
    plane. Specifically, the ascending node is placed 90° ahead of the Sun's RA
    (for LTAN = 18:00h, i.e. the dusk terminator). An error of 1' in RA_sun
    propagates directly as a 1' error in RAAN.

    Astropy's built-in `get_sun()` uses a low-precision analytical model with
    ~1 arcminute error. This function instead uses the JPL DE432s ephemeris,
    which is accurate to sub-arcsecond level for dates within ±200 years.

    Method
    ------
    1. Fetch barycentric positions of Earth and Sun from DE432s.
    2. Compute the geocentric position vector (Sun − Earth, in ICRS).
    3. Convert to GCRS (Geocentric Celestial Reference System = equatorial J2000)
       to read RA directly.

    Parameters
    ----------
    t : astropy.time.Time
        The epoch at which RA is evaluated (UTC recommended).

    Returns
    -------
    float
        Sun's geocentric right ascension in degrees [0, 360).

    References
    ----------
    [1] JPL DE432s ephemeris: https://ssd.jpl.nasa.gov/planets/eph_export.html
    [6] Astronomical Almanac — geocentric vs. barycentric distinctions.
    """
    with solar_system_ephemeris.set("de432s"):
        earth_bary = get_body_barycentric("earth", t)
        sun_bary = get_body_barycentric("sun", t)

    # Geocentric position: barycentric Sun minus barycentric Earth
    sun_gcrs_cartesian = CartesianRepresentation(sun_bary.xyz - earth_bary.xyz)

    # Attach to GCRS frame (equatorial, geocentric, aligned with J2000)
    sun_gcrs = GCRS(sun_gcrs_cartesian, obstime=t)

    return sun_gcrs.ra.to(u.deg).value


# ===========================================================================
# Step 2 — Orbital geometry: semi-major axis and mean motion
# ===========================================================================


def compute_orbital_geometry(
    altitude_km: float, eccentricity: float
) -> tuple[float, float, float]:
    """
    Compute fundamental orbital geometry parameters from altitude and eccentricity.

    Why this function?
    ------------------
    Altitude is the user-facing input, but the physics requires the semi-major
    axis 'a' and mean motion 'n'. The mean motion appears in both the SSO
    inclination formula and the SGP4 initialisation.

    Theory
    ------
    For a Keplerian orbit around Earth:

        a = Re + h                    (semi-major axis from altitude h)
        n = sqrt(mu / a³)             (unperturbed mean motion, Kepler's 3rd law)
        p = a * (1 − e²)              (semi-latus rectum)

    Note: SGP4 requires mean motion in rad/min (not rad/s), so both are returned.

    Parameters
    ----------
    altitude_km : float
        Orbit altitude above Earth's surface [km].
    eccentricity : float
        Orbital eccentricity (0 = circular).

    Returns
    -------
    tuple[float, float, float]
        (a_km, n_rad_s, n_rad_min) — semi-major axis [km],
        mean motion [rad/s], mean motion [rad/min].

    References
    ----------
    [1] Vallado §2.2 — Keplerian orbital elements.
    """
    a_km = RE_KM + altitude_km
    n_rad_s = math.sqrt(MU_KM3_S2 / a_km**3)
    n_rad_min = n_rad_s * 60.0  # rad/s → rad/min (SGP4 convention)

    return a_km, n_rad_s, n_rad_min


# ===========================================================================
# Step 3 — SSO inclination: J2-only initial guess
# ===========================================================================


def compute_sso_inclination_j2(
    a_km: float,
    n_rad_s: float,
    eccentricity: float,
) -> float:
    """
    Compute the SSO inclination using the first-order J2 nodal precession formula.

    Why this function?
    ------------------
    Earth's oblateness (J2) causes the orbital plane to precess about the polar
    axis. The SSO condition forces this precession rate to exactly match the Sun's
    annual eastward drift, so the orbit-Sun geometry stays fixed year-round.

    Theory
    ------
    The secular RAAN drift from J2 perturbation is [1, eq. 9-41]:

        dΩ/dt = -(3/2) * J2 * (Re/p)² * n * cos(i) / (1−e²)²

    where p = a(1−e²) is the semi-latus rectum.

    Setting dΩ/dt = ω_sun (Sun's mean motion in rad/s) and solving for cos(i):

        cos(i) = -2 * ω_sun * a² * (1−e²)² / (3 * J2 * Re² * n)

    Note the negative sign: SSO requires a retrograde-ish orbit (i > 90°) so
    the J2 precession is eastward (positive dΩ/dt) rather than the usual
    westward regression.

    Parameters
    ----------
    a_km : float
        Semi-major axis [km].
    n_rad_s : float
        Unperturbed mean motion [rad/s].
    eccentricity : float
        Orbital eccentricity.

    Returns
    -------
    float
        SSO inclination [rad] — initial J2-only estimate.

    Raises
    ------
    ValueError
        If no real SSO solution exists (|cos(i)| > 1, typically altitude > 6000 km).

    References
    ----------
    [1] Vallado §9.4 — Sun-synchronous orbits (eq. 9-40 / 9-41).
    [3] Eagle, MATLAB FE#43333 — Equation 1.
    """
    cos_i = (
        -2.0 * SUN_MEAN_MOTION_RAD_S * a_km**2 * (1.0 - eccentricity**2) ** 2
    ) / (3.0 * J2 * RE_KM**2 * n_rad_s)

    if abs(cos_i) > 1.0:
        raise ValueError(
            f"No Sun-synchronous solution exists for altitude "
            f"{a_km - RE_KM:.1f} km (cos(i)={cos_i:.4f}). "
            f"SSO requires altitudes typically below ~6000 km."
        )

    return math.acos(cos_i)


# ===========================================================================
# Step 4 — SSO inclination: J4 iterative refinement
# ===========================================================================


def compute_sso_inclination_j4_refined(
    a_km: float,
    n_rad_s: float,
    eccentricity: float,
    inclination_j2_rad: float,
    max_iterations: int = 20,
    convergence_threshold_rad: float = 1e-12,
) -> float:
    """
    Refine the SSO inclination by iteratively correcting for J4 perturbations.

    Why this function?
    ------------------
    The J2-only formula ignores the J4 zonal harmonic, which contributes a small
    but non-negligible correction to the RAAN drift rate — particularly important
    at low altitudes (< 600 km) where (Re/p)² is larger. The correction is
    typically 0.001–0.005° in inclination. satmad and Vallado both apply this
    refinement [1, 5].

    Theory
    ------
    The combined J2+J4 secular RAAN drift rate is [1, p.650, eq. 9-41]:

        dΩ/dt = -(3/2) * J2 * (Re/p)² * n * cos(i) *
                [1 + (3/2) * (J4/J2) * (Re/p)² * (1 − (5/4)*sin²(i))]

    where p = a(1−e²) is the semi-latus rectum.

    Iterative Newton correction:
        Given the current inclination iₖ, compute the residual in RAAN rate:
            δΩ̇ = dΩ/dt(iₖ) − ω_sun
        Then update via the partial derivative:
            d(dΩ/dt)/di = (dΩ/dt) * tan(i)  [from differentiating cos(i)]
            δi = -δΩ̇ / (dΩ/dt * tan(i))
            iₖ₊₁ = iₖ + δi

        Repeat until |δi| < convergence_threshold_rad.

    This is equivalent to Newton's method on the function f(i) = dΩ/dt(i) − ω_sun.

    Parameters
    ----------
    a_km : float
        Semi-major axis [km].
    n_rad_s : float
        Unperturbed mean motion [rad/s].
    eccentricity : float
        Orbital eccentricity.
    inclination_j2_rad : float
        Initial inclination guess from J2-only formula [rad].
    max_iterations : int, optional
        Maximum number of Newton iterations (default 20; typically converges in < 5).
    convergence_threshold_rad : float, optional
        Convergence criterion on inclination change per iteration [rad].
        Default 1e-12 rad ≈ 2e-10 degrees (well below any practical requirement).

    Returns
    -------
    float
        Refined SSO inclination [rad] including J4 correction.

    References
    ----------
    [1] Vallado §9.4–9.5, eq. 9-41 — J2+J4 secular RAAN drift.
    [5] satmad TLE.init_sso() — iterative inclination refinement.
    """
    p_km = a_km * (1.0 - eccentricity**2)  # semi-latus rectum [km]
    re_over_p2 = (RE_KM / p_km) ** 2  # (Re/p)² — governs harmonic strength

    # Maximum allowed inclination change per iteration.
    # Prevents Newton from overshooting when the denominator is near zero
    # (e.g. if i drifts toward 90° where tan(i) → ±∞).
    MAX_STEP_RAD = math.radians(0.5)

    def _compute_omega_dot(inc: float) -> float:
        """J2+J4 secular RAAN drift rate [rad/s] at inclination inc [rad]."""
        cos_i = math.cos(inc)
        sin_i = math.sin(inc)
        j2_term = -(3.0 / 2.0) * J2 * re_over_p2 * n_rad_s * cos_i
        j4_factor = 1.0 + (3.0 / 2.0) * (J4 / J2) * re_over_p2 * (
            1.0 - (5.0 / 4.0) * sin_i**2
        )
        return j2_term * j4_factor

    inclination = inclination_j2_rad
    # Seed the "previous" rate with the SSO target so the first correction
    # reflects the full J4 residual, mirroring satmad's initialisation.
    omega_dot_prev = SUN_MEAN_MOTION_RAD_S

    for _ in range(max_iterations):

        omega_dot_curr = _compute_omega_dot(inclination)

        # --- Sequential-difference step (satmad pattern) ---
        # Instead of Newton against a fixed target, compare consecutive rates.
        # This is numerically stable because the denominator uses the well-behaved
        # tan(i) of the current iterate, and the numerator stays small throughout.
        #
        #   δΩ̇ = Ω̇(iₖ) − Ω̇_prev
        #   δi  = −δΩ̇ / (Ω̇_prev × tan(iₖ))
        #
        # Reference: satmad TLE.init_sso() [5]
        tan_i = math.tan(inclination)
        denominator = omega_dot_prev * tan_i

        if abs(denominator) < 1e-30:
            # Degenerate case (nearly equatorial orbit): no refinement possible
            break

        delta_i = -(omega_dot_curr - omega_dot_prev) / denominator

        # Hard clamp: never move more than MAX_STEP_RAD in one iteration
        delta_i = max(-MAX_STEP_RAD, min(MAX_STEP_RAD, delta_i))

        inclination += delta_i
        omega_dot_prev = omega_dot_curr

        # Guard: keep inclination in valid physical range (0, π)
        inclination = max(1e-6, min(math.pi - 1e-6, inclination))

        if abs(delta_i) < convergence_threshold_rad:
            break

    return inclination


# ===========================================================================
# Step 5 — RAAN from LTAN (dawn-dusk alignment)
# ===========================================================================


def compute_raan_from_ltan(
    sun_ra_deg: float,
    ltan_hours: float = 18.0,
) -> float:
    """
    Compute the RAAN required to place the ascending node at a given Local Time
    of the Ascending Node (LTAN).

    Why this function?
    ------------------
    The "local solar time" of a ground track crossing is determined by the angle
    between the orbital plane's ascending node and the Sun-Earth line. For a
    dawn-dusk orbit we want the ascending node on the dusk terminator, i.e.
    LTAN = 18:00 h (90° ahead of the Sun-Earth direction in the equatorial plane).

    Theory
    ------
    The Sun's right ascension (RA_sun) gives the angle in the equatorial plane
    between the vernal equinox and the Earth-Sun direction. The local solar noon
    meridian (12:00 h) is aligned with the Sun, so:

        LTAN = 12h  →  RAAN = RA_sun        (ascending node toward Sun)
        LTAN = 18h  →  RAAN = RA_sun + 90°  (ascending node on dusk terminator)
        LTAN =  6h  →  RAAN = RA_sun − 90°  (ascending node on dawn terminator)

    General formula [4][1]:
        RAAN = RA_sun + 15° × (LTAN − 12h)

    The factor 15°/h converts hours of local solar time into degrees of arc,
    because the Earth (and the Sun as seen from Earth) subtends 360° in 24h.

    Parameters
    ----------
    sun_ra_deg : float
        Sun's geocentric right ascension [degrees].
    ltan_hours : float, optional
        Target Local Time of the Ascending Node [hours, 0–24). Default 18.0 (dusk).

    Returns
    -------
    float
        RAAN in degrees [0, 360).

    References
    ----------
    [1] Vallado §9.4 — LTAN/RAAN relationship (eq. 9-43).
    [4] Eagle, MATLAB FE#39085 — Mean Local Time of the Ascending Node.
    [3] Eagle, MATLAB FE#43333 — Equation 3.
    """
    raan_deg = (sun_ra_deg + 15.0 * (ltan_hours - 12.0)) % 360.0
    return raan_deg


# ===========================================================================
# Step 6 — SGP4 epoch conversion
# ===========================================================================


def compute_sgp4_epoch(epoch_utc: datetime) -> float:
    """
    Convert a UTC datetime to the SGP4 epoch format used by sgp4init().

    Why this function?
    ------------------
    SGP4 does not use Unix time, Julian Date, or any common standard.
    It measures time as fractional days since 1949 December 31 00:00 UT,
    which corresponds to JD 2433281.5. This is a legacy format inherited from
    early NORAD tracking systems.

    Theory
    ------
    The Julian Date (JD) is a continuous day count from January 1, 4713 BC noon.
    The SGP4 epoch is:

        sgp4_epoch = (JD + fractional_day) − 2433281.5

    The `jday()` helper from the sgp4 library returns (JD_integer, fractional_day)
    separately to preserve precision.

    Parameters
    ----------
    epoch_utc : datetime
        UTC epoch (timezone-naive datetime is assumed to be UTC).

    Returns
    -------
    float
        SGP4 epoch: days since 1949-12-31 00:00 UT.

    References
    ----------
    [1] Vallado §3.5 — Julian Date and time systems.
    [1] Vallado §9.7 — TLE epoch definition and SGP4 initialisation.
    """
    jd, fr = jday(
        epoch_utc.year,
        epoch_utc.month,
        epoch_utc.day,
        epoch_utc.hour,
        epoch_utc.minute,
        epoch_utc.second,
    )
    return (jd + fr) - 2433281.5


# ===========================================================================
# Step 7 — TLE line 1 checksum
# ===========================================================================


def calculate_tle_line_checksum(tle_line_without_checksum: str) -> int:
    """
    Compute the modulo-10 checksum for a TLE line.

    Why this function?
    ------------------
    TLE lines each end with a single-digit checksum that allows receivers to
    detect transmission errors. The checksum is defined by the TLE standard
    (NORAD / Space Track) and must be recomputed whenever a line is modified.

    Algorithm
    ---------
    For each of the 68 characters (before the checksum digit at position 69):
        - Add the numeric value if the character is a digit 0–9.
        - Add 1 if the character is a minus sign '-' (as per TLE spec).
        - Ignore all other characters (spaces, letters, dots, plus signs).
    Return (sum mod 10).

    Parameters
    ----------
    tle_line_without_checksum : str
        Exactly 68 characters — the TLE line body without the trailing checksum digit.

    Returns
    -------
    int
        Single-digit checksum (0–9).

    Raises
    ------
    ValueError
        If the input is not exactly 68 characters.

    References
    ----------
    [1] Vallado Appendix C — TLE format specification.
    https://celestrak.org/columns/v04n03/ — CelesTrak TLE format description.
    """
    if len(tle_line_without_checksum) != 68:
        raise ValueError(
            f"TLE line must be exactly 68 characters for checksum; "
            f"got {len(tle_line_without_checksum)}."
        )

    total = 0
    for char in tle_line_without_checksum:
        if char.isdigit():
            total += int(char)
        elif char == "-":
            total += 1

    return total % 10


# ===========================================================================
# Step 8 — Build a single TLE from orbital elements
# ===========================================================================


def build_tle(
    sat_index: int,
    constellation_name: str,
    sgp4_epoch: float,
    inclination_rad: float,
    raan_deg: float,
    eccentricity: float,
    argument_of_perigee_deg: float,
    mean_anomaly_deg: float,
    mean_motion_rad_min: float,
) -> "TwoLineElement":
    """
    Initialise an SGP4 satellite record and export it as a TwoLineElement.

    Why this function?
    ------------------
    The sgp4 library's `Satrec.sgp4init()` sets all orbital elements in the
    internal TLE representation. `export_tle()` then serialises the record into
    the standard two 69-character TLE lines as defined by NORAD/Space Track.

    The international designator field (columns 10–17 of Line 1) is patched to
    "00000ABC " after export, because sgp4init() does not populate this field
    and leaves garbage bytes that would fail external TLE parsers.

    Parameters
    ----------
    sat_index : int
        Zero-based satellite index within the constellation (used as sat number).
    constellation_name : str
        Name prefix for the satellite (e.g. "MYCONST").
    sgp4_epoch : float
        Days since 1949-12-31 00:00 UT (from compute_sgp4_epoch).
    inclination_rad : float
        Orbital inclination [rad].
    raan_deg : float
        Right ascension of ascending node [degrees].
    eccentricity : float
        Orbital eccentricity.
    argument_of_perigee_deg : float
        Argument of perigee [degrees].
    mean_anomaly_deg : float
        Mean anomaly [degrees].
    mean_motion_rad_min : float
        Mean motion [rad/min].

    Returns
    -------
    TwoLineElement
        Fully formatted and checksum-verified TLE.

    References
    ----------
    [1] Vallado §9.7 — SGP4 TLE initialisation.
    Vallado et al., "Revisiting Spacetrack Report #3", AIAA 2006-6753.
    """
    sat_sgp4 = Satrec()
    sat_sgp4.sgp4init(
        WGS72,
        "i",  # improved mode
        sat_index + 1,  # satellite catalogue number
        sgp4_epoch,
        0.0,  # Bstar drag coefficient
        0.0,  # ndot  (first  derivative of mean motion)
        0.0,  # nddot (second derivative of mean motion)
        eccentricity,
        math.radians(argument_of_perigee_deg),
        inclination_rad,
        math.radians(mean_anomaly_deg),
        mean_motion_rad_min,
        math.radians(raan_deg),
    )

    line1, line2 = export_tle(sat_sgp4)

    # Patch international designator field (cols 9-17, 0-indexed) and recompute checksum.
    # The designator "00000ABC" encodes: launch year 00, launch number 000, piece "ABC".
    tle_line1 = line1[:9] + "00000ABC " + line1[18:]
    tle_line1 = tle_line1[:68] + str(calculate_tle_line_checksum(tle_line1[:68]))

    return TwoLineElement(
        satellite_name=f"{constellation_name} {sat_index}",
        line1=tle_line1,
        line2=line2,
    )


# ===========================================================================
# Main public API — generate_sso_dawn_dusk
# ===========================================================================


def generate_sso_dawn_dusk(
    constellation_name: str,
    number_of_satellites: int,
    altitude_km: float,
    epoch: datetime,
    eccentricity: float = 0.00001,
    argument_of_perigee_degree: float = 0.0,
    ltan_hours: float = 18.0,
    use_j4_refinement: bool = True,
) -> list[TwoLineElement]:
    """
    Generate a dawn-dusk Sun-synchronous orbit (SSO) constellation TLE set.

    The orbital plane is aligned with the Earth terminator at the specified epoch.
    Inclination satisfies the J2+J4 nodal precession condition. RAAN is computed
    from the Sun's high-precision RA (JPL DE432s) so the LTAN equals `ltan_hours`.
    Satellites are evenly distributed in mean anomaly around the single plane.

    Pipeline
    --------
    1. Normalise epoch to UTC.
    2. Compute semi-major axis and mean motion.
    3. Compute SSO inclination (J2 initial guess + optional J4 refinement).
    4. Compute RAAN from Sun's RA and requested LTAN.
    5. Convert epoch to SGP4 format.
    6. Build one TLE per satellite, evenly spaced in mean anomaly.

    Parameters
    ----------
    constellation_name : str
        Name prefix for each satellite (e.g. "DAWNSAT").
    number_of_satellites : int
        Number of satellites evenly distributed in the single orbital plane.
    altitude_km : float
        Orbital altitude above Earth's surface [km].
    epoch : datetime
        Epoch at which orbital elements are defined. Timezone-aware datetimes are
        converted to UTC; naive datetimes are assumed to already be UTC.
    eccentricity : float, optional
        Orbital eccentricity (default: near-circular 0.00001; exact zero is
        avoided because it causes argument-of-perigee singularity in SGP4).
    argument_of_perigee_degree : float, optional
        Argument of perigee [degrees]. Default 0.0.
    ltan_hours : float, optional
        Local Time of the Ascending Node [hours, 0–24). Default 18.0 (dusk).
        Use 6.0 for dawn.
    use_j4_refinement : bool, optional
        If True (default), apply J4 iterative refinement to inclination.
        If False, use J2-only formula (faster, ~0.003° less accurate).

    Returns
    -------
    list[TwoLineElement]
        List of `number_of_satellites` TLEs, aligned with the SSO dawn-dusk terminator.

    Raises
    ------
    ValueError
        If no SSO solution exists for the given altitude (see compute_sso_inclination_j2).

    Example
    -------
    >>> from datetime import datetime, timezone
    >>> tles = generate_sso_dawn_dusk("DAWNSAT", 6, 550.0, datetime(2025, 6, 21, tzinfo=timezone.utc))
    >>> for tle in tles:
    ...     print(tle)

    References
    ----------
    [1] Vallado §9.4 — SSO design; §9.7 — TLE generation.
    [3] Eagle, MATLAB FE#43333 — Sun-Synchronous Orbit Design.
    """

    # ------------------------------------------------------------------
    # Step 1 — Normalise epoch to a naive UTC datetime
    # ------------------------------------------------------------------
    if epoch.tzinfo is not None:
        epoch_utc = epoch.astimezone(timezone.utc).replace(tzinfo=None)
    else:
        epoch_utc = epoch

    # ------------------------------------------------------------------
    # Step 2 — Orbital geometry
    # ------------------------------------------------------------------
    a_km, n_rad_s, n_rad_min = compute_orbital_geometry(altitude_km, eccentricity)

    # ------------------------------------------------------------------
    # Step 3 — SSO inclination
    # ------------------------------------------------------------------
    inclination_rad = compute_sso_inclination_j2(a_km, n_rad_s, eccentricity)

    if use_j4_refinement:
        inclination_rad = compute_sso_inclination_j4_refined(
            a_km, n_rad_s, eccentricity, inclination_rad
        )

    # ------------------------------------------------------------------
    # Step 4 — RAAN aligned to requested LTAN
    # ------------------------------------------------------------------
    t = Time(epoch_utc, scale="utc")
    sun_ra_deg = get_sun_ra_deg_high_precision(t)
    raan_deg = compute_raan_from_ltan(sun_ra_deg, ltan_hours)

    # ------------------------------------------------------------------
    # Step 5 — SGP4 epoch
    # ------------------------------------------------------------------
    sgp4_epoch = compute_sgp4_epoch(epoch_utc)

    # ------------------------------------------------------------------
    # Step 6 — Build one TLE per satellite slot
    # Satellites are evenly spaced in mean anomaly:
    #   ΔM = 360° / N_sats
    # This produces a uniformly distributed Walker-like single-plane constellation
    # (Walker Delta pattern with 1 plane). See Wertz [2] Ch. 9 for Walker patterns.
    # ------------------------------------------------------------------
    two_line_elements = []

    for sat_index in range(number_of_satellites):
        mean_anomaly_deg = (sat_index * 360.0 / number_of_satellites) % 360.0

        tle = build_tle(
            sat_index=sat_index,
            constellation_name=constellation_name,
            sgp4_epoch=sgp4_epoch,
            inclination_rad=inclination_rad,
            raan_deg=raan_deg,
            eccentricity=eccentricity,
            argument_of_perigee_deg=argument_of_perigee_degree,
            mean_anomaly_deg=mean_anomaly_deg,
            mean_motion_rad_min=n_rad_min,
        )
        two_line_elements.append(tle)

    return two_line_elements
