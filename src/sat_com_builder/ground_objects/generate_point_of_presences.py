from sat_com_builder.factories import DefaultPointOfPresenceFactory
from sat_com_builder.ground_objects.utils import generate_ground_object_from_file
from sat_com_builder.models import GroundObjectData
from sat_com_model.factories import AbstractPointOfPresenceFactory
from sat_com_model.models import GroundObjectDomain, PointOfPresence


def generate_point_of_presences_from_ground_objects(
    ground_objects: list[GroundObjectData],
    ground_object_domain: GroundObjectDomain = None,
    factory: AbstractPointOfPresenceFactory = None,
) -> list[PointOfPresence]:
    """
    Build points of presence from ground object data.

    :param ground_objects: Ground object data (id, label, position).
    :param ground_object_domain: Ground object domain to use.
    :param factory: Factory used to build each point of presence. Defaults to DefaultPointOfPresenceFactory.
    :return: List of points of presence
    """
    factory = factory or DefaultPointOfPresenceFactory()
    return [
        factory.create_point_of_presence(
            object_id=ground_object.id,
            label=ground_object.label,
            longitude=ground_object.longitude,
            latitude=ground_object.latitude,
            altitude=ground_object.altitude,
            ground_object_domain=ground_object_domain,
        )
        for ground_object in ground_objects
    ]


def generate_point_of_presences(
    point_of_presence_file_path: str,
    ground_object_domain: GroundObjectDomain = None,
    factory: AbstractPointOfPresenceFactory = None,
) -> list[PointOfPresence]:
    """
    Reads point of presences from the input file.

    :param ground_object_domain: Ground object domain to use.
    :param point_of_presence_file_path: Filename of point of presences basic (typically /path/to/point_of_presences.txt)
    :param factory: Factory used to build each point of presence. Defaults to DefaultPointOfPresenceFactory.

    :return: List of point of presences
    """
    return generate_point_of_presences_from_ground_objects(
        generate_ground_object_from_file(point_of_presence_file_path),
        ground_object_domain=ground_object_domain,
        factory=factory,
    )
