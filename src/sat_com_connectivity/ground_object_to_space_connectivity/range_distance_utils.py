from sat_com_model.models import GroundToSpaceLink, Satellite, DistanceModel


def check_and_update_distance_if_satellite_is_in_range(
    link: GroundToSpaceLink, distance_model: DistanceModel
) -> bool:

    if isinstance(link.source, Satellite):
        ground_object = link.destination
        satellite = link.source
    else:
        ground_object = link.source
        satellite = link.destination

    distance_between_two_object = distance_model.get_ground_distance_km(
        ground_object.spatial_position, satellite.spatial_position
    )

    link_is_still_valid = (
        distance_between_two_object
        <= ground_object.ground_object_domain.maximum_satellite_range_distance
    )

    return link_is_still_valid
