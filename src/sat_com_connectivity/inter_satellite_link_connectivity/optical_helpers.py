from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Literal

import numpy as np

from sat_com_connectivity.inter_satellite_link_connectivity.models import (
    OpticISLVisibilityConstraintResult,
    PossibleOpticalLink,
)
from sat_com_model.models import Satellite, OpticalLinkTerminal

# =========================================================================
# ECI CACHE
# Centralised SGP4 call deduplication. Pass a single instance through all
# internal functions so each satellite is propagated at most once per tick.
# =========================================================================


class _EciCache:
    """
    Lazy per-satellite ECI cache keyed by topology_uniq_id.
    Build once at the top of any public function, pass down to every helper.
    """

    def __init__(self):
        self._pos: dict[int, np.ndarray] = {}
        self._vel: dict[int, np.ndarray] = {}

    def get(self, sat: Satellite) -> tuple[np.ndarray, np.ndarray]:
        sid = sat.topology_uniq_id
        if sid not in self._pos:
            mm = sat.get_movement_model()
            self._pos[sid] = np.asarray(
                mm.get_position_earth_general_inertial(), dtype=float
            ).flatten()[:3]
            self._vel[sid] = np.asarray(
                mm.get_velocity_earth_general_inertial(), dtype=float
            ).flatten()[:3]
        return self._pos[sid], self._vel[sid]

    def warm(self, satellites: list[Satellite]) -> None:
        for sat in satellites:
            self.get(sat)

    def __len__(self) -> int:
        return len(self._pos)


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
    return np.stack([x_hat, y_hat, z_hat], axis=1)


