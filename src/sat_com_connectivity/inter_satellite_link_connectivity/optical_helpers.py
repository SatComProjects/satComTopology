from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Literal

import numpy as np

from sat_com_connectivity.inter_satellite_link_connectivity.models import (
    OpticISLVisibilityConstraintResult,
    PossibleOpticalLink,
)
from sat_com_model.constants import WGS84_A, ATMOSPHERE_EXCLUSION_ZONE_KM
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


def _compute_los_min_altitude(
    pos_1: np.ndarray,  # (N, 3) [km]
    pos_2: np.ndarray,  # (M, 3) [km]
) -> np.ndarray:
    """
    Minimum altitude of the LOS chord above Earth's surface for every (i,j) pair.

    Computed as: distance from Earth's centre to the closest point on the
    chord segment, minus R_earth.

    Returns : (N, M) minimum altitude [km]. Negative means occulted by Earth.

    References
    ----------
    Chaudhry & Yanikomeroglu (2021) — 80 km atmospheric exclusion threshold
    https://arxiv.org/pdf/2103.00056
    """
    d = pos_2[np.newaxis, :, :] - pos_1[:, np.newaxis, :]  # (N, M, 3)
    d2 = np.einsum("ijk,ijk->ij", d, d)  # |d|²  (N, M)
    t = -np.einsum("ik,ijk->ij", pos_1, d) / np.where(d2 > 0, d2, 1.0)
    t = np.clip(t, 0.0, 1.0)  # (N, M)
    closest = pos_1[:, np.newaxis, :] + t[:, :, np.newaxis] * d  # (N, M, 3)
    min_radius = np.linalg.norm(closest, axis=2)  # (N, M)
    return min_radius - WGS84_A  # altitude [km]


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

    Returns
    -------
    az_rate_deg_s : (N, M)  absolute azimuth rate   [deg/s]  — always ≥ 0
    el_rate_deg_s : (N, M)  absolute elevation rate  [deg/s] — always ≥ 0
    range_rate_km_s : (N, M)  signed range rate [km/s]
                      positive = satellites diverging
                      negative = satellites closing

    Note: az/el rates are returned as magnitudes (abs). When signed rates are
    required for recovery-time estimation use the dedicated signed path in
    _check_pair_feasibility instead.
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
    terminal: OpticalLinkTerminal
    satellite_index: int
    terminal_index: int
    position_km: np.ndarray
    velocity_km_s: np.ndarray
    el_min_deg: float
    el_max_deg: float
    az_max_deg: float
    range_max_km: float
    max_angular_velocity_deg_s: float
    boresight_az_deg: float
    boresight_el_deg: float
    min_contact_duration: float


def _build_terminal_records(
    satellites: list[Satellite],
    cache: _EciCache,
) -> list[_TerminalRecord]:
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
                    min_contact_duration=cfg.minimum_contact_duration_seconds,
                )
            )
    return records


