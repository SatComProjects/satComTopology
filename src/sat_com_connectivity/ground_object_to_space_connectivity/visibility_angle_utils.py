from typing import List

from pydantic import BaseModel, Field

from sat_com_model.models import (
    Satellite,
    GroundObject,
    GroundToSpaceLink,
)
from sat_com_trajectopy.angle_utils import get_elevation_angle


class VisibleSatellite(BaseModel):
    satellite: Satellite = Field(default=None)
    elevation_above_horizon: float = Field(default=None)


def get_visible_satellites(
    satellites: List[Satellite], ground_object: GroundObject
) -> List[VisibleSatellite]:

    visible_satellites = []
    for satellite in satellites:
        elev = get_elevation_angle(
            sat_coordinates=satellite.get_coordinates().to_latitude_longitude_altitude(),
            gnd_coordinates=ground_object.get_coordinates().to_latitude_longitude_altitude(),
        )
        if elev >= ground_object.ground_object_domain.elevation_above_horizon:
            visible_satellites.append(
                VisibleSatellite(satellite=satellite, elevation_above_horizon=elev)
            )
    return visible_satellites


def check_and_update_elevation_if_satellite_is_visible(link: GroundToSpaceLink) -> bool:

    if isinstance(link.source, Satellite):
        ground_object = link.destination
        satellite = link.source
    else:
        ground_object = link.source
        satellite = link.destination

    elevation_angle = get_elevation_angle(
        sat_coordinates=satellite.get_coordinates().to_latitude_longitude_altitude(),
        gnd_coordinates=ground_object.get_coordinates().to_latitude_longitude_altitude(),
    )

    elevation_angle_is_still_valid = (
        elevation_angle >= ground_object.ground_object_domain.elevation_above_horizon
    )
    if elevation_angle_is_still_valid:
        link.elevation_above_horizon_angle = elevation_angle

        return True
    else:
        return False


def get_best_satellites_among_visible_satellites(
    ground_object: GroundObject,
    satellites: List[Satellite],
) -> VisibleSatellite | None:
    """
    Returns the satellite with the highest elevation angle from the list of visible satellites.
    """
    visible_satellites = get_visible_satellites(
        satellites=satellites, ground_object=ground_object
    )

    best_elevation = -1
    best_satellite = None
    for visible_satellite in visible_satellites:
        if visible_satellite.elevation_above_horizon > best_elevation:
            best_elevation = visible_satellite.elevation_above_horizon
            best_satellite = visible_satellite.satellite

    return (
        VisibleSatellite(
            satellite=best_satellite, elevation_above_horizon=best_elevation
        )
        if best_satellite
        else None
    )
