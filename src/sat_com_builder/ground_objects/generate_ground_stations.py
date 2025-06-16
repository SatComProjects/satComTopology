from sat_com_builder.ground_objects.utils import generate_ground_object_from_file
from sat_com_model.models import (
    GroundStation,
    create_ground_station,
    GroundObjectDomain,
)


def generate_ground_stations_from_file(
    ground_station_file_path: str, ground_object_domain: GroundObjectDomain = None
) -> list[GroundStation]:
    """
    Reads ground stations from the input file.

    :param ground_object_domain: Ground object domain to use.
    :param ground_station_file_path: Filename of ground stations basic (typically /path/to/ground_stations.txt)

    :return: List of ground stations
    """
    ground_stations = list()

    ground_station_objects = generate_ground_object_from_file(ground_station_file_path)
    for ground_station_object in ground_station_objects:
        ground_station = create_ground_station(
            ground_station_object.id, ground_object_domain.identifier
        )
        ground_station.set_position(
            longitude=ground_station_object.longitude,
            latitude=ground_station_object.latitude,
            altitude=ground_station_object.altitude,
        )
        ground_station.ground_object_domain = ground_object_domain
        ground_station.label = ground_station_object.label
        ground_stations.append(ground_station)

    return ground_stations
