import numpy as np

from sat_com_connectivity.ground_object_to_space_connectivity.visibility_angle_utils import (
    VisibleSatellite,
)
from sat_com_model.models import GroundObject


def get_best_visible_satellite_with_biggest_shell(
    visible_satellites: list["VisibleSatellite"],
) -> "VisibleSatellite | None":
    """
    Selects the best visible satellite, prioritizing:
      1. Shells with the largest total number of satellites
         (shell size = satellites_per_orbit_plane × orbit_plane_count)
      2. Highest elevation_above_horizon within that shell.
    Satellites are grouped by unique shell identity to avoid ambiguity.
    """
    if not visible_satellites:
        return None

    # Group satellites by their shell identity
    shell_to_visible_satellites: dict[int, list[VisibleSatellite]] = {}
    for vs in visible_satellites:
        shell_id = id(vs.satellite.shell)
        shell_to_visible_satellites.setdefault(shell_id, []).append(vs)

    # Select the highest-elevation satellite from each shell
    best_per_shell = []
    for sats in shell_to_visible_satellites.values():
        best_sat_in_shell = max(sats, key=lambda s: s.elevation_above_horizon)
        best_per_shell.append(best_sat_in_shell)

    # Select the one in the largest shell (tie-breaker: elevation)
    return max(
        best_per_shell,
        key=lambda s: (
            s.satellite.shell.amount_of_satellite_per_orbit_plane
            * s.satellite.shell.amount_of_orbit_plane,
            s.elevation_above_horizon,
        ),
        default=None,
    )


def get_best_visible_satellite_with_lowest_shell(
    visible_satellites: list["VisibleSatellite"],
) -> "VisibleSatellite | None":
    """
    Selects the best visible satellite, prioritizing:
      1. Higher mean_revolution_per_day (lower orbital altitude)
      2. Higher elevation_above_horizon (better visibility)
    Satellites are grouped by unique shell identity to avoid float comparison issues.
    """
    if not visible_satellites:
        return None

    shell_to_visible_satellites: dict[int, list[VisibleSatellite]] = {}
    for vs in visible_satellites:
        shell_id = id(vs.satellite.shell)
        shell_to_visible_satellites.setdefault(shell_id, []).append(vs)

    # Build a single list of one "best" satellite per shell (highest elevation in that shell)
    best_per_shell = []
    for sats in shell_to_visible_satellites.values():
        best_sat_in_shell = max(sats, key=lambda s: s.elevation_above_horizon)
        best_per_shell.append(best_sat_in_shell)

    # From those, pick the one with the largest mean_revolution_per_day (then elevation)
    return max(
        best_per_shell,
        key=lambda s: (
            s.satellite.shell.mean_revolution_per_day,
            s.elevation_above_horizon,
        ),
        default=None,
    )


def satellites_are_approaching(
    satellites: list[VisibleSatellite], ground_object: GroundObject
) -> bool:
    """
    Check if the satellite is approaching the ground object.
    """
    output = []
    for satellite in satellites:
        coordinates_satellite = (
            satellite.satellite.get_coordinates().to_latitude_longitude_altitude()
        )
        future_coordinates_satellite = (
            satellite.satellite.get_movement_model()
            .get_longitude_latitude_altitude(delta_t=10)
            .to_longitude_latitude_altitude()
        )

        angular_velocity_direction = [
            future_coordinates_satellite[1] - coordinates_satellite[0],
            future_coordinates_satellite[0] - coordinates_satellite[1],
        ]
        angular_velocity_direction = np.array(
            angular_velocity_direction
        ) / np.linalg.norm(angular_velocity_direction)

        coordinates_ground_object = (
            ground_object.get_coordinates().to_latitude_longitude_altitude()
        )

        difference_vector = [
            coordinate_ground_object - coordinate_satellite
            for coordinate_satellite, coordinate_ground_object in zip(
                coordinates_satellite[:2], coordinates_ground_object[:2]
            )
        ]

        difference_vector = np.array(difference_vector) / np.linalg.norm(
            difference_vector
        )

        dot_product = np.dot(angular_velocity_direction, difference_vector)

        if dot_product > 0:
            # The satellite is approaching the ground object
            output.append((satellite, dot_product))
    # Sort the output by angle in descending order

    output.sort(
        key=lambda x: x[1], reverse=True
    )  # Sort by angle (the higher the dot product, the closer the satellite is approaching the ground object)
    output = [satellite for satellite, _ in output]

    return output
