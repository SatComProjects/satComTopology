from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from sat_com_connectivity.inter_satellite_link_connectivity.models import (
    OpticISLVisibilityConstraintResult,
    PossibleOpticalLink,
)
from sat_com_model.models import Satellite

# =========================================================================
# FLAT TERMINAL RECORD — internal working unit
# =========================================================================


@dataclass(frozen=True)
class _TerminalRecord:
    """Flat view of one terminal with its satellite's ECI state."""

    satellite_index: int  # index within the input satellites list
    terminal_index: int  # index within satellite.optical_link_terminals
    position_km: np.ndarray  # (3,) ECI position  [km]
    velocity_km_s: np.ndarray  # (3,) ECI velocity  [km/s]
    el_min_deg: float
    el_max_deg: float
    az_max_deg: float
    range_max_km: float
    max_angular_velocity_deg_s: float


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
    positions_b: np.ndarray,
    velocities_b: np.ndarray,
    el_t0: np.ndarray,
    az_t0: np.ndarray,
    dt_seconds: float = 1.0,
) -> tuple[np.ndarray, np.ndarray]:
    """
    First-order finite-difference estimate of azimuth and elevation angular rates.

    Propagates pos(t+dt) = pos(t) + vel*dt, rebuilds LVLH frame at t+dt,
    recomputes angles and divides by dt.  Accurate for dt << orbital period
    (1 s is fine for LEO where the frame rotates ~0.06 deg/s).

    Returns : az_rate_deg_s (N,M), el_rate_deg_s (N,M)   [both positive]
    """
    pos_a_dt = positions_a + velocities_a * dt_seconds
    pos_b_dt = positions_b + velocities_b * dt_seconds
    frames_a_dt = _build_lvlh_frames(pos_a_dt, velocities_a)
    el_dt, az_dt, _ = _compute_angles_a_to_b(pos_a_dt, frames_a_dt, pos_b_dt)
    d_el = el_dt - el_t0
    d_az = (az_dt - az_t0 + 180.0) % 360.0 - 180.0  # wrap to shortest arc
    return np.abs(d_az) / dt_seconds, np.abs(d_el) / dt_seconds


# =========================================================================
# EXTRACTION HELPER
# =========================================================================


