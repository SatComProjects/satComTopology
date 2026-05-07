from sat_com_builder.ground_objects.utils import generate_ground_object_from_file
from sat_com_model.models import (
    GroundObjectDomain,
    PointOfPresence,
    create_point_of_presence,
)


def generate_point_of_presences(
    point_of_presence_file_path: str, ground_object_domain: GroundObjectDomain = None
) -> list[PointOfPresence]:
    """
    Reads point of presences from the input file.

    :param ground_object_domain: Ground object domain to use.
    :param point_of_presence_file_path: Filename of point of presences basic (typically /path/to/point_of_presences.txt)

    :return: List of point of presences
    """
    point_of_presences = list()
    point_of_presences_objects = generate_ground_object_from_file(
        point_of_presence_file_path
    )

    for point_of_presence_object in point_of_presences_objects:
        ground_station = create_point_of_presence(
            point_of_presence_object.id, ground_object_domain.identifier
        )
        ground_station.set_position(
            longitude=point_of_presence_object.longitude,
            latitude=point_of_presence_object.latitude,
            altitude=point_of_presence_object.altitude,
        )
        ground_station.ground_object_domain = ground_object_domain
        ground_station.label = point_of_presence_object.label
        point_of_presence_object.append(ground_station)

    return point_of_presences
