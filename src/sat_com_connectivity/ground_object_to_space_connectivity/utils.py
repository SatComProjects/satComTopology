from sat_com_connectivity.ground_object_to_space_connectivity.visibility_angle_utils import (
    VisibleSatellite,
)


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
        shell_id = id(vs.satellite.walker_shell)
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
            s.satellite.walker_shell.amount_of_satellite_per_orbit_plane
            * s.satellite.walker_shell.amount_of_orbit_plane,
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
        shell_id = id(vs.satellite.walker_shell)
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
            s.satellite.walker_shell.mean_revolution_per_day,
            s.elevation_above_horizon,
        ),
        default=None,
    )