def _extract_terminal_records(satellites: list[Satellite]) -> list[_TerminalRecord]:
    """
    Flatten all terminals from a list of satellites into _TerminalRecord objects.
    satellite_index tracks which satellite each record belongs to.
    Satellites with no terminals are silently skipped.
    """
    records: list[_TerminalRecord] = []
    for sat_idx, sat in enumerate(satellites):
        if not sat.optical_link_terminals:
            continue
        movement_model = sat.get_movement_model()
        pos = np.asarray(
            movement_model.get_position_earth_general_inertial(), dtype=float
        ).flatten()[:3]
        vel = np.asarray(
            movement_model.get_velocity_earth_general_inertial(), dtype=float
        ).flatten()[:3]
        for term_idx, terminal in enumerate(sat.optical_link_terminals):
            cfg = terminal.terminal_configuration
            records.append(
                _TerminalRecord(
                    satellite_index=sat_idx,
                    terminal_index=term_idx,
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
# SHARED VECTORISED CORE
# =========================================================================


def _compute_all_terminal_constraints(
    satellites_group_1: list[Satellite],
    satellites_group_2: list[Satellite],
    angular_velocity_dt_seconds: float = 1.0,
) -> tuple:
    """
    Full vectorised computation shared by both public functions.

    Returns
    -------
    records_1, records_2        : flat terminal lists
    el_12, az_12, range_12      : (N, M) geometry arrays, group 1 → group 2
    az_rate_12, el_rate_12      : (N, M) angular rates,   group 1 → group 2
    el_21, az_21                : (M, N) geometry arrays, group 2 → group 1
    az_rate_21, el_rate_21      : (M, N) angular rates,   group 2 → group 1
    omega_ok_12                 : (N, M) angular velocity constraint flag, 1→2
    omega_ok_21                 : (M, N) angular velocity constraint flag, 2→1
    link_ok_12                  : (N, M) all constraints combined,         1→2
    link_ok_21                  : (M, N) all constraints combined,         2→1
    bidirectional               : (N, M) link_ok_12 & link_ok_21.T
    """
    records_1 = _extract_terminal_records(satellites_group_1)
    records_2 = _extract_terminal_records(satellites_group_2)

    N, M = len(records_1), len(records_2)

    pos_1 = np.array([r.position_km for r in records_1])  # (N, 3)
    vel_1 = np.array([r.velocity_km_s for r in records_1])
    pos_2 = np.array([r.position_km for r in records_2])  # (M, 3)
    vel_2 = np.array([r.velocity_km_s for r in records_2])

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

    frames_1 = _build_lvlh_frames(pos_1, vel_1)
    frames_2 = _build_lvlh_frames(pos_2, vel_2)

    el_12, az_12, range_12 = _compute_angles_a_to_b(pos_1, frames_1, pos_2)
    el_21, az_21, _ = _compute_angles_a_to_b(pos_2, frames_2, pos_1)

    az_rate_12, el_rate_12 = _compute_angular_velocity_a_to_b(
        pos_1,
        vel_1,
        pos_2,
        vel_2,
        el_12,
        az_12,
        dt_seconds=angular_velocity_dt_seconds,
    )  # (N, M)

    az_rate_21, el_rate_21 = _compute_angular_velocity_a_to_b(
        pos_2,
        vel_2,
        pos_1,
        vel_1,
        el_21,
        az_21,
        dt_seconds=angular_velocity_dt_seconds,
    )  # (M, N)

    # Total LOS angular rate — magnitude of the 2D angular velocity vector.
    # The CONDOR GEN1 CPA spec gives a single pointing rate limit, not per-axis.
    omega_total_12 = np.sqrt(az_rate_12**2 + el_rate_12**2)  # (N, M)
    omega_total_21 = np.sqrt(az_rate_21**2 + el_rate_21**2)  # (M, N)

    el_ok_12 = (el_12 >= el_min_1) & (el_12 <= el_max_1)
    az_ok_12 = np.abs(az_12) <= az_max_1
    range_ok_12 = range_12 <= range_max_1
    omega_ok_12 = omega_total_12 <= omega_max_1  # (N, M)
    link_ok_12 = el_ok_12 & az_ok_12 & range_ok_12 & omega_ok_12

    el_ok_21 = (el_21 >= el_min_2) & (el_21 <= el_max_2)
    az_ok_21 = np.abs(az_21) <= az_max_2
    range_ok_21 = range_12.T <= range_max_2
    omega_ok_21 = omega_total_21 <= omega_max_2  # (M, N)
    link_ok_21 = el_ok_21 & az_ok_21 & range_ok_21 & omega_ok_21

    bidirectional = link_ok_12 & link_ok_21.T  # (N, M)

    return (
        records_1,
        records_2,
        el_12,
        az_12,
        range_12,
        omega_total_12,  # total LOS rate [deg/s], 1→2
        el_21,
        az_21,
        omega_total_21,  # total LOS rate [deg/s], 2→1
        omega_ok_12,
        omega_ok_21,
        link_ok_12,
        link_ok_21,
        bidirectional,
    )


# =========================================================================
# PUBLIC API 1 — raw terminal-level results
# =========================================================================


def compute_OISL_constraints_between_satellites(
    satellites_group_1: list[Satellite],
    satellites_group_2: list[Satellite],
    angular_velocity_dt_seconds: float = 1.0,
) -> list[list[OpticISLVisibilityConstraintResult]]:
    """
    Check ISL constraints terminal-to-terminal.  Returns a (N_terminals × M_terminals)
    matrix — one result per terminal pair.
    Use compute_OISL_possible_links() to get one result per satellite pair instead.
    """
    (
        records_1,
        records_2,
        el_12,
        az_12,
        range_12,
        omega_total_12,
        el_21,
        az_21,
        omega_total_21,
        omega_ok_12,
        omega_ok_21,
        link_ok_12,
        link_ok_21,
        bidirectional,
    ) = _compute_all_terminal_constraints(
        satellites_group_1, satellites_group_2, angular_velocity_dt_seconds
    )

    N, M = len(records_1), len(records_2)
    results: list[list[OpticISLVisibilityConstraintResult]] = []

    for i in range(N):
        row: list[OpticISLVisibilityConstraintResult] = []
        for j in range(M):
            rec = records_1[i]
            row.append(
                OpticISLVisibilityConstraintResult(
                    elevation_angle_degree=float(el_12[i, j]),
                    azimuth_angle_degree=float(az_12[i, j]),
                    range_distance_km=float(range_12[i, j]),
                    angular_velocity_rate_degree_per_second=float(omega_total_12[i, j]),
                    flag_elevation=bool(
                        (el_12[i, j] >= rec.el_min_deg)
                        and (el_12[i, j] <= rec.el_max_deg)
                    ),
                    flag_azimuth=bool(abs(az_12[i, j]) <= rec.az_max_deg),
                    flag_range=bool(range_12[i, j] <= rec.range_max_km),
                    flag_angular_velocity=bool(omega_ok_12[i, j]),
                    flag_overall=bool(link_ok_12[i, j]),
                    flag_bidirectional=bool(bidirectional[i, j]),
                )
            )
        results.append(row)

    return results


# =========================================================================
# PUBLIC API 2 — one PossibleOpticalLink per valid terminal pair
# =========================================================================


def compute_OISL_possible_links(
    satellites_group_1: list[Satellite],
    satellites_group_2: list[Satellite],
    angular_velocity_dt_seconds: float = 1.0,
    selection_strategy: Literal[
        "best_angular_velocity", "shortest_range"
    ] = "best_angular_velocity",
    bidirectional_only: bool = True,
) -> list[PossibleOpticalLink]:
    """
    Compute possible optical ISLs, returning one PossibleOpticalLink per
    valid terminal pair (not per satellite pair).

    Each OpticalLinkTerminal is an independent hardware device that may have
    its own constraint parameters.  The result list contains one entry per
    (terminal_a, terminal_b) combination that passes the filters, preserving
    full per-terminal granularity.

    Result count example:
        satellite_a has 4 terminals, satellite_b has 4 terminals
        → up to 16 PossibleOpticalLink entries for that satellite pair.

    Parameters
    ----------
    satellites_group_1          : list[Satellite]
    satellites_group_2          : list[Satellite]
    angular_velocity_dt_seconds : finite-difference step [s]  (default 1 s)
    selection_strategy          : scoring criterion for selection_score field:
                                  "best_angular_velocity" → max(az_rate, el_rate)
                                  "shortest_range"        → range_distance_km
    bidirectional_only          : if True (default), only emit pairs where
                                  both terminals satisfy all their constraints.
                                  If False, also include one-way feasible pairs.

    Returns
    -------
    list[PossibleOpticalLink]
        Sorted by selection_score ascending (best links first).
        To get the single best terminal pair per satellite pair, group by
        (satellite_a.satellite_name, satellite_b.satellite_name) and take
        the first entry.
    """
    (
        records_1,
        records_2,
        el_12,
        az_12,
        range_12,
        omega_total_12,
        el_21,
        az_21,
        omega_total_21,
        omega_ok_12,
        omega_ok_21,
        link_ok_12,
        link_ok_21,
        bidirectional,
    ) = _compute_all_terminal_constraints(
        satellites_group_1, satellites_group_2, angular_velocity_dt_seconds
    )

    if not records_1 or not records_2:
        return []

    # Score matrix (N, M) — lower is better
    if selection_strategy == "best_angular_velocity":
        score_matrix = omega_total_12  # single total rate, consistent with the spec
    else:
        score_matrix = range_12

    # Candidate mask — which (i, j) terminal pairs to emit
    candidate_mask = bidirectional if bidirectional_only else link_ok_12

    # All valid flat indices at once — no Python loop over the full matrix
    valid_i, valid_j = np.where(candidate_mask)

    results: list[PossibleOpticalLink] = []

    for i, j in zip(valid_i.tolist(), valid_j.tolist()):
        rec_1 = records_1[i]
        rec_2 = records_2[j]
        satellite_1 = satellites_group_1[rec_1.satellite_index]
        satellite_2 = satellites_group_2[rec_2.satellite_index]

        constraint_a_to_b = OpticISLVisibilityConstraintResult(
            elevation_angle_degree=float(el_12[i, j]),
            azimuth_angle_degree=float(az_12[i, j]),
            range_distance_km=float(range_12[i, j]),
            angular_velocity_rate_degree_per_second=float(omega_total_12[i, j]),
            flag_elevation=bool(
                (el_12[i, j] >= rec_1.el_min_deg) and (el_12[i, j] <= rec_1.el_max_deg)
            ),
            flag_azimuth=bool(abs(az_12[i, j]) <= rec_1.az_max_deg),
            flag_range=bool(range_12[i, j] <= rec_1.range_max_km),
            flag_angular_velocity=bool(omega_ok_12[i, j]),
            flag_overall=bool(link_ok_12[i, j]),
            flag_bidirectional=bool(bidirectional[i, j]),
        )

        constraint_b_to_a = OpticISLVisibilityConstraintResult(
            elevation_angle_degree=float(el_21[j, i]),
            azimuth_angle_degree=float(az_21[j, i]),
            range_distance_km=float(range_12[i, j]),  # symmetric
            angular_velocity_rate_degree_per_second=float(omega_total_21[j, i]),
            flag_elevation=bool(
                (el_21[j, i] >= rec_2.el_min_deg) and (el_21[j, i] <= rec_2.el_max_deg)
            ),
            flag_azimuth=bool(abs(az_21[j, i]) <= rec_2.az_max_deg),
            flag_range=bool(range_12[i, j] <= rec_2.range_max_km),
            flag_angular_velocity=bool(omega_ok_21[j, i]),
            flag_overall=bool(link_ok_21[j, i]),
            flag_bidirectional=bool(bidirectional[i, j]),
        )

        results.append(
            PossibleOpticalLink(
                satellite_a=satellite_1,
                satellite_b=satellite_2,
                terminal_a=satellite_1.optical_link_terminals[rec_1.terminal_index],
                terminal_b=satellite_2.optical_link_terminals[rec_2.terminal_index],
                constraint_a_to_b=constraint_a_to_b,
                constraint_b_to_a=constraint_b_to_a,
                bidirectional_possible=bool(bidirectional[i, j]),
                selection_score=float(score_matrix[i, j]),
            )
        )

    results.sort(key=lambda x: x.selection_score)
    return results


def compute_OISL_links(
    satellites_group_1: list[Satellite],
    satellites_group_2: list[Satellite],
    maximum_range_to_filter_in_km: float = 10_000.0,
    angular_velocity_dt_seconds: float = 1.0,
    selection_strategy: Literal[
        "best_angular_velocity", "shortest_range"
    ] = "best_angular_velocity",
) -> list[PossibleOpticalLink]:
    """
    Compute one PossibleOpticalLink per satellite pair.

    Unlike compute_OISL_possible_links(), impossible links are NOT discarded —
    every satellite pair within range is returned with its flags set truthfully.
    The caller can inspect flag_bidirectional / flag_overall to decide what to do.

    The only filter is maximum_range_to_filter_in_km, which prunes satellite
    pairs that are geometrically too far to ever establish a link (e.g. opposite
    sides of the orbit).  Set it to float("inf") to return all pairs.

    For each satellite pair the best terminal combination is selected
    (lowest score under selection_strategy).

    Parameters
    ----------
    satellites_group_1 / satellites_group_2
        Satellite groups to cross-check.
    maximum_range_to_filter_in_km : float
        Only pairs whose minimum terminal range ≤ this value are returned.
        Default 10 000 km covers any realistic LEO ISL geometry.
    angular_velocity_dt_seconds : float
        Finite-difference step for angular rate estimation [s].
    selection_strategy : "best_angular_velocity" | "shortest_range"
        Criterion for picking the best terminal pair per satellite pair.

    Returns
    -------
    list[PossibleOpticalLink]
        One entry per satellite pair within range.
        Impossible links are included with bidirectional_possible=False and
        individual flags set to reflect which constraint failed.
        Sorted by selection_score ascending.
    """
    (
        records_1,
        records_2,
        el_12,
        az_12,
        range_12,
        omega_total_12,
        el_21,
        az_21,
        omega_total_21,
        omega_ok_12,
        omega_ok_21,
        link_ok_12,
        link_ok_21,
        bidirectional,
    ) = _compute_all_terminal_constraints(
        satellites_group_1, satellites_group_2, angular_velocity_dt_seconds
    )

    if not records_1 or not records_2:
        return []

    # Score matrix (N, M) — lower is better, used to pick best terminal pair
    score_matrix = (
        omega_total_12 if selection_strategy == "best_angular_velocity" else range_12
    )

    # Build satellite_index → terminal flat-indices lookup
    sat_terms_1: dict[int, list[int]] = {}
    for flat_idx, rec in enumerate(records_1):
        sat_terms_1.setdefault(rec.satellite_index, []).append(flat_idx)

    sat_terms_2: dict[int, list[int]] = {}
    for flat_idx, rec in enumerate(records_2):
        sat_terms_2.setdefault(rec.satellite_index, []).append(flat_idx)

    results: list[PossibleOpticalLink] = []

    for sat_idx_1, term_indices_1 in sat_terms_1.items():
        satellite_1 = satellites_group_1[sat_idx_1]
        rows = np.array(term_indices_1)

        for sat_idx_2, term_indices_2 in sat_terms_2.items():
            satellite_2 = satellites_group_2[sat_idx_2]
            cols = np.array(term_indices_2)

            # Sub-range matrix for this satellite pair (all terminals share position
            # so all values are identical — just check [0,0])
            sub_range = range_12[np.ix_(rows, cols)]
            if float(sub_range.min()) > maximum_range_to_filter_in_km:
                continue

            # Best terminal pair = lowest score (no feasibility filter applied —
            # we want to represent the pair even if it fails all constraints)
            sub_score = score_matrix[np.ix_(rows, cols)]
            local_i, local_j = np.unravel_index(np.argmin(sub_score), sub_score.shape)
            i = rows[local_i]
            j = cols[local_j]

            rec_1 = records_1[i]
            rec_2 = records_2[j]

            # Individual constraint flags — reflect terminal config truthfully
            el_flag_12 = bool(
                (el_12[i, j] >= rec_1.el_min_deg) and (el_12[i, j] <= rec_1.el_max_deg)
            )
            az_flag_12 = bool(abs(az_12[i, j]) <= rec_1.az_max_deg)
            range_flag_12 = bool(range_12[i, j] <= rec_1.range_max_km)
            omega_flag_12 = bool(omega_ok_12[i, j])

            el_flag_21 = bool(
                (el_21[j, i] >= rec_2.el_min_deg) and (el_21[j, i] <= rec_2.el_max_deg)
            )
            az_flag_21 = bool(abs(az_21[j, i]) <= rec_2.az_max_deg)
            range_flag_21 = bool(range_12[i, j] <= rec_2.range_max_km)
            omega_flag_21 = bool(omega_ok_21[j, i])

            is_bidirectional = bool(bidirectional[i, j])

            constraint_a_to_b = OpticISLVisibilityConstraintResult(
                elevation_angle_degree=float(el_12[i, j]),
                azimuth_angle_degree=float(az_12[i, j]),
                range_distance_km=float(range_12[i, j]),
                angular_velocity_rate_degree_per_second=float(omega_total_12[i, j]),
                flag_elevation=el_flag_12,
                flag_azimuth=az_flag_12,
                flag_range=range_flag_12,
                flag_angular_velocity=omega_flag_12,
                flag_overall=bool(link_ok_12[i, j]),
                flag_bidirectional=is_bidirectional,
            )

            constraint_b_to_a = OpticISLVisibilityConstraintResult(
                elevation_angle_degree=float(el_21[j, i]),
                azimuth_angle_degree=float(az_21[j, i]),
                range_distance_km=float(range_12[i, j]),  # symmetric
                angular_velocity_rate_degree_per_second=float(omega_total_21[j, i]),
                flag_elevation=el_flag_21,
                flag_azimuth=az_flag_21,
                flag_range=range_flag_21,
                flag_angular_velocity=omega_flag_21,
                flag_overall=bool(link_ok_21[j, i]),
                flag_bidirectional=is_bidirectional,
            )

            results.append(
                PossibleOpticalLink(
                    satellite_a=satellite_1,
                    satellite_b=satellite_2,
                    terminal_a=satellite_1.optical_link_terminals[rec_1.terminal_index],
                    terminal_b=satellite_2.optical_link_terminals[rec_2.terminal_index],
                    constraint_a_to_b=constraint_a_to_b,
                    constraint_b_to_a=constraint_b_to_a,
                    bidirectional_possible=is_bidirectional,
                    selection_score=float(sub_score[local_i, local_j]),
                )
            )

    results.sort(key=lambda x: x.selection_score)
    return results