def _build_terminal_records_from_pool(
    terminals: list[OpticalLinkTerminal],
    cache: _EciCache,
) -> list[_TerminalRecord]:
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
                min_contact_duration=cfg.minimum_contact_duration_seconds,
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
                                      conservative linear extrapolation from current rates.
                                      Bug fix #3: now includes geometric ω-limit estimate
                                      for closing satellite pairs.
    estimated_duration_21           : (M, N) same for 2→1 direction
    estimated_duration              : (N, M) element-wise minimum of _12 and _21.T
    duration_ok, duration_1_ok, duration_2_ok : minimum-contact-duration gate flags
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

    # Azimuth relative to boresight — (N, M) and (M, N)
    az_rel_12 = np.abs((az_12 - boresight_az_1 + 180.0) % 360.0 - 180.0)
    az_rel_21 = np.abs((az_21 - boresight_az_2 + 180.0) % 360.0 - 180.0)

    el_ok_12 = (el_12 >= el_min_1) & (el_12 <= el_max_1)
    az_ok_12 = az_rel_12 <= az_max_1
    range_ok_12 = range_12 <= range_max_1
    omega_ok_12 = omega_total_12 <= omega_max_1

    los_min_altitude = _compute_los_min_altitude(pos_1, pos_2)  # (N, M)
    los_clear = los_min_altitude >= ATMOSPHERE_EXCLUSION_ZONE_KM  # (N, M)

    link_ok_12 = el_ok_12 & az_ok_12 & range_ok_12 & omega_ok_12 & los_clear

    el_ok_21 = (el_21 >= el_min_2) & (el_21 <= el_max_2)
    az_ok_21 = az_rel_21 <= az_max_2
    range_ok_21 = range_12.T <= range_max_2
    omega_ok_21 = omega_total_21 <= omega_max_2

    link_ok_21 = el_ok_21 & az_ok_21 & range_ok_21 & omega_ok_21 & los_clear.T

    bidirectional = link_ok_12 & link_ok_21.T
    alignment_score = az_rel_12 + az_rel_21.T  # lower = better boresight alignment

    # ── Estimated link duration — conservative linear extrapolation ────────
    #
    # For each active constraint compute the remaining margin and divide by
    # the current rate of change → seconds until violation.
    #
    # Fix A (new): LOS time-to-violation.
    #   LOS minimum altitude is not static. We compute its finite-difference
    #   rate using the same dt as for angular velocity.  When the altitude is
    #   falling toward the exclusion-zone threshold the t_los term caps the
    #   estimated duration correctly (link 1 failure mode: LOS collapsed from
    #   84.6 → 80.1 km in 10 s while all other margins were wide open).
    #
    # Fix B (revised ω): CPA-guarded geometric estimate.
    #   Previous formula: t_ω = r · (1 − ω/ω_max) / (−ṙ)
    #   assumed constant range_rate, which over-predicts how quickly ω grows
    #   for crossing-orbit pairs.  For two satellites on different orbital
    #   NOTE on the CPA guard (removed in fix #7):
    #   A previous version added a linear-motion CPA guard here to avoid
    #   emitting finite t_ω for pairs that never get close enough to spike ω.
    #   That guard used r_cpa = |Δr×Δv|/|Δv|, which is only valid for
    #   straight-line motion over short timescales.  When satellites are
    #   thousands of km apart, the orbital curvature over the next
    #   several hundred seconds makes the linear r_cpa wildly wrong —
    #   typically 10–15× larger than the true CPA (see link 7d061f61:
    #   linear r_cpa=2070 km vs actual CPA ≈150 km, r_crit=209 km).
    #   The guard therefore incorrectly sets t_ω=inf for pairs that
    #   genuinely will spike ω, which is far more harmful to terminal
    #   selection than a conservative underestimate.
    #
    #   The simple formula t_ω = (r − r_crit) / (−ṙ) is used instead.
    #   It overestimates by ≤~50% because |ṙ| grows as satellites
    #   approach (conservative), but it is always finite for a truly
    #   converging pair and never produces the 4–6× over-estimate
    #   that the broken CPA guard caused.
    #
    #   The CPA-aware formula (fix #6) is KEPT in _check_pair_feasibility
    #   because that function is called at update ticks when satellites
    #   are already close and the linear approximation is valid.

    dt = angular_velocity_dt_seconds

    # ── LOS rate (N, M) ────────────────────────────────────────────────────
    pos_1_dt = pos_1 + vel_1 * dt  # (N, 3)
    pos_2_dt = pos_2 + vel_2 * dt  # (M, 3)
    los_min_altitude_dt = _compute_los_min_altitude(pos_1_dt, pos_2_dt)  # (N, M)
    los_rate = (los_min_altitude_dt - los_min_altitude) / dt  # (N, M) km/s, signed

    # t_los: only finite when LOS altitude is dropping
    t_los = np.where(
        los_rate < 0,
        np.maximum(los_min_altitude - ATMOSPHERE_EXCLUSION_ZONE_KM, 0.0)
        / (-los_rate + _EPS),
        np.inf,
    )  # (N, M); symmetric — same chord for both directions

    # ── Margins ─────────────────────────────────────────────────────────────
    el_margin_12 = np.minimum(el_12 - el_min_1, el_max_1 - el_12)  # (N, M) deg
    az_margin_12 = az_max_1 - az_rel_12  # (N, M) deg

    t_el_12 = np.maximum(el_margin_12, 0.0) / (el_rate_12 + _EPS)
    t_az_12 = np.maximum(az_margin_12, 0.0) / (az_rate_12 + _EPS)
    t_range_12 = np.where(
        range_rate_12 > 0,
        np.maximum(range_max_1 - range_12, 0.0) / (range_rate_12 + _EPS),
        np.inf,  # closing link — range constraint will not be hit
    )

    # Fix #7 direction 1→2: simple conservative t_ω, no CPA guard.
    # r_crit = ω·r/ω_max (range where ω = ω_max, assuming v_⊥ ≈ const).
    # t_ω = (r − r_crit) / (−ṙ) — always finite for a closing pair.
    safe_omega_max_1 = np.where(omega_max_1 > 0, omega_max_1, 1.0)
    r_crit_12 = omega_total_12 * range_12 / safe_omega_max_1  # (N, M) km
    t_omega_12 = np.where(
        (range_rate_12 < 0) & (omega_total_12 < omega_max_1),
        np.maximum(range_12 - r_crit_12, 0.0) / (-range_rate_12 + _EPS),
        np.inf,
    )

    el_margin_21 = np.minimum(el_21 - el_min_2, el_max_2 - el_21)  # (M, N)
    az_margin_21 = az_max_2 - az_rel_21

    t_el_21 = np.maximum(el_margin_21, 0.0) / (el_rate_21 + _EPS)
    t_az_21 = np.maximum(az_margin_21, 0.0) / (az_rate_21 + _EPS)
    t_range_21 = np.where(
        range_rate_21 > 0,
        np.maximum(range_max_2 - range_12.T, 0.0) / (range_rate_21 + _EPS),
        np.inf,
    )

    # Fix #7 direction 2→1
    safe_omega_max_2 = np.where(omega_max_2 > 0, omega_max_2, 1.0)
    r_crit_21 = omega_total_21 * range_12.T / safe_omega_max_2  # (M, N) km
    t_omega_21 = np.where(
        (range_rate_21 < 0) & (omega_total_21 < omega_max_2),
        np.maximum(range_12.T - r_crit_21, 0.0) / (-range_rate_21 + _EPS),
        np.inf,
    )

    # Combine — t_los is direction-agnostic (same chord), use for both
    estimated_duration_12 = np.minimum(
        np.minimum(np.minimum(np.minimum(t_el_12, t_az_12), t_range_12), t_omega_12),
        t_los,
    )
    estimated_duration_21 = np.minimum(
        np.minimum(np.minimum(np.minimum(t_el_21, t_az_21), t_range_21), t_omega_21),
        t_los.T,
    )

    estimated_duration = np.minimum(
        estimated_duration_12,
        estimated_duration_21.T,
    )

    duration_min_1 = np.array([r.min_contact_duration for r in records_1]).reshape(N, 1)
    duration_min_2 = np.array([r.min_contact_duration for r in records_2]).reshape(M, 1)

    duration_1_ok = estimated_duration >= duration_min_1
    duration_2_ok = estimated_duration >= duration_min_2.T
    duration_ok = duration_1_ok & duration_2_ok

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
        los_clear,
        los_min_altitude,
        link_ok_12,
        link_ok_21,
        bidirectional,
        alignment_score,
        estimated_duration_12,
        estimated_duration_21,
        estimated_duration,
        duration_ok,
        duration_1_ok,
        duration_2_ok,
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
    los_clear: np.ndarray,
    los_min_altitude: np.ndarray,
    link_ok_12: np.ndarray,
    link_ok_21: np.ndarray,
    bidirectional: np.ndarray,
    score: float,
    i: int,
    j: int,
    estimated_duration_12: np.ndarray = None,
    estimated_duration_21: np.ndarray = None,
) -> PossibleOpticalLink:
    # Bug fix #4: compute boresight-relative azimuth for the flag, not raw LVLH azimuth.
    az_rel_12_ij = float(
        abs((az_12[i, j] - rec_1.boresight_az_deg + 180.0) % 360.0 - 180.0)
    )
    az_rel_21_ji = float(
        abs((az_21[j, i] - rec_2.boresight_az_deg + 180.0) % 360.0 - 180.0)
    )

    return PossibleOpticalLink(
        satellite_a=satellite_1,
        satellite_b=satellite_2,
        terminal_a=rec_1.terminal,
        terminal_b=rec_2.terminal,
        constraint_a_to_b=OpticISLVisibilityConstraintResult(
            los_clear=bool(los_clear[i, j]),
            los_min_altitude_km=float(los_min_altitude[i, j]),
            elevation_angle_degree=float(el_12[i, j]),
            azimuth_angle_degree=float(az_12[i, j]),
            range_distance_km=float(range_12[i, j]),
            angular_velocity_rate_degree_per_second=float(omega_total_12[i, j]),
            range_rate=float(range_rate_12[i, j]),
            estimated_duration=(
                float(estimated_duration_12[i, j])
                if estimated_duration_12 is not None
                else None
            ),
            flag_elevation=bool(rec_1.el_min_deg <= el_12[i, j] <= rec_1.el_max_deg),
            flag_azimuth=bool(az_rel_12_ij <= rec_1.az_max_deg),  # Bug fix #4
            flag_range=bool(range_12[i, j] <= rec_1.range_max_km),
            flag_angular_velocity=bool(omega_ok_12[i, j]),
            flag_overall=bool(link_ok_12[i, j]),
            flag_bidirectional=bool(bidirectional[i, j]),
        ),
        constraint_b_to_a=OpticISLVisibilityConstraintResult(
            los_clear=bool(los_clear[i, j]),
            los_min_altitude_km=float(los_min_altitude[i, j]),
            elevation_angle_degree=float(el_21[j, i]),
            azimuth_angle_degree=float(az_21[j, i]),
            range_distance_km=float(range_12[i, j]),
            angular_velocity_rate_degree_per_second=float(omega_total_21[j, i]),
            estimated_duration=(
                float(estimated_duration_21[j, i])
                if estimated_duration_12 is not None
                else None
            ),
            range_rate=float(range_rate_12[i, j]),
            flag_elevation=bool(rec_2.el_min_deg <= el_21[j, i] <= rec_2.el_max_deg),
            flag_azimuth=bool(az_rel_21_ji <= rec_2.az_max_deg),  # Bug fix #4
            flag_range=bool(range_12[i, j] <= rec_2.range_max_km),
            flag_angular_velocity=bool(omega_ok_21[j, i]),
            flag_overall=bool(link_ok_21[j, i]),
            flag_bidirectional=bool(bidirectional[i, j]),
        ),
        bidirectional_possible=bool(bidirectional[i, j]),
        selection_score=score,
    )


