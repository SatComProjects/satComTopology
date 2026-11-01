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


def get_best_visible_satellite_from_white_list(
    visible_satellites: list["VisibleSatellite"],
    ground_object: GroundObject,
) -> "VisibleSatellite | None":
    """
    Selects the best visible satellite based on shell white list prioritization.

    If the white list is empty, returns the satellite with the highest elevation angle (no priority).
    If the white list has elements, iterates through the shells in order and returns the best satellite
    (highest elevation angle) from the first shell that has visible satellites.

    :param visible_satellites: List of visible satellites
    :param ground_object: Ground object with shells_whitelist in its domain
    :return: Best visible satellite according to white list rules, or None if no visible satellites
    """
    if not visible_satellites:
        return None

    # Get shell white lists from ground object domain
    shells_whitelist = (
        ground_object.ground_object_domain.shells_whitelist
        if ground_object.ground_object_domain
        else []
    )

    # If white list is empty, return satellite with highest elevation angle
    if not shells_whitelist:
        return max(visible_satellites, key=lambda s: s.elevation_above_horizon)

    # Filter visible satellites by shell identifier based on white list priority
    for shell_identifier in shells_whitelist:
        # Find all visible satellites in this shell
        satellites_in_shell = []
        for vs in visible_satellites:
            try:
                if (
                    vs.satellite
                    and vs.satellite.shell
                    and vs.satellite.shell.identifier == shell_identifier
                ):
                    satellites_in_shell.append(vs)
            except (AttributeError, TypeError):
                # Skip satellites with invalid shell structure
                pass

        # If we found satellites in this shell, return the one with highest elevation
        if satellites_in_shell:
            return max(satellites_in_shell, key=lambda s: s.elevation_above_horizon)

    # If no satellites found in any white listed shells, return None
    return None


def filter_visible_satellites_by_white_list(
    visible_satellites: list["VisibleSatellite"],
    ground_object: GroundObject,
) -> list["VisibleSatellite"]:
    """
    Filters visible satellites to only include those in the shell white list.

    If the white list is empty, returns all visible satellites (no filtering).
    If the white list has elements, returns only satellites that match shells in the white list,
    preserving the order of shells as they appear in the white list.

    :param visible_satellites: List of visible satellites
    :param ground_object: Ground object with shells_whitelist in its domain
    :return: Filtered list of visible satellites
    """
    if not visible_satellites:
        return []

    # Get shell white lists from ground object domain
    shells_whitelist = (
        ground_object.ground_object_domain.shells_whitelist
        if ground_object.ground_object_domain
        else []
    )

    # If white list is empty, return all visible satellites
    if not shells_whitelist:
        return visible_satellites

    # Filter satellites by white list, preserving order of white list
    filtered = []
    for shell_identifier in shells_whitelist:
        for vs in visible_satellites:
            if vs.satellite.shell and vs.satellite.shell.identifier == shell_identifier:
                filtered.append(vs)

    return filtered


def get_closest_visible_satellite_from_white_list(
    visible_satellites: list,  # list of Satellite or similar objects with shell attribute
    ground_object: GroundObject,
    distance_model,
) -> object | None:
    """
    Returns the closest satellite from the white list prioritized satellites.

    If the white list is empty, returns the closest satellite among all visible satellites.
    If the white list has elements, returns the closest satellite from the first shell in the white list
    that has visible satellites. If no satellites in that shell, tries the next shell, etc.

    :param visible_satellites: List of visible satellites
    :param ground_object: Ground object with shells_whitelist in its domain
    :param distance_model: Distance model to compute distances
    :return: Closest satellite according to white list rules, or None if no visible satellites
    """
    if not visible_satellites:
        return None

    # Get shell white lists from ground object domain
    shells_whitelist = (
        ground_object.ground_object_domain.shells_whitelist
        if ground_object.ground_object_domain
        else []
    )

    # If white list is empty, return the closest satellite among all
    if not shells_whitelist:
        closest = distance_model.k_closest(ground_object, visible_satellites, k=1)
        return closest[0] if closest else None

    # Filter satellites by shell identifier based on white list priority
    for shell_identifier in shells_whitelist:
        # Find all visible satellites in this shell
        satellites_in_shell = [
            vs
            for vs in visible_satellites
            if (
                vs
                and hasattr(vs, "shell")
                and vs.shell
                and hasattr(vs.shell, "identifier")
                and vs.shell.identifier == shell_identifier
            )
        ]

        # If we found satellites in this shell, return the closest one
        if satellites_in_shell:
            closest = distance_model.k_closest(ground_object, satellites_in_shell, k=1)
            if closest:
                return closest[0]

    # If no satellites found in any white listed shells, return None
    return None


