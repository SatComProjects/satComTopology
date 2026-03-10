from dataclasses import dataclass

import numpy as np

from sat_com_connectivity.inter_satellite_link_connectivity.models import (
    OpticISLVisibilityConstraintResult,
)
from sat_com_model.models import Satellite


@dataclass(frozen=True)
class _TerminalRecord:
    """Flat view of one terminal with its satellite's ECI state."""

    satellite_name: str
    terminal_index: int  # index within satellite.optical_link_terminals
    position_km: np.ndarray  # (3,) ECI position  [km]
    velocity_km_s: np.ndarray  # (3,) ECI velocity  [km/s]
    # Constraint parameters (from OpticalLinkConfiguration)
    el_min_deg: float
    el_max_deg: float
    az_max_deg: float
    range_max_km: float
    max_angular_velocity_deg_s: float  # CPA slew rate limit [deg/s]


# =========================================================================
# GEOMETRY HELPERS
# =========================================================================


def _build_lvlh_frames(positions: np.ndarray, velocities: np.ndarray) -> np.ndarray:
    """
    Parameters : positions (N,3) [km], velocities (N,3) [km/s]
    Returns    : frames (N,3,3)  rows are [x_hat, y_hat, z_hat]
    """
    z_hat = positions / np.linalg.norm(positions, axis=1, keepdims=True)
    v_dot_z = np.sum(velocities * z_hat, axis=1, keepdims=True)
    x_raw = velocities - v_dot_z * z_hat
    x_hat = x_raw / np.linalg.norm(x_raw, axis=1, keepdims=True)
    y_hat = np.cross(z_hat, x_hat)
    return np.stack([x_hat, y_hat, z_hat], axis=1)  # (N, 3, 3)


