import math

EARTH_RADIUS_KM = 6378.135

KM_TO_METER = 1000

EARTH_RADIUS_METERS = 6371 * KM_TO_METER

# km, semi-major axis
WGS84_A = 6378.137

# first eccentricity squared
WGS84_E2 = 6.69437999014e-3

# rad/s, Earth rotation rate
OMEGA_EARTH = 7.2921150e-5

# Tropical year Days
TROPICAL_YEAR_DAYS = 365.2421897


# Sun Mean Motion Ras S
SUN_MEAN_MOTION_RAD_S = 2.0 * math.pi / (TROPICAL_YEAR_DAYS * 86400.0)

# ---------------------------------------------------------------------------
# WGS72 constants are used throughout because TLEs are defined in the WGS72
# frame. The SGP4 propagator (which consumes TLEs) was fitted to WGS72.
# Using WGS84 constants would introduce a small but systematic inconsistency.
# Reference: [1] Appendix D; sgp4 library source (Vallado et al., 2006).

WGS72_A = 6378.135  # km  (vs WGS84: 6378.137)

WGS72_E2 = 6.6943799901414e-3  # (vs WGS84: 6.69437999014e-3)

MU_KM3_S2 = 398600.8  # km^3/s^2

RE_KM = 6378.135  # km

J2 = 1.082616e-3

J4 = -1.65597e-6


# GMST linear model — IAU 1982 (Aoki et al., 1982)
# Ref: Vallado, "Fundamentals of Astrodynamics and Applications", 4th ed., eq. 3-45
#      Aoki et al., "The new definition of Universal Time", A&A 105, 1982
GMST_J2000_DEG = 280.46061837  # GMST at J2000.0 epoch (2000 Jan 1, 12:00 TT), degrees
GMST_RATE_DEG_PER_DAY = (
    360.98564736629  # Earth sidereal rotation rate, degrees/solar day
)
#                                         # = 360° / 86164.09054s × 86400s/day

# seconds/day = 24h × 60min × 60s
SECONDS_PER_DAY = 86400.0


# IUGG mean Earth radius — spherical approximation only.
# Do NOT use in geodetic conversions; use WGS72 ellipsoid constants instead.
# Ref: Moritz, H., "Geodetic Reference System 1980", J. Geodesy, 2000
EARTH_MEAN_RADIUS_KM = 6371.009


ATMOSPHERE_EXCLUSION_ZONE_KM = 80.0