def get_best_visible_satellite_from_white_list_unordered(
    visible_satellites: list["VisibleSatellite"],
    ground_object: GroundObject,
) -> "VisibleSatellite | None":
    """
    Selects the best visible satellite based on shell white list filtering (NO priority ordering).

    If the white list is empty, returns the satellite with the highest elevation angle.
    If the white list has elements, returns the best satellite (highest elevation)
    among ALL satellites from ALL white-listed shells (treats all shells equally).

    :param visible_satellites: List of visible satellites
    :param ground_object: Ground object with shells_whitelist in its domain
    :return: Best visible satellite from white-listed shells, or None if no visible satellites
    """
    if not visible_satellites:
        return None

    # Get shell white lists from ground object domain
    shells_whitelist = (
        ground_object.ground_object_domain.shells_whitelist
        if ground_object.ground_object_domain
        else []
    )

    # If white list is empty, return satellite with highest elevation angle
    if not shells_whitelist:
        return max(visible_satellites, key=lambda s: s.elevation_above_horizon)

    # Filter visible satellites by shell identifier (no ordering, treat all equally)
    satellites_in_white_list = []
    for vs in visible_satellites:
        try:
            if (
                vs.satellite
                and vs.satellite.shell
                and vs.satellite.shell.identifier in shells_whitelist
            ):
                satellites_in_white_list.append(vs)
        except (AttributeError, TypeError):
            # Skip satellites with invalid shell structure
            pass

    # If we found satellites in white list, return the one with highest elevation
    if satellites_in_white_list:
        return max(satellites_in_white_list, key=lambda s: s.elevation_above_horizon)

    # If no satellites found in any white listed shells, return None
    return None


def get_closest_visible_satellite_from_white_list_unordered(
    visible_satellites: list,  # list of Satellite or similar objects with shell attribute
    ground_object: GroundObject,
    distance_model,
) -> object | None:
    """
    Returns the closest satellite from white-listed shells (NO priority ordering).

    If the white list is empty, returns the closest satellite among all visible satellites.
    If the white list has elements, returns the closest satellite among ALL satellites
    from ALL white-listed shells (treats all shells equally, no fallback priority).

    :param visible_satellites: List of visible satellites
    :param ground_object: Ground object with shells_whitelist in its domain
    :param distance_model: Distance model to compute distances
    :return: Closest satellite from white-listed shells, or None if no visible satellites
    """
    if not visible_satellites:
        return None

    # Get shell white lists from ground object domain
    shells_whitelist = (
        ground_object.ground_object_domain.shells_whitelist
        if ground_object.ground_object_domain
        else []
    )

    # If white list is empty, return the closest satellite among all
    if not shells_whitelist:
        closest = distance_model.k_closest(ground_object, visible_satellites, k=1)
        return closest[0] if closest else None

    # Filter satellites by shell identifier (no ordering, all shells treated equally)
    satellites_in_white_list = [
        vs
        for vs in visible_satellites
        if (
            vs
            and hasattr(vs, "shell")
            and vs.shell
            and hasattr(vs.shell, "identifier")
            and vs.shell.identifier in shells_whitelist
        )
    ]

    # If we found satellites in white list, return the closest one
    if satellites_in_white_list:
        closest = distance_model.k_closest(ground_object, satellites_in_white_list, k=1)
        return closest[0] if closest else None

    # If no satellites found in any white listed shells, return None
    return None