def _check_pair_feasibility(
    rec_a: _TerminalRecord,
    rec_b: _TerminalRecord,
    angular_velocity_dt_seconds: float = 1.0,
) -> tuple[bool, float, float]:
    """
    Check bidirectional feasibility for one specific terminal pair and estimate
    how long until a currently-infeasible link becomes feasible again.

    Returns
    -------
    feasible         : bool
    alignment_score  : float  — az_rel_ab + az_rel_ba when feasible, inf otherwise
    recover_time_s   : float  — seconds until feasibility recovers (0 if already feasible)

    Fixes applied
    -------------
    Bug fix #1 — angular-velocity term added to compute_recovery_time.
    Bug fix #2 — signed rates used for el, az_rel, range, los.
    Bug fix #6 — CPA-aware ω recovery: previous formula r·(ω/ω_max−1)/ṙ is
                 ill-conditioned near closest approach (ṙ ≈ 0 → t → ∞ or blows
                 up), giving wildly wrong recovery estimates in all four
                 scenarios around CPA:
                   (a) pre-CPA,  ṙ<0, ω rising      → old: inf  (correct: finite)
                   (b) at CPA,   ṙ≈0, ω at peak      → old: inf  (correct: finite)
                   (c) post-CPA, ṙ small, ω falling   → old: 10–25× overestimate
                   (d) well past CPA, ṙ large          → old: reasonable

                 The correct formula uses the closest-approach geometry directly:
                   r_cpa   = |Δr × Δv| / |Δv|        (impact parameter)
                   r_crit  = v_⊥ / ω_max_rad          (range where ω = ω_max)
                   if r_cpa ≥ r_crit: ω never reaches limit → t_ω = inf (wait, we
                     ARE already violated, so this branch only fires if the limit
                     was already breached before CPA geometry applies — treat as inf)
                   else:
                     t_to_cpa  = max(−Δr·Δv / |Δv|², 0)   (time until CPA, ≥ 0)
                     t_after   = √(r_crit² − r_cpa²) / |Δv| (time from CPA to r_crit)
                     t_ω = t_to_cpa + t_after

                 This single expression is accurate for all four scenarios above.
    """
    EPS = 1e-9
    dt = angular_velocity_dt_seconds

    pos_a = rec_a.position_km.reshape(1, 3)
    vel_a = rec_a.velocity_km_s.reshape(1, 3)
    pos_b = rec_b.position_km.reshape(1, 3)
    vel_b = rec_b.velocity_km_s.reshape(1, 3)

    # ─────────────────────────────────────────────
    # Geometry at t0 and t0+dt — one finite-difference step.
    # ─────────────────────────────────────────────
    pos_a_dt = pos_a + vel_a * dt
    pos_b_dt = pos_b + vel_b * dt

    frames_a_t0 = _build_lvlh_frames(pos_a, vel_a)
    frames_b_t0 = _build_lvlh_frames(pos_b, vel_b)
    frames_a_dt = _build_lvlh_frames(pos_a_dt, vel_a)
    frames_b_dt = _build_lvlh_frames(pos_b_dt, vel_b)

    el_ab_arr, az_ab_arr, range_arr = _compute_angles_a_to_b(pos_a, frames_a_t0, pos_b)
    el_ba_arr, az_ba_arr, _ = _compute_angles_a_to_b(pos_b, frames_b_t0, pos_a)
    el_ab_dt_arr, az_ab_dt_arr, range_dt_arr = _compute_angles_a_to_b(
        pos_a_dt, frames_a_dt, pos_b_dt
    )
    el_ba_dt_arr, az_ba_dt_arr, _ = _compute_angles_a_to_b(
        pos_b_dt, frames_b_dt, pos_a_dt
    )

    # ─────────────────────────────────────────────
    # Scalars at t0
    # ─────────────────────────────────────────────
    el_ab = float(el_ab_arr[0, 0])
    az_ab = float(az_ab_arr[0, 0])
    range_val = float(range_arr[0, 0])
    el_ba = float(el_ba_arr[0, 0])
    az_ba = float(az_ba_arr[0, 0])

    # ─────────────────────────────────────────────
    # Boresight-relative azimuth deviations at t0 and t0+dt
    # ─────────────────────────────────────────────
    az_rel_ab = abs(_az_relative(az_ab, rec_a.boresight_az_deg))
    az_rel_ba = abs(_az_relative(az_ba, rec_b.boresight_az_deg))
    az_rel_ab_dt = abs(_az_relative(float(az_ab_dt_arr[0, 0]), rec_a.boresight_az_deg))
    az_rel_ba_dt = abs(_az_relative(float(az_ba_dt_arr[0, 0]), rec_b.boresight_az_deg))

    # ─────────────────────────────────────────────
    # Signed rates — carry sign for recovery estimation (Bug fix #2)
    # ─────────────────────────────────────────────
    el_rate_ab = (float(el_ab_dt_arr[0, 0]) - el_ab) / dt
    el_rate_ba = (float(el_ba_dt_arr[0, 0]) - el_ba) / dt
    az_rel_rate_ab = (az_rel_ab_dt - az_rel_ab) / dt
    az_rel_rate_ba = (az_rel_ba_dt - az_rel_ba) / dt
    range_rate = (float(range_dt_arr[0, 0]) - range_val) / dt

    # ─────────────────────────────────────────────
    # Angular velocity magnitudes at t0
    # ─────────────────────────────────────────────
    d_az_ab = (float(az_ab_dt_arr[0, 0]) - az_ab + 180.0) % 360.0 - 180.0
    d_el_ab = float(el_ab_dt_arr[0, 0]) - el_ab
    omega_ab = float(np.sqrt((d_az_ab / dt) ** 2 + (d_el_ab / dt) ** 2))

    d_az_ba = (float(az_ba_dt_arr[0, 0]) - az_ba + 180.0) % 360.0 - 180.0
    d_el_ba = float(el_ba_dt_arr[0, 0]) - el_ba
    omega_ba = float(np.sqrt((d_az_ba / dt) ** 2 + (d_el_ba / dt) ** 2))

    # ─────────────────────────────────────────────
    # LoS altitude and its signed rate
    # ─────────────────────────────────────────────
    los_alt = float(_compute_los_min_altitude(pos_a, pos_b)[0, 0])
    los_alt_dt = float(_compute_los_min_altitude(pos_a_dt, pos_b_dt)[0, 0])
    los_rate = (los_alt_dt - los_alt) / dt  # km/s, positive = clearing

    los_clear = los_alt >= ATMOSPHERE_EXCLUSION_ZONE_KM

    # ─────────────────────────────────────────────
    # CPA geometry — shared by both terminal directions (Bug fix #6)
    #
    # r_cpa   : closest-approach distance [km] under linear-motion assumption.
    #           Independent of which terminal we're looking at.
    # v_rel   : magnitude of relative velocity [km/s].
    # t_to_cpa: time from t0 until CPA [s], ≥ 0 (0 if already past CPA).
    #           Formula: -Δr·Δv / |Δv|²  (dot-product time-of-closest-approach)
    # ─────────────────────────────────────────────
    rel_pos_vec = (pos_b - pos_a).flatten()  # (3,) km
    rel_vel_vec = (vel_b - vel_a).flatten()  # (3,) km/s
    v_rel_mag = float(np.linalg.norm(rel_vel_vec))
    r_cpa = float(
        np.linalg.norm(np.cross(rel_pos_vec, rel_vel_vec)) / (v_rel_mag + EPS)
    )
    t_to_cpa = max(
        float(-np.dot(rel_pos_vec, rel_vel_vec)) / (v_rel_mag**2 + EPS),
        0.0,
    )

    # ─────────────────────────────────────────────
    # Constraint checks
    # ─────────────────────────────────────────────
    ok_ab = (
        rec_a.el_min_deg <= el_ab <= rec_a.el_max_deg
        and az_rel_ab <= rec_a.az_max_deg
        and range_val <= rec_a.range_max_km
        and omega_ab <= rec_a.max_angular_velocity_deg_s
        and los_clear
    )
    ok_ba = (
        rec_b.el_min_deg <= el_ba <= rec_b.el_max_deg
        and az_rel_ba <= rec_b.az_max_deg
        and range_val <= rec_b.range_max_km
        and omega_ba <= rec_b.max_angular_velocity_deg_s
        and los_clear
    )

    # ─────────────────────────────────────────────
    # Recovery time helper
    # ─────────────────────────────────────────────
    def compute_recovery_time(
        el_: float,
        el_rate_signed: float,
        el_min: float,
        el_max: float,
        az_rel_: float,
        az_rel_rate_signed: float,
        az_max: float,
        rng: float,
        rng_rate_signed: float,
        rng_max: float,
        los_alt_: float,
        los_rate_signed: float,
        los_threshold: float,
        omega_: float,
        omega_max: float,
    ) -> float:
        # --- Elevation -------------------------------------------------------
        if el_ < el_min:
            t_el = (
                (el_min - el_) / (el_rate_signed + EPS)
                if el_rate_signed > 0
                else np.inf
            )
        elif el_ > el_max:
            t_el = (
                (el_ - el_max) / (-el_rate_signed + EPS)
                if el_rate_signed < 0
                else np.inf
            )
        else:
            t_el = 0.0

        # --- Azimuth deviation -----------------------------------------------
        if az_rel_ > az_max:
            t_az = (
                (az_rel_ - az_max) / (-az_rel_rate_signed + EPS)
                if az_rel_rate_signed < 0
                else np.inf
            )
        else:
            t_az = 0.0

        # --- Range -----------------------------------------------------------
        if rng > rng_max:
            t_range = (
                (rng - rng_max) / (-rng_rate_signed + EPS)
                if rng_rate_signed < 0
                else np.inf
            )
        else:
            t_range = 0.0

        # --- Line-of-sight ---------------------------------------------------
        if los_alt_ < los_threshold:
            t_los = (
                (los_threshold - los_alt_) / (los_rate_signed + EPS)
                if los_rate_signed > 0
                else np.inf
            )
        else:
            t_los = 0.0

        # --- Angular velocity (Bug fix #6 — CPA-aware) -----------------------
        #
        # v_⊥ ≈ ω · r is approximately constant across the flyby.
        # r_crit = v_⊥ / ω_max_rad : range at which ω equals ω_max.
        #
        # Recovery timeline:
        #   t_to_cpa  — time from now until closest approach (pre-computed, ≥ 0)
        #   t_after   — time from CPA until r grows back to r_crit
        #             = sqrt(max(r_crit² − r_cpa², 0)) / v_rel
        #
        # This formula works for ALL scenarios:
        #   pre-CPA  : t_to_cpa > 0, t_after > 0  → correct finite sum
        #   at CPA   : t_to_cpa = 0, t_after > 0  → correct
        #   post-CPA : t_to_cpa = 0, t_after computed from current r
        #              (t_after shrinks correctly as r grows)
        #
        # If r_cpa ≥ r_crit the satellites never actually get close enough;
        # but since ω IS currently violated that means we're already inside
        # r_crit on the way in — use t_to_cpa=0 + t_after normally.
        if omega_ > omega_max:
            v_perp_km = omega_ * rng * (np.pi / 180.0)  # km/s  (approx constant)
            r_crit_km = v_perp_km / (omega_max * np.pi / 180.0 + EPS)
            t_after = np.sqrt(max(r_crit_km**2 - r_cpa**2, 0.0)) / (v_rel_mag + EPS)
            t_omega = t_to_cpa + t_after
        else:
            t_omega = 0.0

        return max(t_el, t_az, t_range, t_los, t_omega)

    if not (ok_ab and ok_ba):
        t_rec_ab = compute_recovery_time(
            el_ab,
            el_rate_ab,
            rec_a.el_min_deg,
            rec_a.el_max_deg,
            az_rel_ab,
            az_rel_rate_ab,
            rec_a.az_max_deg,
            range_val,
            range_rate,
            rec_a.range_max_km,
            los_alt,
            los_rate,
            ATMOSPHERE_EXCLUSION_ZONE_KM,
            omega_ab,
            rec_a.max_angular_velocity_deg_s,
        )
        t_rec_ba = compute_recovery_time(
            el_ba,
            el_rate_ba,
            rec_b.el_min_deg,
            rec_b.el_max_deg,
            az_rel_ba,
            az_rel_rate_ba,
            rec_b.az_max_deg,
            range_val,
            range_rate,
            rec_b.range_max_km,
            los_alt,
            los_rate,
            ATMOSPHERE_EXCLUSION_ZONE_KM,
            omega_ba,
            rec_b.max_angular_velocity_deg_s,
        )
        t_recover = max(t_rec_ab, t_rec_ba)
        return False, float("inf"), float(t_recover)

    return True, az_rel_ab + az_rel_ba, 0.0


