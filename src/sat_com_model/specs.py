from sat_com_model.model import GroundStationLink, GroundStation


def ground_station_link_is_connected_to_ground_station(
    ground_station_link: GroundStationLink, ground_station_object_id: int
) -> bool:
    source = ground_station_link.source
    destination = ground_station_link.destination

    if isinstance(source, GroundStation):
        return source.object_id == ground_station_object_id
    elif isinstance(destination, GroundStation):
        return destination.object_id == ground_station_object_id
    else:
        raise ValueError("This ground station link is corrupted")
