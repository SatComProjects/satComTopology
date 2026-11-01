from sat_com_builder.factories import DefaultGroundStationFactory
from sat_com_builder.ground_objects.utils import generate_ground_object_from_file
from sat_com_builder.models import GroundObjectData
from sat_com_model.factories import AbstractGroundStationFactory
from sat_com_model.models import GroundStation, GroundObjectDomain


def generate_ground_stations_from_ground_objects(
    ground_objects: list[GroundObjectData],
    ground_object_domain: GroundObjectDomain = None,
    factory: AbstractGroundStationFactory = None,
) -> list[GroundStation]:
    """
    Build ground stations from ground object data.

    :param ground_objects: Ground object data (id, label, position).
    :param ground_object_domain: Ground object domain to use.
    :param factory: Factory used to build each ground station. Defaults to DefaultGroundStationFactory.
    :return: List of ground stations
    """
    factory = factory or DefaultGroundStationFactory()
    return [
        factory.create_ground_station(
            object_id=ground_object.id,
            label=ground_object.label,
            longitude=ground_object.longitude,
            latitude=ground_object.latitude,
            altitude=ground_object.altitude,
            ground_object_domain=ground_object_domain,
        )
        for ground_object in ground_objects
    ]


def generate_ground_stations_from_file(
    ground_station_file_path: str,
    ground_object_domain: GroundObjectDomain = None,
    factory: AbstractGroundStationFactory = None,
) -> list[GroundStation]:
    """
    Reads ground stations from the input file.

    :param ground_object_domain: Ground object domain to use.
    :param ground_station_file_path: Filename of ground stations basic (typically /path/to/ground_stations.txt)
    :param factory: Factory used to build each ground station. Defaults to DefaultGroundStationFactory.

    :return: List of ground stations
    """
    return generate_ground_stations_from_ground_objects(
        generate_ground_object_from_file(ground_station_file_path),
        ground_object_domain=ground_object_domain,
        factory=factory,
    )