def _compute_angles_a_to_b(
    positions_a: np.ndarray,
    frames_a: np.ndarray,
    positions_b: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Elevation, azimuth, range from every point in A toward every point in B,
    expressed in A's LVLH frames.

    Returns : elevation_deg (N,M), azimuth_deg (N,M), range_km (N,M)
    """
    d = positions_b[np.newaxis, :, :] - positions_a[:, np.newaxis, :]
    range_km = np.linalg.norm(d, axis=2)
    local = np.einsum("iab, ijb -> ija", frames_a, d)
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
    range_t0: np.ndarray,
    dt_seconds: float = 1.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    First-order finite-difference estimate of az/el angular rates and range rate.

    Parameters
    ----------
    range_t0 : (N, M)  range at t=0 [km], already computed by _compute_angles_a_to_b

    Returns
    -------
    az_rate_deg_s : (N, M)  absolute azimuth rate   [deg/s]
    el_rate_deg_s : (N, M)  absolute elevation rate  [deg/s]
    range_rate_km_s : (N, M)  signed range rate [km/s]
                      positive = satellites diverging
                      negative = satellites closing
    """
    pos_a_dt = positions_a + velocities_a * dt_seconds
    pos_b_dt = positions_b + velocities_b * dt_seconds
    frames_a_dt = _build_lvlh_frames(pos_a_dt, velocities_a)
    el_dt, az_dt, range_dt = _compute_angles_a_to_b(pos_a_dt, frames_a_dt, pos_b_dt)
    d_az = (az_dt - az_t0 + 180.0) % 360.0 - 180.0
    d_el = el_dt - el_t0
    range_rate = (range_dt - range_t0) / dt_seconds  # km/s, signed
    return np.abs(d_az) / dt_seconds, np.abs(d_el) / dt_seconds, range_rate


def _az_relative(
    az: float | np.ndarray, boresight: float | np.ndarray
) -> float | np.ndarray:
    """Azimuth deviation from boresight, wrapped to [-180, 180]."""
    return (az - boresight + 180.0) % 360.0 - 180.0


# =========================================================================
# TERMINAL RECORD — flat view of one terminal with cached ECI
# =========================================================================


@dataclass(frozen=True)
class _TerminalRecord:
    terminal: OpticalLinkTerminal  # hashable via terminal_id UUID
    satellite_index: int  # index into the source satellite list
    terminal_index: int  # index in satellite.optical_link_terminals
    position_km: np.ndarray
    velocity_km_s: np.ndarray
    el_min_deg: float
    el_max_deg: float
    az_max_deg: float
    range_max_km: float
    max_angular_velocity_deg_s: float
    boresight_az_deg: float
    boresight_el_deg: float


def _build_terminal_records(
    satellites: list[Satellite],
    cache: _EciCache,
) -> list[_TerminalRecord]:
    """
    Flatten all terminals from a satellite list into _TerminalRecord objects.
    ECI is read from the cache — no redundant SGP4 calls.
    """
    records: list[_TerminalRecord] = []
    for sat_idx, sat in enumerate(satellites):
        if not sat.optical_link_terminals:
            continue
        pos, vel = cache.get(sat)
        for term_idx, terminal in enumerate(sat.optical_link_terminals):
            cfg = terminal.terminal_configuration
            records.append(
                _TerminalRecord(
                    terminal=terminal,
                    satellite_index=sat_idx,
                    terminal_index=term_idx,
                    position_km=pos,
                    velocity_km_s=vel,
                    el_min_deg=cfg.min_elevation_degrees,
                    el_max_deg=cfg.max_elevation_degrees,
                    az_max_deg=cfg.max_azimuth_degrees,
                    range_max_km=cfg.maximum_range_distance_km,
                    max_angular_velocity_deg_s=cfg.maximum_angular_velocity_degree_per_second,
                    boresight_az_deg=terminal.azimuth_angle_configuration,
                    boresight_el_deg=terminal.elevation_angle_configuration,
                )
            )
    return records


def _build_terminal_records_from_pool(
    terminals: list[OpticalLinkTerminal],
    cache: _EciCache,
) -> list[_TerminalRecord]:
    """
    Build records directly from a terminal pool.
    terminal.host_satellite is used — satellite list is not required.
    """
    records: list[_TerminalRecord] = []
    for term_idx, terminal in enumerate(terminals):
        sat = terminal.host_satellite
        pos, vel = cache.get(sat)
        cfg = terminal.terminal_configuration
        records.append(
            _TerminalRecord(
                terminal=terminal,
                satellite_index=sat.topology_uniq_id,
                terminal_index=term_idx,
                position_km=pos,
                velocity_km_s=vel,
                el_min_deg=cfg.min_elevation_degrees,
                el_max_deg=cfg.max_elevation_degrees,
                az_max_deg=cfg.max_azimuth_degrees,
                range_max_km=cfg.maximum_range_distance_km,
                max_angular_velocity_deg_s=cfg.maximum_angular_velocity_degree_per_second,
                boresight_az_deg=terminal.azimuth_angle_configuration,
                boresight_el_deg=terminal.elevation_angle_configuration,
            )
        )
    return records


# =========================================================================
# SHARED VECTORISED CORE
# =========================================================================
_EPS = 1e-9  # division guard


def _compute_constraint_matrices(
    records_1: list[_TerminalRecord],
    records_2: list[_TerminalRecord],
    angular_velocity_dt_seconds: float = 1.0,
) -> tuple:
    """
    Pure numpy computation over two flat terminal record lists.
    All SGP4 work is already done — records carry cached ECI.

    Returns
    -------
    el_12, az_12, range_12          : (N, M) geometry,           group 1 → group 2
    omega_total_12                  : (N, M) total LOS rate [deg/s]
    range_rate_12                   : (N, M) signed range rate [km/s]
                                      positive = diverging, useful for Doppler
    el_21, az_21                    : (M, N) geometry,           group 2 → group 1
    omega_total_21                  : (M, N) total LOS rate [deg/s]
    range_rate_21                   : (M, N) signed range rate [km/s]
    omega_ok_12, omega_ok_21        : angular velocity constraint flags
    link_ok_12, link_ok_21          : all constraints combined
    bidirectional                   : (N, M) link_ok_12 & link_ok_21.T
    alignment_score                 : (N, M) combined boresight az deviation (lower=better)
    estimated_duration_12           : (N, M) seconds until first constraint violation [s]
                                      conservative linear extrapolation from current rates
    """
    N, M = len(records_1), len(records_2)

    pos_1 = np.array([r.position_km for r in records_1])
    vel_1 = np.array([r.velocity_km_s for r in records_1])
    pos_2 = np.array([r.position_km for r in records_2])
    vel_2 = np.array([r.velocity_km_s for r in records_2])

    el_min_1 = np.array([r.el_min_deg for r in records_1]).reshape(N, 1)
    el_max_1 = np.array([r.el_max_deg for r in records_1]).reshape(N, 1)
    az_max_1 = np.array([r.az_max_deg for r in records_1]).reshape(N, 1)
    range_max_1 = np.array([r.range_max_km for r in records_1]).reshape(N, 1)
    omega_max_1 = np.array([r.max_angular_velocity_deg_s for r in records_1]).reshape(
        N, 1
    )
    boresight_az_1 = np.array([r.boresight_az_deg for r in records_1]).reshape(N, 1)

    el_min_2 = np.array([r.el_min_deg for r in records_2]).reshape(M, 1)
    el_max_2 = np.array([r.el_max_deg for r in records_2]).reshape(M, 1)
    az_max_2 = np.array([r.az_max_deg for r in records_2]).reshape(M, 1)
    range_max_2 = np.array([r.range_max_km for r in records_2]).reshape(M, 1)
    omega_max_2 = np.array([r.max_angular_velocity_deg_s for r in records_2]).reshape(
        M, 1
    )
    boresight_az_2 = np.array([r.boresight_az_deg for r in records_2]).reshape(M, 1)

    frames_1 = _build_lvlh_frames(pos_1, vel_1)
    frames_2 = _build_lvlh_frames(pos_2, vel_2)

    el_12, az_12, range_12 = _compute_angles_a_to_b(pos_1, frames_1, pos_2)
    el_21, az_21, _ = _compute_angles_a_to_b(pos_2, frames_2, pos_1)

    az_rate_12, el_rate_12, range_rate_12 = _compute_angular_velocity_a_to_b(
        pos_1,
        vel_1,
        pos_2,
        vel_2,
        el_12,
        az_12,
        range_12,
        dt_seconds=angular_velocity_dt_seconds,
    )
    az_rate_21, el_rate_21, range_rate_21 = _compute_angular_velocity_a_to_b(
        pos_2,
        vel_2,
        pos_1,
        vel_1,
        el_21,
        az_21,
        range_12.T,
        dt_seconds=angular_velocity_dt_seconds,
    )

    omega_total_12 = np.sqrt(az_rate_12**2 + el_rate_12**2)
    omega_total_21 = np.sqrt(az_rate_21**2 + el_rate_21**2)

    # Azimuth relative to boresight
    az_rel_12 = np.abs((az_12 - boresight_az_1 + 180.0) % 360.0 - 180.0)  # (N, M)
    az_rel_21 = np.abs((az_21 - boresight_az_2 + 180.0) % 360.0 - 180.0)  # (M, N)

    el_ok_12 = (el_12 >= el_min_1) & (el_12 <= el_max_1)
    az_ok_12 = az_rel_12 <= az_max_1
    range_ok_12 = range_12 <= range_max_1
    omega_ok_12 = omega_total_12 <= omega_max_1
    link_ok_12 = el_ok_12 & az_ok_12 & range_ok_12 & omega_ok_12

    el_ok_21 = (el_21 >= el_min_2) & (el_21 <= el_max_2)
    az_ok_21 = az_rel_21 <= az_max_2
    range_ok_21 = range_12.T <= range_max_2
    omega_ok_21 = omega_total_21 <= omega_max_2
    link_ok_21 = el_ok_21 & az_ok_21 & range_ok_21 & omega_ok_21

    bidirectional = link_ok_12 & link_ok_21.T
    alignment_score = az_rel_12 + az_rel_21.T  # lower = better boresight alignment

    # ── Estimated link duration — conservative linear extrapolation ────────
    #
    # For each active constraint we compute the remaining margin and divide by
    # the current rate of change to get seconds until violation.
    # Elevation: take the smaller of the two margins (lower/upper bound) —
    #   conservative because we don't know which direction el is moving.
    # Azimuth:   margin to the FOV boundary, decreasing at az_rate_12.
    # Range:     only relevant when satellites are diverging (range_rate > 0).
    #   If closing, the range constraint will not be hit — set to inf.
    # We do NOT estimate time for the omega constraint because that would
    # require the rate-of-rate (jerk), which is not computed here.
    #
    # Result is clamped to [0, inf] — negative margin means already violated.

    el_margin_12 = np.minimum(el_12 - el_min_1, el_max_1 - el_12)  # (N, M) deg
    az_margin_12 = az_max_1 - az_rel_12  # (N, M) deg

    t_el_12 = np.maximum(el_margin_12, 0.0) / (el_rate_12 + _EPS)
    t_az_12 = np.maximum(az_margin_12, 0.0) / (az_rate_12 + _EPS)
    t_range_12 = np.where(
        range_rate_12 > 0,
        np.maximum(range_max_1 - range_12, 0.0) / (range_rate_12 + _EPS),
        np.inf,  # closing link — range constraint not the limiting factor
    )

    # Minimum across all three constraint clocks — first one to fire wins
    estimated_duration_12 = np.minimum(np.minimum(t_el_12, t_az_12), t_range_12)

    return (
        el_12,
        az_12,
        range_12,
        omega_total_12,
        range_rate_12,
        el_21,
        az_21,
        omega_total_21,
        range_rate_21,
        omega_ok_12,
        omega_ok_21,
        link_ok_12,
        link_ok_21,
        bidirectional,
        alignment_score,
        estimated_duration_12,
    )


# =========================================================================
# LINK BUILDER HELPER
# =========================================================================


def _make_possible_link(
    rec_1: _TerminalRecord,
    rec_2: _TerminalRecord,
    satellite_1: Satellite,
    satellite_2: Satellite,
    el_12: np.ndarray,
    az_12: np.ndarray,
    range_12: np.ndarray,
    range_rate_12: np.ndarray,
    omega_total_12: np.ndarray,
    el_21: np.ndarray,
    az_21: np.ndarray,
    omega_total_21: np.ndarray,
    omega_ok_12: np.ndarray,
    omega_ok_21: np.ndarray,
    link_ok_12: np.ndarray,
    link_ok_21: np.ndarray,
    bidirectional: np.ndarray,
    score: float,
    i: int,
    j: int,
    estimated_duration_12: np.ndarray = None,
) -> PossibleOpticalLink:
    return PossibleOpticalLink(
        satellite_a=satellite_1,
        satellite_b=satellite_2,
        terminal_a=rec_1.terminal,
        terminal_b=rec_2.terminal,
        constraint_a_to_b=OpticISLVisibilityConstraintResult(
            elevation_angle_degree=float(el_12[i, j]),
            azimuth_angle_degree=float(az_12[i, j]),
            range_distance_km=float(range_12[i, j]),
            angular_velocity_rate_degree_per_second=float(omega_total_12[i, j]),
            range_rate=range_rate_12[i, j],
            estimated_duration=(
                float(estimated_duration_12[i, j])
                if estimated_duration_12 is not None
                else None
            ),
            flag_elevation=bool(
                (el_12[i, j] >= rec_1.el_min_deg) and (el_12[i, j] <= rec_1.el_max_deg)
            ),
            flag_azimuth=bool(abs(az_12[i, j]) <= rec_1.az_max_deg),
            flag_range=bool(range_12[i, j] <= rec_1.range_max_km),
            flag_angular_velocity=bool(omega_ok_12[i, j]),
            flag_overall=bool(link_ok_12[i, j]),
            flag_bidirectional=bool(bidirectional[i, j]),
        ),
        constraint_b_to_a=OpticISLVisibilityConstraintResult(
            elevation_angle_degree=float(el_21[j, i]),
            azimuth_angle_degree=float(az_21[j, i]),
            range_distance_km=float(range_12[i, j]),
            angular_velocity_rate_degree_per_second=float(omega_total_21[j, i]),
            estimated_duration=(
                float(estimated_duration_12[i, j])
                if estimated_duration_12 is not None
                else None
            ),
            range_rate=range_rate_12[i, j],
            flag_elevation=bool(
                (el_21[j, i] >= rec_2.el_min_deg) and (el_21[j, i] <= rec_2.el_max_deg)
            ),
            flag_azimuth=bool(abs(az_21[j, i]) <= rec_2.az_max_deg),
            flag_range=bool(range_12[i, j] <= rec_2.range_max_km),
            flag_angular_velocity=bool(omega_ok_21[j, i]),
            flag_overall=bool(link_ok_21[j, i]),
            flag_bidirectional=bool(bidirectional[i, j]),
        ),
        bidirectional_possible=bool(bidirectional[i, j]),
        selection_score=score,
    )


# =========================================================================
# INTERNAL PAIR FEASIBILITY — pure numpy, no SGP4, uses cached ECI
# =========================================================================


def _check_pair_feasibility(
    rec_a: _TerminalRecord,
    rec_b: _TerminalRecord,
    angular_velocity_dt_seconds: float = 1.0,
) -> tuple[bool, float]:
    """
    Bidirectional feasibility check from pre-computed _TerminalRecord objects.
    Returns (feasible, alignment_score). Zero SGP4 calls.
    """
    pos_a = rec_a.position_km.reshape(1, 3)
    vel_a = rec_a.velocity_km_s.reshape(1, 3)
    pos_b = rec_b.position_km.reshape(1, 3)
    vel_b = rec_b.velocity_km_s.reshape(1, 3)

    frames_a = _build_lvlh_frames(pos_a, vel_a)
    frames_b = _build_lvlh_frames(pos_b, vel_b)

    el_ab, az_ab, range_ab = _compute_angles_a_to_b(pos_a, frames_a, pos_b)
    el_ba, az_ba, _ = _compute_angles_a_to_b(pos_b, frames_b, pos_a)

    az_rate_ab, el_rate_ab, _ = _compute_angular_velocity_a_to_b(
        pos_a,
        vel_a,
        pos_b,
        vel_b,
        el_ab,
        az_ab,
        range_ab,
        dt_seconds=angular_velocity_dt_seconds,
    )
    az_rate_ba, el_rate_ba, _ = _compute_angular_velocity_a_to_b(
        pos_b,
        vel_b,
        pos_a,
        vel_a,
        el_ba,
        az_ba,
        range_ab.T,
        dt_seconds=angular_velocity_dt_seconds,
    )

    omega_ab = float(np.sqrt(az_rate_ab[0, 0] ** 2 + el_rate_ab[0, 0] ** 2))
    omega_ba = float(np.sqrt(az_rate_ba[0, 0] ** 2 + el_rate_ba[0, 0] ** 2))

    az_rel_ab = abs(_az_relative(float(az_ab[0, 0]), rec_a.boresight_az_deg))
    az_rel_ba = abs(_az_relative(float(az_ba[0, 0]), rec_b.boresight_az_deg))

    ok_ab = (
        rec_a.el_min_deg <= float(el_ab[0, 0]) <= rec_a.el_max_deg
        and az_rel_ab <= rec_a.az_max_deg
        and float(range_ab[0, 0]) <= rec_a.range_max_km
        and omega_ab <= rec_a.max_angular_velocity_deg_s
    )
    ok_ba = (
        rec_b.el_min_deg <= float(el_ba[0, 0]) <= rec_b.el_max_deg
        and az_rel_ba <= rec_b.az_max_deg
        and float(range_ab[0, 0]) <= rec_b.range_max_km
        and omega_ba <= rec_b.max_angular_velocity_deg_s
    )

    if not (ok_ab and ok_ba):
        return False, float("inf")

    return True, az_rel_ab + az_rel_ba


def _rec_to_possible_link(
    rec_a: _TerminalRecord,
    rec_b: _TerminalRecord,
    score: float,
    angular_velocity_dt_seconds: float = 1.0,
) -> PossibleOpticalLink:
    """Build a full PossibleOpticalLink from two records. Called only for winners."""
    pos_a = rec_a.position_km.reshape(1, 3)
    vel_a = rec_a.velocity_km_s.reshape(1, 3)
    pos_b = rec_b.position_km.reshape(1, 3)
    vel_b = rec_b.velocity_km_s.reshape(1, 3)

    frames_a = _build_lvlh_frames(pos_a, vel_a)
    frames_b = _build_lvlh_frames(pos_b, vel_b)

    el_ab, az_ab, range_ab = _compute_angles_a_to_b(pos_a, frames_a, pos_b)
    el_ba, az_ba, _ = _compute_angles_a_to_b(pos_b, frames_b, pos_a)

    az_rate_ab, el_rate_ab, range_rate_ab = _compute_angular_velocity_a_to_b(
        pos_a,
        vel_a,
        pos_b,
        vel_b,
        el_ab,
        az_ab,
        range_ab,
        dt_seconds=angular_velocity_dt_seconds,
    )
    az_rate_ba, el_rate_ba, range_rate_ba = _compute_angular_velocity_a_to_b(
        pos_b,
        vel_b,
        pos_a,
        vel_a,
        el_ba,
        az_ba,
        range_ab.T,
        dt_seconds=angular_velocity_dt_seconds,
    )

    omega_ab = float(np.sqrt(az_rate_ab[0, 0] ** 2 + el_rate_ab[0, 0] ** 2))
    omega_ba = float(np.sqrt(az_rate_ba[0, 0] ** 2 + el_rate_ba[0, 0] ** 2))

    return PossibleOpticalLink(
        satellite_a=rec_a.terminal.host_satellite,
        satellite_b=rec_b.terminal.host_satellite,
        terminal_a=rec_a.terminal,
        terminal_b=rec_b.terminal,
        constraint_a_to_b=OpticISLVisibilityConstraintResult(
            elevation_angle_degree=float(el_ab[0, 0]),
            azimuth_angle_degree=float(az_ab[0, 0]),
            range_distance_km=float(range_ab[0, 0]),
            range_rate=float(range_rate_ab),
            angular_velocity_rate_degree_per_second=omega_ab,
            flag_elevation=True,
            flag_azimuth=True,
            flag_range=True,
            flag_angular_velocity=True,
            flag_overall=True,
            flag_bidirectional=True,
        ),
        constraint_b_to_a=OpticISLVisibilityConstraintResult(
            elevation_angle_degree=float(el_ba[0, 0]),
            azimuth_angle_degree=float(az_ba[0, 0]),
            range_distance_km=float(range_ab[0, 0]),
            range_rate=float(range_rate_ba[0, 0]),
            angular_velocity_rate_degree_per_second=omega_ba,
            flag_elevation=True,
            flag_azimuth=True,
            flag_range=True,
            flag_angular_velocity=True,
            flag_overall=True,
            flag_bidirectional=True,
        ),
        bidirectional_possible=True,
        selection_score=score,
    )


# =========================================================================
# PUBLIC API - feasibility check for one specific terminal pair
# =========================================================================


def compute_OISL_feasibility_for_terminal_pair(
    satellite_a: Satellite,
    terminal_a: OpticalLinkTerminal,
    satellite_b: Satellite,
    terminal_b: OpticalLinkTerminal,
    angular_velocity_dt_seconds: float = 1.0,
    _cache: _EciCache | None = None,
) -> PossibleOpticalLink | None:
    """
    Check bidirectional feasibility for one specific terminal pair.
    Accepts an optional pre-built _EciCache to avoid redundant SGP4 calls
    when called in a loop (e.g. from compute_OISL_links_from_terminal_pools).
    """
    cache = _cache or _EciCache()
    pos_a, vel_a = cache.get(satellite_a)
    pos_b, vel_b = cache.get(satellite_b)

    cfg_a = terminal_a.terminal_configuration
    cfg_b = terminal_b.terminal_configuration

    rec_a = _TerminalRecord(
        terminal=terminal_a,
        satellite_index=0,
        terminal_index=0,
        position_km=pos_a,
        velocity_km_s=vel_a,
        el_min_deg=cfg_a.min_elevation_degrees,
        el_max_deg=cfg_a.max_elevation_degrees,
        az_max_deg=cfg_a.max_azimuth_degrees,
        range_max_km=cfg_a.maximum_range_distance_km,
        max_angular_velocity_deg_s=cfg_a.maximum_angular_velocity_degree_per_second,
        boresight_az_deg=terminal_a.azimuth_angle_configuration,
        boresight_el_deg=terminal_a.elevation_angle_configuration,
    )
    rec_b = _TerminalRecord(
        terminal=terminal_b,
        satellite_index=1,
        terminal_index=0,
        position_km=pos_b,
        velocity_km_s=vel_b,
        el_min_deg=cfg_b.min_elevation_degrees,
        el_max_deg=cfg_b.max_elevation_degrees,
        az_max_deg=cfg_b.max_azimuth_degrees,
        range_max_km=cfg_b.maximum_range_distance_km,
        max_angular_velocity_deg_s=cfg_b.maximum_angular_velocity_degree_per_second,
        boresight_az_deg=terminal_b.azimuth_angle_configuration,
        boresight_el_deg=terminal_b.elevation_angle_configuration,
    )

    feasible, score = _check_pair_feasibility(rec_a, rec_b, angular_velocity_dt_seconds)
    if not feasible:
        return None

    return _rec_to_possible_link(rec_a, rec_b, score, angular_velocity_dt_seconds)


# =========================================================================
# PUBLIC API 6 — inter-shell assignment from terminal pools. We filter with a balltree
# =========================================================================


def compute_OISL_links_from_terminal_pools_filtered(
    terminals_group_1: list[OpticalLinkTerminal],
    terminals_group_2: list[OpticalLinkTerminal],
    maximum_range_to_filter_in_km: float = 10_000.0,
    angular_velocity_dt_seconds: float = 1.0,
    selection_strategy: Literal[
        "best_alignment",
        "best_angular_velocity",
        "shortest_range",
        "estimated_link_duration",
    ] = "estimated_link_duration",
    debug: bool = False,
) -> list[PossibleOpticalLink]:
    if not terminals_group_1 or not terminals_group_2:
        return []

    t_start = time.perf_counter()
    n1, n2 = len(terminals_group_1), len(terminals_group_2)

    # Single ECI cache
    cache = _EciCache()
    cache.warm([t.host_satellite for t in terminals_group_1 + terminals_group_2])
    t_eci = time.perf_counter() - t_start

    # Build flat records
    records_1 = _build_terminal_records_from_pool(terminals_group_1, cache)
    records_2 = _build_terminal_records_from_pool(terminals_group_2, cache)

    # -----------------------------------------------------------------------
    # Full vectorised constraint computation — ONE batch, no Python loop
    # -----------------------------------------------------------------------
    t_matrix_start = time.perf_counter()
    (
        el_12,
        az_12,
        range_12,
        omega_total_12,
        range_rate_12,
        el_21,
        az_21,
        omega_total_21,
        range_rate_21,
        omega_ok_12,
        omega_ok_21,
        link_ok_12,
        link_ok_21,
        bidirectional,
        alignment_score,
        estimated_duration_12,
    ) = _compute_constraint_matrices(records_1, records_2, angular_velocity_dt_seconds)
    t_matrix = time.perf_counter() - t_matrix_start

    # Apply range pre-filter and cross-shell mask as numpy arrays
    range_ok = range_12 <= maximum_range_to_filter_in_km  # (N, M)
    same_shell = np.array(
        [
            [
                records_1[i].terminal.host_satellite.shell.identifier
                == records_2[j].terminal.host_satellite.shell.identifier
                for j in range(n2)
            ]
            for i in range(n1)
        ],
        dtype=bool,
    )

    candidate = bidirectional & range_ok & ~same_shell  # (N, M)

    score_matrix = (
        alignment_score
        if selection_strategy == "best_alignment"
        else (
            omega_total_12
            if selection_strategy == "best_angular_velocity"
            else (
                -estimated_duration_12  # negative: argmin → longest duration
                if selection_strategy == "estimated_link_duration"
                else range_12
            )
        )
    )

    # Replace non-candidates with inf so argmin ignores them
    # score_masked = np.where(candidate, score_matrix, np.inf)  # (N, M)
    score_masked = np.where(
        candidate,
        (
            score_matrix
            if selection_strategy != "estimated_link_duration"
            else np.where(estimated_duration_12 > 0, -estimated_duration_12, np.inf)
        ),
        np.inf,
    )

    total_candidates = int(candidate.sum())

    # -----------------------------------------------------------------------
    # Greedy assignment — group 1 priority, one terminal → one connection
    # Pure numpy indexing, no Python feasibility loop
    # -----------------------------------------------------------------------
    t_assign_start = time.perf_counter()
    booked_j: set[int] = set()
    results: list[PossibleOpticalLink] = []

    for i in range(n1):
        row = score_masked[i].copy()

        # Mask already booked group-2 terminals
        for j in booked_j:
            row[j] = np.inf

        best_j = int(np.argmin(row))
        if row[best_j] == np.inf:
            continue  # no feasible candidate for this terminal

        results.append(
            _make_possible_link(
                records_1[i],
                records_2[best_j],
                records_1[i].terminal.host_satellite,
                records_2[best_j].terminal.host_satellite,
                el_12,
                az_12,
                range_12,
                range_rate_12,
                omega_total_12,
                el_21,
                az_21,
                omega_total_21,
                omega_ok_12,
                omega_ok_21,
                link_ok_12,
                link_ok_21,
                bidirectional,
                float(score_matrix[i, best_j]),
                i,
                best_j,
                estimated_duration_12,
            )
        )
        booked_j.add(best_j)

    t_assign = time.perf_counter() - t_assign_start
    t_total = time.perf_counter() - t_start

    if debug:
        print(
            f"[pool] group_1={n1}, group_2={n2}, max_pairs={n1 * n2}\n"
            f"  candidates after filter  : {total_candidates} / {n1 * n2} "
            f"({100 * total_candidates / max(n1 * n2, 1):.1f}%)\n"
            f"  links assigned           : {len(results)}\n"
            f"  eci warm                 : {t_eci*1000:.1f}ms\n"
            f"  matrix computation       : {t_matrix*1000:.1f}ms\n"
            f"  greedy assignment        : {t_assign*1000:.1f}ms\n"
            f"  total                    : {t_total*1000:.1f}ms"
        )

    results.sort(key=lambda x: x.selection_score)
    return results


# =========================================================================
# PUBLIC API 6 — inter-shell assignment from terminal pools. No filter
# =========================================================================


def compute_OISL_links_from_terminal_pools(
    terminals_group_1: list[OpticalLinkTerminal],
    terminals_group_2: list[OpticalLinkTerminal],
    angular_velocity_dt_seconds: float = 1.0,
    selection_strategy: Literal[
        "best_alignment", "best_angular_velocity", "shortest_range"
    ] = "best_alignment",
) -> list[PossibleOpticalLink]:
    """
    Compute inter-shell optical links from two small pre-filtered terminal pools.
    Group 1 drives assignment. Group 2 is secondary. One terminal → one connection.
    No range pre-filter — caller is responsible for passing only relevant terminals.
    """
    if not terminals_group_1 or not terminals_group_2:
        return []

    cache = _EciCache()
    cache.warm([t.host_satellite for t in terminals_group_1 + terminals_group_2])

    records_1 = _build_terminal_records_from_pool(terminals_group_1, cache)
    records_2 = _build_terminal_records_from_pool(terminals_group_2, cache)

    (
        el_12,
        az_12,
        range_12,
        omega_total_12,
        range_rate_12,
        el_21,
        az_21,
        omega_total_21,
        range_rate_21,
        omega_ok_12,
        omega_ok_21,
        link_ok_12,
        link_ok_21,
        bidirectional,
        alignment_score,
        estimated_duration_12,
    ) = _compute_constraint_matrices(records_1, records_2, angular_velocity_dt_seconds)

    score_matrix = (
        alignment_score
        if selection_strategy == "best_alignment"
        else (
            omega_total_12
            if selection_strategy == "best_angular_velocity"
            else range_12
        )
    )

    score_masked = np.where(bidirectional, score_matrix, np.inf)

    booked_j: set[int] = set()
    results: list[PossibleOpticalLink] = []

    for i in range(len(records_1)):
        row = score_masked[i].copy()
        for j in booked_j:
            row[j] = np.inf

        best_j = int(np.argmin(row))
        if row[best_j] == np.inf:
            continue

        results.append(
            _make_possible_link(
                records_1[i],
                records_2[best_j],
                records_1[i].terminal.host_satellite,
                records_2[best_j].terminal.host_satellite,
                el_12,
                az_12,
                range_12,
                range_rate_12,
                omega_total_12,
                el_21,
                az_21,
                omega_total_21,
                omega_ok_12,
                omega_ok_21,
                link_ok_12,
                link_ok_21,
                bidirectional,
                float(score_matrix[i, best_j]),
                i,
                best_j,
            )
        )
        booked_j.add(best_j)

    results.sort(key=lambda x: x.selection_score)

    return results
