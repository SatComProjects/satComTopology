from typing import List

from pydantic import BaseModel, Field
from telecom_lib.utils import get_elevation_angle

from sat_com_model.models import (
    Satellite,
    GroundObject,
)


class VisibleSatellite(BaseModel):
    satellite: Satellite = Field(default=None)
    elevation_above_horizon: float = Field(default=None)


def get_visible_satellites(
    satellites: List[Satellite], ground_object: GroundObject
) -> List[VisibleSatellite]:

    visible_satellites = []
    for satellite in satellites:
        elev = get_elevation_angle(
            satellite.get_coordinates().to_latitude_longitude_altitude(),
            ground_object.get_coordinates().to_latitude_longitude_altitude(),
        )
        if elev >= ground_object.ground_object_domain.elevation_above_horizon:
            visible_satellites.append(
                VisibleSatellite(satellite=satellite, elevation_above_horizon=elev)
            )
    return visible_satellites
