"""
Ground-to-space geometry used by the connectivity computations.

Moved from `sat_com_trajectopy.angle_utils` (kept there as deprecated aliases).

Earth model: WGS72 ellipsoid everywhere, the frame of the TLEs and of the SGP4
propagator (see sat_com_model.constants). Positions are ECEF, in meters.
"""

import math

import numpy as np

from sat_com_model.constants import KM_TO_METER, WGS72_A, WGS72_E2


def latitude_longitude_altitude_to_x_y_z(
    lat: float, lon: float, elev: float
) -> tuple[float, float, float]:
    """
    Geodetic coordinates to ECEF cartesian coordinates, on the WGS72 ellipsoid.

    :param lat: Geodetic latitude, degrees
    :param lon: Longitude, degrees
    :param elev: Altitude above the ellipsoid, meters
    :return: (x, y, z) in meters
    """
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    sin_lat = math.sin(lat_rad)
    cos_lat = math.cos(lat_rad)

    semi_major_axis_m = WGS72_A * KM_TO_METER
    # Prime vertical radius of curvature
    n = semi_major_axis_m / math.sqrt(1.0 - WGS72_E2 * sin_lat**2)

    x = (n + elev) * cos_lat * math.cos(lon_rad)
    y = (n + elev) * cos_lat * math.sin(lon_rad)
    z = (n * (1.0 - WGS72_E2) + elev) * sin_lat
    return x, y, z


def ground_to_up_vector(gnd_coords: tuple[float, float, float]) -> np.ndarray:
    """
    Local 'up' unit vector at a ground location: the normal to the ellipsoid
    (geodetic vertical).

    :param gnd_coords: (lat, lon, alt) in degrees and meters
    """
    lat, lon = np.radians(gnd_coords[0]), np.radians(gnd_coords[1])
    return np.array(
        [
            np.cos(lat) * np.cos(lon),
            np.cos(lat) * np.sin(lon),
            np.sin(lat),
        ]
    )


def get_elevation_angle(
    sat_coordinates: tuple[float, float, float],
    gnd_coordinates: tuple[float, float, float],
) -> float:
    """
    Elevation angle from a ground station to a satellite.

    :param sat_coordinates: (lat, lon, alt) of satellite in degrees and meters
    :param gnd_coordinates: (lat, lon, alt) of ground station in degrees and meters
    :return: Elevation angle in degrees
    """
    return get_elevation_angle_and_distance(sat_coordinates, gnd_coordinates)[0]


def get_elevation_angle_and_distance(
    sat_coordinates: tuple[float, float, float],
    gnd_coordinates: tuple[float, float, float],
) -> tuple[float, float]:
    """
    Elevation angle from a ground station to a satellite, and the straight-line
    distance between them. Both come from the same ground-to-satellite vector.

    :param sat_coordinates: (lat, lon, alt) of satellite in degrees and meters
    :param gnd_coordinates: (lat, lon, alt) of ground station in degrees and meters
    :return: (elevation angle in degrees, distance in meters)
    """
    vector = np.array(
        latitude_longitude_altitude_to_x_y_z(*sat_coordinates)
    ) - np.array(latitude_longitude_altitude_to_x_y_z(*gnd_coordinates))

    distance = np.linalg.norm(vector)
    # Clipped: rounding can push a satellite at zenith slightly above 1 -> NaN.
    sin_elevation = np.clip(
        np.dot(vector, ground_to_up_vector(gnd_coordinates)) / distance, -1.0, 1.0
    )
    return np.degrees(np.arcsin(sin_elevation)), distance


def satellites_to_ecef(satellites: list) -> np.ndarray:
    """ECEF coordinates (meters) of every satellite, shape (N, 3)."""
    return np.array(
        [
            latitude_longitude_altitude_to_x_y_z(
                *sat.get_coordinates().to_latitude_longitude_altitude()
            )
            for sat in satellites
        ]
    )


def compute_elevations(
    sat_ecef: np.ndarray, gnd_ecef: np.ndarray, up: np.ndarray
) -> np.ndarray:
    """Elevation angles (degrees) of all satellites relative to a ground station."""
    return compute_elevations_and_distances(sat_ecef, gnd_ecef, up)[0]


def compute_elevations_and_distances(
    sat_ecef: np.ndarray, gnd_ecef: np.ndarray, up: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """
    Elevation angles (degrees) of all satellites relative to the ground station,
    and their straight-line distances (meters, same unit as the ECEF inputs).
    """
    vectors = sat_ecef - gnd_ecef
    distances = np.linalg.norm(vectors, axis=1)
    # Clipped: rounding can push a satellite at zenith slightly above 1 -> NaN.
    sin_elevations = np.clip((vectors @ up) / distances, -1.0, 1.0)
    return np.degrees(np.arcsin(sin_elevations)), distances