def _rec_to_possible_link(
    rec_a: _TerminalRecord,
    rec_b: _TerminalRecord,
    score: float,
    angular_velocity_dt_seconds: float = 1.0,
    temporary_unavailable: bool = False,
    estimated_recover_time: float | None = None,
) -> PossibleOpticalLink:
    """
    Build a full PossibleOpticalLink from two records.
    Called only from compute_OISL_feasibility_for_terminal_pair (single-pair path).

    Flags reflect actual constraint state in both the feasible and infeasible
    (temporary_unavailable) cases.  Bug fix #4 applied: flag_azimuth uses the
    boresight-relative deviation, not the raw LVLH azimuth.
    """
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

    los_min_altitude = _compute_los_min_altitude(pos_a, pos_b)
    los_clear = bool(los_min_altitude[0, 0] >= ATMOSPHERE_EXCLUSION_ZONE_KM)

    # Bug fix #4: boresight-relative azimuth for flags
    az_rel_ab_val = abs(_az_relative(float(az_ab[0, 0]), rec_a.boresight_az_deg))
    az_rel_ba_val = abs(_az_relative(float(az_ba[0, 0]), rec_b.boresight_az_deg))

    # Compute actual per-constraint flags (correct for both feasible and infeasible cases)
    flag_el_ab = bool(rec_a.el_min_deg <= float(el_ab[0, 0]) <= rec_a.el_max_deg)
    flag_az_ab = bool(az_rel_ab_val <= rec_a.az_max_deg)
    flag_range_ab = bool(float(range_ab[0, 0]) <= rec_a.range_max_km)
    flag_omega_ab = bool(omega_ab <= rec_a.max_angular_velocity_deg_s)

    flag_el_ba = bool(rec_b.el_min_deg <= float(el_ba[0, 0]) <= rec_b.el_max_deg)
    flag_az_ba = bool(az_rel_ba_val <= rec_b.az_max_deg)
    flag_range_ba = bool(float(range_ab[0, 0]) <= rec_b.range_max_km)
    flag_omega_ba = bool(omega_ba <= rec_b.max_angular_velocity_deg_s)

    flag_overall_ab = (
        flag_el_ab and flag_az_ab and flag_range_ab and flag_omega_ab and los_clear
    )
    flag_overall_ba = (
        flag_el_ba and flag_az_ba and flag_range_ba and flag_omega_ba and los_clear
    )
    flag_bidir = flag_overall_ab and flag_overall_ba

    return PossibleOpticalLink(
        satellite_a=rec_a.terminal.host_satellite,
        satellite_b=rec_b.terminal.host_satellite,
        terminal_a=rec_a.terminal,
        terminal_b=rec_b.terminal,
        constraint_a_to_b=OpticISLVisibilityConstraintResult(
            elevation_angle_degree=float(el_ab[0, 0]),
            azimuth_angle_degree=float(az_ab[0, 0]),
            range_distance_km=float(range_ab[0, 0]),
            range_rate=float(range_rate_ab[0, 0]),
            angular_velocity_rate_degree_per_second=omega_ab,
            flag_elevation=flag_el_ab,
            flag_azimuth=flag_az_ab,
            flag_range=flag_range_ab,
            flag_angular_velocity=flag_omega_ab,
            flag_overall=flag_overall_ab,
            flag_bidirectional=flag_bidir,
            los_min_altitude_km=float(los_min_altitude[0, 0]),
            los_clear=los_clear,
        ),
        constraint_b_to_a=OpticISLVisibilityConstraintResult(
            elevation_angle_degree=float(el_ba[0, 0]),
            azimuth_angle_degree=float(az_ba[0, 0]),
            range_distance_km=float(range_ab[0, 0]),
            range_rate=float(range_rate_ba[0, 0]),
            angular_velocity_rate_degree_per_second=omega_ba,
            flag_elevation=flag_el_ba,
            flag_azimuth=flag_az_ba,
            flag_range=flag_range_ba,
            flag_angular_velocity=flag_omega_ba,
            flag_overall=flag_overall_ba,
            flag_bidirectional=flag_bidir,
            los_min_altitude_km=float(los_min_altitude[0, 0]),
            los_clear=los_clear,
        ),
        bidirectional_possible=flag_bidir,
        selection_score=score,
        temporary_unavailable=temporary_unavailable,
        estimated_recover_time=estimated_recover_time,
    )


