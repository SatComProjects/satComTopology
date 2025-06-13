import math

import numpy as np


def latitude_longitude_altitude_to_x_y_z(lat, lon, elev):
    """
    Method to convert latitude, longitude and elevation to cartesian coordinates
    :param lat: Latitude
    :param lon: Longitude
    :param elev: Elevation
    :return: Cartesian coordinates
    """
    R = 6378.137  # Radius of the Earth in km
    x = (R + elev) * math.cos(math.radians(lat)) * math.cos(math.radians(lon))
    y = (R + elev) * math.cos(math.radians(lat)) * math.sin(math.radians(lon))
    z = (R + elev) * math.sin(math.radians(lat))
    return x, y, z


def get_elevation_angle(
    sat_coordinates: tuple[float, float, float],
    gnd_coordinates: tuple[float, float, float],
) -> float:
    """
    Calculate the elevation angle from a ground station to a satellite.

    :param sat_coordinates: (lat, lon, alt) of satellite in degrees and meters
    :param gnd_coordinates: (lat, lon, alt) of ground station in degrees and meters
    :return: Elevation angle in degrees
    """
    # Convert both positions to ECEF
    sat_ecef = latitude_longitude_altitude_to_x_y_z(*sat_coordinates)
    gnd_ecef = latitude_longitude_altitude_to_x_y_z(*gnd_coordinates)

    # Vector from ground to satellite
    vector = np.array(sat_ecef) - np.array(gnd_ecef)

    # Convert ground coordinates to radians
    lat, lon = np.radians(gnd_coordinates[0]), np.radians(gnd_coordinates[1])

    # ENU basis vectors
    up = np.array([np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)])

    # Project vector onto "up" direction
    distance = np.linalg.norm(vector)
    elevation_rad = np.arcsin(np.dot(vector, up) / distance)

    return np.degrees(elevation_rad)
