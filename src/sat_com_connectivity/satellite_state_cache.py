"""
Satellite state cache shared by every connectivity computation of a simulation.

One `SatelliteStateCache` lives in the SimulationManager. Ground-to-space
strategies, inter-satellite strategies and addressing plans all read satellite
state through it, so each satellite is converted at most once per simulation
time step, whatever the number of ground objects, shells or phases.

Validity
--------
Every entry belongs to one simulation time (an "epoch"), read from the
satellite movement model clock (`MovementModel.get_datetime()`). As soon as a
satellite reports another time, the whole cache is dropped. The
SimulationManager also calls `invalidate()` at the start of each tick, which
covers movement models whose clock never changes (test doubles).

All satellites of a simulation follow the same SimulationTimeManager, so a
single epoch is enough.

Every cached array is read-only: one array is shared by many consumers, so an
in-place modification would silently corrupt the others.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from sat_com_connectivity.utils import satellites_to_ecef

if TYPE_CHECKING:
    from sat_com_model.models import MovementModel, Satellite

# Epoch of an empty cache. Never equal to any datetime.
_NO_EPOCH = object()


def _read_only(array: np.ndarray) -> np.ndarray:
    array.flags.writeable = False
    return array


def build_lvlh_frames(positions: np.ndarray, velocities: np.ndarray) -> np.ndarray:
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


class EciCache:
    """
    Lazy per-satellite ECI cache for one finite-difference step `dt`.

    Stores for every satellite:
      - position / velocity / LVLH frame at current time (t)
      - position / velocity / LVLH frame at t + dt

    Entries are keyed by movement model: the ECI state is a function of the
    movement model and its clock only. The models are kept referenced so their
    `id()` cannot be reused while the cache holds their entries.

    `dt` is fixed at construction. Never use a cache with another
    `angular_velocity_dt_seconds` than its own `dt`: the angular velocities and
    range rates would be wrong. Use `SatelliteStateCache.eci(dt)` to get the
    right one.
    """

    def __init__(self, dt: float = 0.0):
        self.dt = float(dt)
        self._epoch = _NO_EPOCH
        self._models: dict[int, MovementModel] = {}

        self._pos: dict[int, np.ndarray] = {}
        self._vel: dict[int, np.ndarray] = {}
        self.lvlh_frames: dict[int, np.ndarray] = {}

        self._pos_dt: dict[int, np.ndarray] = {}
        self._vel_dt: dict[int, np.ndarray] = {}
        self.lvlh_frames_dt: dict[int, np.ndarray] = {}

    def invalidate(self) -> None:
        """Drop every entry."""
        self._epoch = _NO_EPOCH
        self._models.clear()
        self._pos.clear()
        self._vel.clear()
        self.lvlh_frames.clear()
        self._pos_dt.clear()
        self._vel_dt.clear()
        self.lvlh_frames_dt.clear()

    def _key(self, sat: Satellite) -> int:
        """Cache key of a satellite. Drops the cache if the simulation time moved."""
        movement_model = sat.get_movement_model()
        now = movement_model.get_datetime()
        if now != self._epoch:
            self.invalidate()
            self._epoch = now
        key = id(movement_model)
        if key not in self._models:
            self._models[key] = movement_model
        return key

    def _ensure_state(self, key: int) -> None:
        if key not in self._pos:
            movement_model = self._models[key]
            self._pos[key] = _read_only(
                np.asarray(
                    movement_model.get_position_earth_general_inertial(), dtype=float
                ).flatten()[:3]
            )
            self._vel[key] = _read_only(
                np.asarray(
                    movement_model.get_velocity_earth_general_inertial(), dtype=float
                ).flatten()[:3]
            )

    def _ensure_state_dt(self, key: int) -> None:
        """
        Position & velocity at t + dt.
        Uses linear propagation (pos + vel*dt) — accurate enough for dt ≈ 1 s.
        """
        if key not in self._pos_dt:
            self._ensure_state(key)
            self._pos_dt[key] = _read_only(self._pos[key] + self._vel[key] * self.dt)
            self._vel_dt[key] = self._vel[key]

    def get(self, sat: Satellite) -> tuple[np.ndarray, np.ndarray]:
        key = self._key(sat)
        self._ensure_state(key)
        return self._pos[key], self._vel[key]

    def get_lvlh_frames(self, sat: Satellite) -> np.ndarray:
        key = self._key(sat)
        if key not in self.lvlh_frames:
            self._ensure_state(key)
            self.lvlh_frames[key] = _read_only(
                build_lvlh_frames(
                    self._pos[key].reshape(1, 3), self._vel[key].reshape(1, 3)
                )[0]
            )
        return self.lvlh_frames[key]

    def get_dt(self, sat: Satellite) -> tuple[np.ndarray, np.ndarray]:
        """Position & velocity at t + dt."""
        key = self._key(sat)
        self._ensure_state_dt(key)
        return self._pos_dt[key], self._vel_dt[key]

    def get_lvlh_frames_dt(self, sat: Satellite) -> np.ndarray:
        """LVLH frame at t + self.dt."""
        key = self._key(sat)
        if key not in self.lvlh_frames_dt:
            self._ensure_state_dt(key)
            self.lvlh_frames_dt[key] = _read_only(
                build_lvlh_frames(
                    self._pos_dt[key].reshape(1, 3), self._vel_dt[key].reshape(1, 3)
                )[0]
            )
        return self.lvlh_frames_dt[key]

    def warm_all_lvlh_frames(self) -> None:
        """
        Vectorised LVLH construction, for both t and t+dt, of every cached
        satellite that has no frame yet. Frames already computed are kept.
        """
        missing = [key for key in self._pos if key not in self.lvlh_frames]
        if missing:
            frames = build_lvlh_frames(
                np.stack([self._pos[key] for key in missing]),
                np.stack([self._vel[key] for key in missing]),
            )
            for key, frame in zip(missing, frames):
                self.lvlh_frames[key] = _read_only(frame)

        if self.dt != 0.0:
            missing_dt = [key for key in self._pos if key not in self.lvlh_frames_dt]
            if missing_dt:
                for key in missing_dt:
                    self._ensure_state_dt(key)
                frames_dt = build_lvlh_frames(
                    np.stack([self._pos_dt[key] for key in missing_dt]),
                    np.stack([self._vel_dt[key] for key in missing_dt]),
                )
                for key, frame in zip(missing_dt, frames_dt):
                    self.lvlh_frames_dt[key] = _read_only(frame)

    def warm(self, satellites: list[Satellite]) -> None:
        for sat in satellites:
            self.get(sat)
            if self.dt != 0.0:
                self.get_dt(sat)
        self.warm_all_lvlh_frames()

    def __len__(self) -> int:
        return len(self._pos)


class SatelliteStateCache:
    """
    Simulation-wide satellite state cache. See the module docstring.

    - `eci(dt)`: ECI positions / velocities / LVLH frames, used by the optical
      inter-satellite link computations. One `EciCache` per `dt`.
    - `ground_ecef(satellites)`: ECEF positions computed from the satellites
      geodetic coordinates, used by the ground-to-space visibility.
    """

    def __init__(self):
        self._eci_caches: dict[float, EciCache] = {}
        self._ground_epoch = _NO_EPOCH
        # key: id() of every satellite, in order. The satellite list is kept
        # so the ids stay valid as long as the entry exists.
        self._ground_ecef: dict[tuple[int, ...], tuple[list[Satellite], np.ndarray]] = (
            {}
        )

    def eci(self, dt: float = 0.0) -> EciCache:
        """The ECI cache for finite-difference step `dt` (seconds)."""
        dt = float(dt)
        cache = self._eci_caches.get(dt)
        if cache is None:
            cache = self._eci_caches[dt] = EciCache(dt)
        return cache

    def ground_ecef(self, satellites: list[Satellite]) -> np.ndarray:
        """
        Same array as `satellites_to_ecef(satellites)`, computed once per
        satellite list and simulation time. Read-only.
        """
        if not satellites:
            return satellites_to_ecef(satellites)

        now = satellites[0].get_movement_model().get_datetime()
        if now != self._ground_epoch:
            self._ground_ecef.clear()
            self._ground_epoch = now

        key = tuple(map(id, satellites))
        entry = self._ground_ecef.get(key)
        if entry is None:
            entry = (list(satellites), _read_only(satellites_to_ecef(satellites)))
            self._ground_ecef[key] = entry
        return entry[1]

    def distances_km(
        self, satellite_pairs: list[tuple[Satellite, Satellite]]
    ) -> np.ndarray:
        """
        Straight-line distance (km) between the satellites of each pair, from
        their ECI positions (SGP4), shape (len(satellite_pairs),).
        """
        if not satellite_pairs:
            return np.empty(0)
        # Positions do not depend on dt: any ECI cache gives the same values.
        cache = self.eci(0.0)
        positions_a = np.stack([cache.get(sat_a)[0] for sat_a, _ in satellite_pairs])
        positions_b = np.stack([cache.get(sat_b)[0] for _, sat_b in satellite_pairs])
        return np.linalg.norm(positions_a - positions_b, axis=1)

    def invalidate(self) -> None:
        """Drop every entry. Called by the SimulationManager at each tick."""
        for cache in self._eci_caches.values():
            cache.invalidate()
        self._ground_ecef.clear()
        self._ground_epoch = _NO_EPOCH
