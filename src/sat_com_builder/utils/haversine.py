from math import radians, cos, sqrt, atan2, sin


def haversine_distance_space(point1, point2) -> float:
    """
    Calculate the haversine distance between two points in meters.

    Parameters:
    - point1: (longitude1, latitude1, altitude1)
    - point2: (longitude2, latitude2, altitude2)

    Returns:
    - Distance in meters.
    """
    # Radius of the Earth in meters
    R = 6371000.0

    # Convert latitude and longitude from degrees to radians
    lon1, lat1, alt1 = map(radians, point1)
    lon2, lat2, alt2 = map(radians, point2)

    # Differences in coordinates
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    dalt = alt2 - alt1

    # Haversine formula
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    # Calculate the distance
    distance = R * c

    # Add altitude difference
    distance = sqrt(distance**2 + dalt**2)

    return distance