def _compute_angles_a_to_b(
    positions_a: np.ndarray,
    frames_a: np.ndarray,
    positions_b: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Elevation, azimuth, range from every terminal in A toward every
    terminal in B, expressed in A's LVLH frames.

    Returns : elevation_deg (N,M), azimuth_deg (N,M), range_km (N,M)
    """
    d = positions_b[np.newaxis, :, :] - positions_a[:, np.newaxis, :]  # (N,M,3)
    range_km = np.linalg.norm(d, axis=2)  # (N,M)

    local = np.einsum("iab, ijb -> ija", frames_a, d)  # (N,M,3)

    safe_r = np.where(range_km > 0, range_km, 1.0)
    sin_el = np.where(range_km > 0, local[:, :, 2] / safe_r, 0.0)
    elevation_deg = np.degrees(np.arcsin(np.clip(sin_el, -1.0, 1.0)))
    azimuth_deg = np.degrees(np.arctan2(local[:, :, 1], local[:, :, 0]))

    return elevation_deg, azimuth_deg, range_km


def _compute_angular_velocity_a_to_b(
    positions_a: np.ndarray,
    velocities_a: np.ndarray,
    frames_a: np.ndarray,
    positions_b: np.ndarray,
    velocities_b: np.ndarray,
    el_t0: np.ndarray,
    az_t0: np.ndarray,
    dt_seconds: float = 1.0,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Estimate azimuth and elevation angular rates of the LOS from A toward B
    using a first-order finite difference over dt_seconds.

    Method
    ------
    Propagate all positions linearly:  pos(t+dt) = pos(t) + vel(t) * dt
    Rebuild LVLH frames at t+dt and recompute az/el.
    Angular rates:
        d_az/dt = (az(t+dt) - az(t)) / dt   [wrapped to shortest arc]
        d_el/dt = (el(t+dt) - el(t)) / dt

    This avoids the need to compute LVLH frame angular velocity derivatives
    while remaining accurate for dt << orbital period (dt = 1 s is fine for LEO).

    Parameters
    ----------
    positions_a, velocities_a : (N, 3)
    frames_a                  : (N, 3, 3)  LVLH frames at t (already built)
    positions_b, velocities_b : (M, 3)
    el_t0, az_t0              : (N, M)  angles at t (already computed)
    dt_seconds                : finite-difference step [s]

    Returns
    -------
    az_rate_deg_s : (N, M)  absolute azimuth rate   [deg/s]
    el_rate_deg_s : (N, M)  absolute elevation rate  [deg/s]
    """
    # Propagate to t + dt  (first-order, constant velocity)
    pos_a_dt = positions_a + velocities_a * dt_seconds  # (N, 3)
    pos_b_dt = positions_b + velocities_b * dt_seconds  # (M, 3)

    # Rebuild A's LVLH frames at t+dt using same velocity direction
    frames_a_dt = _build_lvlh_frames(pos_a_dt, velocities_a)

    # Recompute angles at t + dt
    el_dt, az_dt, _ = _compute_angles_a_to_b(pos_a_dt, frames_a_dt, pos_b_dt)

    # Elevation delta — no wrap needed (range [-90, 90])
    d_el = el_dt - el_t0  # (N, M)

    # Azimuth delta — wrap to (-180, 180] to handle ±180 crossing
    d_az = az_dt - az_t0
    d_az = (d_az + 180.0) % 360.0 - 180.0  # (N, M)

    return np.abs(d_az) / dt_seconds, np.abs(d_el) / dt_seconds


# =========================================================================
# EXTRACTION HELPER
# =========================================================================


def _extract_terminal_records(satellites: list[Satellite]) -> list[_TerminalRecord]:
    """
    Flatten all terminals from a list of satellites into _TerminalRecord objects.
    Satellites with no terminals are silently skipped.
    """
    records: list[_TerminalRecord] = []
    for sat in satellites:
        if not sat.optical_link_terminals:
            continue
        pos = np.asarray(
            sat.get_movement_model().get_position_earth_general_inertial(),
            dtype=float,
        )
        vel = np.asarray(
            sat.get_movement_model().get_velocity_earth_general_inertial(),
            dtype=float,
        )
        for idx, terminal in enumerate(sat.optical_link_terminals):
            cfg = terminal.terminal_configuration
            records.append(
                _TerminalRecord(
                    satellite_name=sat.satellite_name,
                    terminal_index=idx,
                    position_km=pos,
                    velocity_km_s=vel,
                    el_min_deg=cfg.min_elevation_degrees,
                    el_max_deg=cfg.max_elevation_degrees,
                    az_max_deg=cfg.max_azimuth_degrees,
                    range_max_km=cfg.maximum_range_distance_km,
                    max_angular_velocity_deg_s=cfg.maximum_angular_velocity_degree_per_second,
                )
            )
    return records


# =========================================================================
# PUBLIC API
# =========================================================================


def compute_OISL_constraints_between_satellites(
    satellites_group_1: list[Satellite],
    satellites_group_2: list[Satellite],
    angular_velocity_dt_seconds: float = 1.0,
) -> list[list[OpticISLVisibilityConstraintResult]]:
    """
    Check ISL pointing constraints terminal-to-terminal between two groups,
    including the beam-tracking angular velocity constraint.

    For each link i->j, both the azimuth rate |d_az/dt| and elevation rate
    |d_el/dt| must not exceed the CPA slew limit of terminal i.
    The bidirectional flag requires both terminals to satisfy all constraints.

    Parameters
    ----------
    satellites_group_1          : list[Satellite]
    satellites_group_2          : list[Satellite]
    angular_velocity_dt_seconds : finite-difference step for angular rate
                                  estimation [s]  (default 1 s)

    Returns
    -------
    results : list[list[OpticISLVisibilityConstraintResult]]
        results[i][j] — terminal i (group 1) <-> terminal j (group 2).
    """
    records_1 = _extract_terminal_records(satellites_group_1)
    records_2 = _extract_terminal_records(satellites_group_2)

    if not records_1 or not records_2:
        return []

    N = len(records_1)
    M = len(records_2)

    # ── ECI state arrays  ─────────────────────────────────────────
    pos_1 = np.array([r.position_km for r in records_1])  # (N, 3)
    vel_1 = np.array([r.velocity_km_s for r in records_1])  # (N, 3)
    pos_2 = np.array([r.position_km for r in records_2])  # (M, 3)
    vel_2 = np.array([r.velocity_km_s for r in records_2])  # (M, 3)

    # ── Per-terminal constraint vectors (broadcast-ready)  ────────
    el_min_1 = np.array([r.el_min_deg for r in records_1]).reshape(N, 1)
    el_max_1 = np.array([r.el_max_deg for r in records_1]).reshape(N, 1)
    az_max_1 = np.array([r.az_max_deg for r in records_1]).reshape(N, 1)
    range_max_1 = np.array([r.range_max_km for r in records_1]).reshape(N, 1)
    omega_max_1 = np.array([r.max_angular_velocity_deg_s for r in records_1]).reshape(
        N, 1
    )

    el_min_2 = np.array([r.el_min_deg for r in records_2]).reshape(M, 1)
    el_max_2 = np.array([r.el_max_deg for r in records_2]).reshape(M, 1)
    az_max_2 = np.array([r.az_max_deg for r in records_2]).reshape(M, 1)
    range_max_2 = np.array([r.range_max_km for r in records_2]).reshape(M, 1)
    omega_max_2 = np.array([r.max_angular_velocity_deg_s for r in records_2]).reshape(
        M, 1
    )

    # ── LVLH frames  ─────────────────────────────────────────────
    frames_1 = _build_lvlh_frames(pos_1, vel_1)  # (N, 3, 3)
    frames_2 = _build_lvlh_frames(pos_2, vel_2)  # (M, 3, 3)

    # ── Angles at t  ─────────────────────────────────────────────
    el_12, az_12, range_12 = _compute_angles_a_to_b(pos_1, frames_1, pos_2)  # (N, M)
    el_21, az_21, _ = _compute_angles_a_to_b(pos_2, frames_2, pos_1)  # (M, N)

    # ── Angular velocity  ─────────────────────────────────────────
    az_rate_12, el_rate_12 = _compute_angular_velocity_a_to_b(
        pos_1,
        vel_1,
        frames_1,
        pos_2,
        vel_2,
        el_12,
        az_12,
        dt_seconds=angular_velocity_dt_seconds,
    )  # (N, M)

    az_rate_21, el_rate_21 = _compute_angular_velocity_a_to_b(
        pos_2,
        vel_2,
        frames_2,
        pos_1,
        vel_1,
        el_21,
        az_21,
        dt_seconds=angular_velocity_dt_seconds,
    )  # (M, N)

    # ── Constraint flags  ─────────────────────────────────────────
    el_ok_12 = (el_12 >= el_min_1) & (el_12 <= el_max_1)
    az_ok_12 = np.abs(az_12) <= az_max_1
    range_ok_12 = range_12 <= range_max_1
    # Both az and el rates must be within the CPA slew limit
    omega_ok_12 = (az_rate_12 <= omega_max_1) & (el_rate_12 <= omega_max_1)
    link_ok_12 = el_ok_12 & az_ok_12 & range_ok_12 & omega_ok_12

    el_ok_21 = (el_21 >= el_min_2) & (el_21 <= el_max_2)
    az_ok_21 = np.abs(az_21) <= az_max_2
    range_ok_21 = range_12.T <= range_max_2
    omega_ok_21 = (az_rate_21 <= omega_max_2) & (el_rate_21 <= omega_max_2)
    link_ok_21 = el_ok_21 & az_ok_21 & range_ok_21 & omega_ok_21

    bidirectional = link_ok_12 & link_ok_21.T  # (N, M)

    results: list[list[OpticISLVisibilityConstraintResult]] = []

    for i in range(N):
        row: list[OpticISLVisibilityConstraintResult] = []
        for j in range(M):
            row.append(
                OpticISLVisibilityConstraintResult(
                    elevation_angle_degree=float(el_12[i, j]),
                    azimuth_angle_degree=float(az_12[i, j]),
                    azimuth_angular_velocity_rate_degree_per_second=float(
                        az_rate_12[i, j]
                    ),
                    elevation_angular_velocity_rate_degree_per_second=float(
                        el_rate_12[i, j]
                    ),
                    range_distance_km=float(range_12[i, j]),
                    flag_elevation=bool(el_ok_12[i, j]),
                    flag_azimuth=bool(az_ok_12[i, j]),
                    flag_range=bool(range_ok_12[i, j]),
                    flag_angular_velocity=bool(omega_ok_12[i, j]),
                    flag_overall=bool(link_ok_12[i, j]),
                    flag_bidirectional=bool(bidirectional[i, j]),
                )
            )
        results.append(row)

    return results
