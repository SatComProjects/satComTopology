from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from pydantic import BaseModel, Field

from sat_com_model.models import (
    Satellite,
    GroundObject,
    GroundToSpaceLink,
)
from sat_com_connectivity.utils import (
    get_elevation_angle_and_distance,
    latitude_longitude_altitude_to_x_y_z,
    ground_to_up_vector,
    satellites_to_ecef,
    compute_elevations_and_distances,
)

if TYPE_CHECKING:
    from sat_com_connectivity.satellite_state_cache import SatelliteStateCache


class VisibleSatellite(BaseModel):
    satellite: Satellite = Field(default=None)
    elevation_above_horizon: float = Field(default=None)
    """Straight-line ground-to-satellite distance, a by-product of the elevation."""
    distance_km: float | None = Field(default=None)


def get_visible_satellites(
    satellites: list[Satellite],
    ground_object: GroundObject,
    state_cache: SatelliteStateCache | None = None,
) -> list[VisibleSatellite]:
    """
    Vectorized computation of visible satellites for a single ground object.

    `state_cache`: when given, the satellite ECEF positions are computed once
    per time step and shared by every ground object.
    """

    if len(satellites) == 0:
        return []

    gnd_coords = ground_object.get_coordinates().to_latitude_longitude_altitude()
    gnd_ecef = np.array(latitude_longitude_altitude_to_x_y_z(*gnd_coords))
    up = ground_to_up_vector(gnd_coords)

    if state_cache is None:
        sat_ecef = satellites_to_ecef(satellites)
    else:
        sat_ecef = state_cache.ground_ecef(satellites)
    elevations, distances_m = compute_elevations_and_distances(sat_ecef, gnd_ecef, up)

    threshold = ground_object.ground_object_domain.elevation_above_horizon
    mask = elevations >= threshold

    return [
        VisibleSatellite(
            satellite=sat,
            elevation_above_horizon=elev,
            distance_km=float(distance_m) / 1000.0,
        )
        for sat, elev, distance_m, keep in zip(
            satellites, elevations, distances_m, mask
        )
        if keep
    ]


def check_and_update_elevation_if_satellite_is_visible(link: GroundToSpaceLink) -> bool:

    if isinstance(link.source, Satellite):
        ground_object = link.destination
        satellite = link.source
    else:
        ground_object = link.source
        satellite = link.destination

    elevation_angle, distance_m = get_elevation_angle_and_distance(
        sat_coordinates=satellite.get_coordinates().to_latitude_longitude_altitude(),
        gnd_coordinates=ground_object.get_coordinates().to_latitude_longitude_altitude(),
    )

    elevation_angle_is_still_valid = (
        elevation_angle >= ground_object.ground_object_domain.elevation_above_horizon
    )
    if elevation_angle_is_still_valid:
        link.elevation_above_horizon_angle = elevation_angle
        link.distance_km = float(distance_m) / 1000.0

        return True
    else:
        return False


def get_best_satellites_among_visible_satellites(
    ground_object: GroundObject,
    satellites: list[Satellite],
) -> VisibleSatellite | None:
    """
    Returns the satellite with the highest elevation angle from the list of visible satellites.
    """
    visible_satellites = get_visible_satellites(
        satellites=satellites, ground_object=ground_object
    )

    best_elevation = -1
    best = None
    for visible_satellite in visible_satellites:
        if visible_satellite.elevation_above_horizon > best_elevation:
            best_elevation = visible_satellite.elevation_above_horizon
            best = visible_satellite

    return (
        VisibleSatellite(
            satellite=best.satellite,
            elevation_above_horizon=best_elevation,
            distance_km=best.distance_km,
        )
        if best is not None and best.satellite
        else None
    )