# =========================================================================
# PUBLIC API — feasibility check for one specific terminal pair
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
        min_contact_duration=cfg_a.minimum_contact_duration_seconds,
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
        min_contact_duration=cfg_b.minimum_contact_duration_seconds,
    )

    feasible, score, recover_time = _check_pair_feasibility(
        rec_a, rec_b, angular_velocity_dt_seconds
    )
    if not feasible:
        return _rec_to_possible_link(
            rec_a, rec_b, score, angular_velocity_dt_seconds, True, recover_time
        )

    return _rec_to_possible_link(rec_a, rec_b, score, angular_velocity_dt_seconds)


# =========================================================================
# PUBLIC API — inter-shell assignment from terminal pools (with range filter)
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

    n1, n2 = len(terminals_group_1), len(terminals_group_2)

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
        los_clear,
        los_min_altitude,
        link_ok_12,
        link_ok_21,
        bidirectional,
        alignment_score,
        estimated_duration_12,
        estimated_duration_21,
        estimated_duration,
        duration_ok,
        duration_1_ok,
        duration_2_ok,
    ) = _compute_constraint_matrices(records_1, records_2, angular_velocity_dt_seconds)

    # Range pre-filter and cross-shell mask
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

    candidate = bidirectional & range_ok & duration_ok & ~same_shell  # (N, M)

    # Build raw score matrix (lower = better for all strategies)
    if selection_strategy == "best_alignment":
        score_matrix = alignment_score
    elif selection_strategy == "best_angular_velocity":
        score_matrix = omega_total_12
    elif selection_strategy == "shortest_range":
        score_matrix = range_12
    else:  # "estimated_link_duration"
        score_matrix = -estimated_duration  # negate: argmin → longest duration

    # Bug fix #5: use combined estimated_duration (min of both directions),
    # not estimated_duration_12 alone, so that tighter constraints on the
    # group-2 terminal are fully reflected in the selection score.
    if selection_strategy == "estimated_link_duration":
        score_masked = np.where(
            candidate,
            np.where(estimated_duration > 0, -estimated_duration, np.inf),
            np.inf,
        )
    else:
        score_masked = np.where(candidate, score_matrix, np.inf)

    # -----------------------------------------------------------------------
    # Greedy assignment — group 1 priority, one terminal → one connection.
    # Pure numpy indexing, no Python feasibility loop.
    # -----------------------------------------------------------------------
    booked_j: set[int] = set()
    results: list[PossibleOpticalLink] = []

    for i in range(n1):
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
                los_clear,
                los_min_altitude,
                link_ok_12,
                link_ok_21,
                bidirectional,
                float(score_matrix[i, best_j]),
                i,
                best_j,
                estimated_duration_12,
                estimated_duration_21,
            )
        )
        booked_j.add(best_j)

    results.sort(key=lambda x: x.selection_score)
    return results


# =========================================================================
# PUBLIC API — inter-shell assignment from terminal pools (no range filter)
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
        los_clear,
        los_min_altitude,
        link_ok_12,
        link_ok_21,
        bidirectional,
        alignment_score,
        estimated_duration_12,
        estimated_duration_21,
        estimated_duration,
        duration_ok,
        duration_1_ok,
        duration_2_ok,
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
                los_clear,
                los_min_altitude,
                link_ok_12,
                link_ok_21,
                bidirectional,
                float(score_matrix[i, best_j]),
                i,
                best_j,
                estimated_duration_12,
                estimated_duration_21,
            )
        )
        booked_j.add(best_j)

    results.sort(key=lambda x: x.selection_score)
    return results
