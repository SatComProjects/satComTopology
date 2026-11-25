"""Ballard Delta distribution for Earth coverage.

This module distributes a Walker Delta constellation using the geometry of
A. H. Ballard, *Rosette Constellations of Earth Satellites*, IEEE Transactions
on Aerospace and Electronic Systems, vol. AES-16, no. 5, pp. 656-673, 1980.

Two entry points are provided:

- :func:`optimize_delta_phasing` is the layout method.  It takes ``P``, ``Q``,
  inclination and mean motion as fixed mission inputs and selects only the
  inter-plane phasing factor ``F``.
- :func:`optimize_delta_constellation` is the sizing method.  Its fast
  hierarchical search can change the ``T/P/Q`` factorization, inclination and
  altitude.

For the layout method and ``T = P Q`` satellites the distribution is:

- RAAN of plane ``k``: ``360 k / P``
- argument of latitude of satellite ``j`` in plane ``k``:
  ``360 j / Q + 360 F k / T``

The inter-plane phasing factor ``F`` is selected by minimising the worst-case
coverage gap of that exact geometry over one orbital period.  The gap is the
largest angular distance between any point of the sphere and its nearest
satellite subsatellite point, obtained from the spherical Delaunay
triangulation (largest empty circumcircle).  The input values are never
changed.
"""

import math
import warnings
from dataclasses import dataclass, field
from functools import lru_cache
from itertools import combinations
from typing import Iterable, Optional, Sequence

import numpy as np
from scipy.spatial import ConvexHull, QhullError

from sat_com_model.constants import ATMOSPHERE_EXCLUSION_ZONE_KM, MU_KM3_S2, RE_KM

DEFAULT_MIN_ELEVATION_DEG = 10.0
DEFAULT_TIME_SAMPLES = 360
DEFAULT_GRID_POINTS = 20000
DEFAULT_ORDER_K_MAX_SATELLITES = 40
DEFAULT_MAX_PLANE_CANDIDATES = 8
DEFAULT_MAX_PHASING_FACTORS = 16
DEFAULT_MAX_EVALUATIONS = 20000
SECONDS_PER_DAY = 86400.0


@dataclass(frozen=True)
class CoverageEvaluation:
    """Worst-case and best-case coverage of one constellation geometry."""

    max_range_deg: float
    min_range_deg: float
    worst_phase_deg: float
    best_phase_deg: float
    time_uniformity: float
    time_samples: int

    def as_dict(self) -> dict:
        return {
            "max_range_deg": _round(self.max_range_deg),
            "min_range_deg": _round(self.min_range_deg),
            "worst_phase_deg": _round(self.worst_phase_deg),
            "best_phase_deg": _round(self.best_phase_deg),
            "time_uniformity": _round(self.time_uniformity),
            "time_samples": self.time_samples,
        }


@dataclass(frozen=True)
class DeltaCandidate:
    """One evaluated ``T/P/F``/inclination candidate."""

    planes: int
    satellites_per_plane: int
    phasing_factor: int
    inclination_deg: float
    max_coverage_range_deg: float
    min_coverage_range_deg: float = 0.0
    worst_phase_deg: float = 0.0

    @property
    def total_satellites(self) -> int:
        return self.planes * self.satellites_per_plane

    @property
    def walker_notation(self) -> str:
        return f"{self.total_satellites}/{self.planes}/{self.phasing_factor}"

    def as_dict(self) -> dict:
        return {
            "total_satellites": self.total_satellites,
            "walker_notation": self.walker_notation,
            "planes": self.planes,
            "satellites_per_plane": self.satellites_per_plane,
            "phasing_factor": self.phasing_factor,
            "inclination_deg": _round(self.inclination_deg, 4),
            "max_coverage_range_deg": _round(self.max_coverage_range_deg),
            "min_coverage_range_deg": _round(self.min_coverage_range_deg),
            "worst_phase_deg": _round(self.worst_phase_deg),
        }


@dataclass(frozen=True)
class DeltaDesign:
    """Result of the Ballard minimax design."""

    total_satellites: int
    planes: int
    satellites_per_plane: int
    phasing_factor: int
    inclination_deg: float
    altitude_km: float
    mean_revolution_per_day: float
    min_elevation_deg: float
    achieved_min_elevation_deg: float
    coverage_multiplicity: int
    max_coverage_range_deg: float
    min_coverage_range_deg: float
    worst_phase_deg: float
    best_phase_deg: float
    time_uniformity: float
    orbital_period_hours: float
    altitude_mode: str
    time_samples: int
    raan_offset_deg: float = 0.0
    argument_of_latitude_offset_deg: float = 0.0
    candidates: tuple[DeltaCandidate, ...] = field(default_factory=tuple)
    search_truncated: bool = False

    @property
    def walker_notation(self) -> str:
        return f"{self.total_satellites}/{self.planes}/{self.phasing_factor}"

    @property
    def meets_elevation_requirement(self) -> bool:
        return self.achieved_min_elevation_deg + 1e-9 >= self.min_elevation_deg

    def as_dict(self) -> dict:
        return {
            "total_satellites": self.total_satellites,
            "walker_notation": self.walker_notation,
            "planes": self.planes,
            "satellites_per_plane": self.satellites_per_plane,
            "phasing_factor": self.phasing_factor,
            "inclination_deg": _round(self.inclination_deg, 4),
            "altitude_km": _round(self.altitude_km, 3),
            "mean_revolution_per_day": _round(self.mean_revolution_per_day, 6),
            "orbital_period_hours": _round(self.orbital_period_hours, 4),
            "min_elevation_deg": _round(self.min_elevation_deg, 4),
            "achieved_min_elevation_deg": _round(self.achieved_min_elevation_deg, 4),
            "meets_elevation_requirement": self.meets_elevation_requirement,
            "coverage_multiplicity": self.coverage_multiplicity,
            "max_coverage_range_deg": _round(self.max_coverage_range_deg),
            "min_coverage_range_deg": _round(self.min_coverage_range_deg),
            "worst_phase_deg": _round(self.worst_phase_deg),
            "best_phase_deg": _round(self.best_phase_deg),
            "time_uniformity": _round(self.time_uniformity),
            "altitude_mode": self.altitude_mode,
            "time_samples": self.time_samples,
            "raan_offset_deg": _round(self.raan_offset_deg, 4),
            "argument_of_latitude_offset_deg": _round(
                self.argument_of_latitude_offset_deg, 4
            ),
            "search_truncated": self.search_truncated,
            "candidates": [candidate.as_dict() for candidate in self.candidates],
        }

    def as_constellation_property(self, identifier: str) -> dict:
        """Return the fields expected by ``WalkerConstellationProperty``.

        The returned mapping contains no ``design`` block: the numerical search
        has already been done, so a configuration can reuse the result without
        paying the optimization cost again.
        """
        return {
            "identifier": identifier,
            "amount_of_orbit_plane": self.planes,
            "amount_of_satellite_per_orbit_plane": self.satellites_per_plane,
            "inclination": _round(self.inclination_deg, 6),
            "phase_difference_between_satellites": False,
            "mean_revolution_per_day": _round(self.mean_revolution_per_day, 8),
            "phasing_factor": self.phasing_factor,
        }

    def summary(self) -> str:
        return (
            f"{self.walker_notation} (T/P/F), "
            f"i={self.inclination_deg:.2f} deg, "
            f"h={self.altitude_km:.1f} km, "
            f"Rmax={self.max_coverage_range_deg:.2f} deg, "
            f"U_T={self.time_uniformity:.4f}"
        )


def _round(value: float, decimals: int = 6) -> float:
    return float(round(float(value), decimals))


def factorizations(total_satellites: int) -> list[tuple[int, int]]:
    """Return all ordered factorizations ``(P, Q)`` with ``P * Q = T``.

    ``P`` is the number of orbital planes and ``Q`` the number of satellites
    per plane.  ``(3, 4)`` and ``(4, 3)`` are different constellations.
    """
    if total_satellites < 1:
        raise ValueError("total_satellites must be a positive integer")

    result = []
    for planes in range(1, total_satellites + 1):
        if total_satellites % planes == 0:
            result.append((planes, total_satellites // planes))
    return result


def satellite_unit_vectors(
    planes: int,
    satellites_per_plane: int,
    phasing_factor: int,
    inclination_deg: float,
    time_phase_deg: float = 0.0,
    raan_offset_deg: float = 0.0,
    argument_of_latitude_offset_deg: float = 0.0,
) -> np.ndarray:
    """Return the inertial unit vectors of all subsatellite points.

    Parameters
    ----------
    planes, satellites_per_plane
        Walker ``P`` and ``Q``.
    phasing_factor
        Walker ``F``.  The phase of plane ``k`` is ``360 F k / (P Q)``.
    inclination_deg
        Common circular-orbit inclination.
    time_phase_deg
        Argument of latitude added to every satellite, in degrees.  Because all
        satellites share the same mean motion this is a pure time shift.
    raan_offset_deg, argument_of_latitude_offset_deg
        Global rotations of the whole pattern.  They do not change the
        worst-case coverage over the whole sphere, but are kept so the model
        matches the TLE generator exactly.
    """
    if planes < 1 or satellites_per_plane < 1:
        raise ValueError("planes and satellites_per_plane must be positive")

    total_satellites = planes * satellites_per_plane
    plane_index = np.arange(planes)[:, None]
    satellite_index = np.arange(satellites_per_plane)[None, :]

    raan = np.deg2rad(raan_offset_deg + 360.0 * plane_index / planes)
    argument_of_latitude = np.deg2rad(
        argument_of_latitude_offset_deg
        + 360.0 * satellite_index / satellites_per_plane
        + 360.0 * phasing_factor * plane_index / total_satellites
        + time_phase_deg
    )
    inclination = np.deg2rad(inclination_deg)

    x = np.cos(raan) * np.cos(argument_of_latitude) - np.sin(raan) * np.sin(
        argument_of_latitude
    ) * np.cos(inclination)
    y = np.sin(raan) * np.cos(argument_of_latitude) + np.cos(raan) * np.sin(
        argument_of_latitude
    ) * np.cos(inclination)
    z = np.sin(argument_of_latitude) * np.sin(inclination)

    vectors = np.stack(
        [
            np.broadcast_to(x, (planes, satellites_per_plane)),
            np.broadcast_to(y, (planes, satellites_per_plane)),
            np.broadcast_to(z, (planes, satellites_per_plane)),
        ],
        axis=-1,
    ).reshape(-1, 3)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / norms


def satellite_unit_vectors_many(
    planes: int,
    satellites_per_plane: int,
    phasing_factor: int,
    inclination_deg: float,
    time_phases_deg: np.ndarray,
    raan_offset_deg: float = 0.0,
    argument_of_latitude_offset_deg: float = 0.0,
) -> np.ndarray:
    """Vectorised version of :func:`satellite_unit_vectors` over many phases.

    Returns an array of shape ``(number_of_phases, T, 3)``.  Keeping the phase
    axis lets the fast search evaluate a whole orbital period in one einsum
    instead of one Python loop iteration per phase.
    """
    phases = np.asarray(time_phases_deg, dtype=float).reshape(-1)
    plane_index = np.arange(planes)[None, :, None]
    satellite_index = np.arange(satellites_per_plane)[None, None, :]
    total_satellites = planes * satellites_per_plane

    raan = np.deg2rad(raan_offset_deg + 360.0 * plane_index / planes)
    argument_of_latitude = np.deg2rad(
        argument_of_latitude_offset_deg
        + 360.0 * satellite_index / satellites_per_plane
        + 360.0 * phasing_factor * plane_index / total_satellites
        + phases[:, None, None]
    )
    inclination = np.deg2rad(inclination_deg)

    x = np.cos(raan) * np.cos(argument_of_latitude) - np.sin(raan) * np.sin(
        argument_of_latitude
    ) * np.cos(inclination)
    y = np.sin(raan) * np.cos(argument_of_latitude) + np.cos(raan) * np.sin(
        argument_of_latitude
    ) * np.cos(inclination)
    z = np.sin(argument_of_latitude) * np.sin(inclination)

    vectors = np.stack(
        [
            np.broadcast_to(x, (len(phases), planes, satellites_per_plane)),
            np.broadcast_to(y, (len(phases), planes, satellites_per_plane)),
            np.broadcast_to(z, (len(phases), planes, satellites_per_plane)),
        ],
        axis=-1,
    ).reshape(len(phases), -1, 3)
    norms = np.linalg.norm(vectors, axis=2, keepdims=True)
    return vectors / norms


def _triangle_circumradius_deg(
    points: np.ndarray, simplices: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Spherical circumradius of every triangle in ``simplices``.

    Uses Ballard's equidistance relation

    .. math::

        \\sin^2 R = \\frac{4ABC}{(A+B+C)^2-2(A^2+B^2+C^2)}

    with ``A = sin^2(r_ij / 2)``, etc.
    """
    a = points[simplices[:, 0]]
    b = points[simplices[:, 1]]
    c = points[simplices[:, 2]]

    def angular_distance(u: np.ndarray, v: np.ndarray) -> np.ndarray:
        return np.arccos(np.clip(np.sum(u * v, axis=1), -1.0, 1.0))

    side_ab = angular_distance(a, b)
    side_bc = angular_distance(b, c)
    side_ca = angular_distance(c, a)

    A = np.sin(side_ab / 2.0) ** 2
    B = np.sin(side_bc / 2.0) ** 2
    C = np.sin(side_ca / 2.0) ** 2

    denominator = (A + B + C) ** 2 - 2.0 * (A * A + B * B + C * C)
    valid = denominator > 1e-15
    ratio = np.zeros_like(denominator)
    ratio[valid] = 4.0 * A[valid] * B[valid] * C[valid] / denominator[valid]
    radii = np.zeros_like(ratio)
    radii[valid] = np.rad2deg(np.arcsin(np.sqrt(np.clip(ratio[valid], 0.0, 1.0))))
    return radii, valid


def _triangle_circumcenter(
    a: np.ndarray, b: np.ndarray, c: np.ndarray
) -> Optional[tuple[np.ndarray, float]]:
    """Return the small-circle circumcenter and its angular radius."""
    normal = np.cross(a - b, a - c)
    norm = np.linalg.norm(normal)
    if norm < 1e-12:
        return None
    center = normal / norm
    dot = float(np.dot(center, a))
    if dot < 0.0:
        center = -center
        dot = -dot
    radius = math.acos(max(-1.0, min(1.0, dot)))
    return center, radius


def _max_hull_circumradius(
    points: np.ndarray,
) -> Optional[tuple[float, np.ndarray]]:
    """Largest empty spherical circumcircle from the convex hull.

    Each convex-hull facet defines a plane ``n . x = d``.  The cap centred on
    the outward normal has angular radius ``arccos(d)`` and contains no
    satellite: it is an empty coverage gap.  When the origin is outside the
    hull (a very sparse constellation) ``d`` is negative and the gap is larger
    than a hemisphere, which is why the plane distance is used directly rather
    than the ``sin^2 R`` relation alone.
    """
    if len(points) < 4:
        return None
    try:
        hull = ConvexHull(points)
    except (QhullError, ValueError):
        return None

    # ConvexHull.equations rows are [normal, offset] with normal.x + offset <= 0
    # for every input point.  The facet plane is normal.x = -offset.
    distances = np.clip(-hull.equations[:, 3], -1.0, 1.0)
    radii = np.arccos(distances)
    best_index = int(np.argmax(radii))
    return math.degrees(float(radii[best_index])), hull.equations[best_index, :3]


def fibonacci_sphere(number_of_points: int) -> np.ndarray:
    """Return approximately uniform points on the unit sphere."""
    if number_of_points < 1:
        raise ValueError("number_of_points must be positive")
    indices = np.arange(number_of_points) + 0.5
    phi = np.arccos(1.0 - 2.0 * indices / number_of_points)
    theta = math.pi * (1.0 + 5.0**0.5) * indices
    return np.stack(
        [np.cos(theta) * np.sin(phi), np.sin(theta) * np.sin(phi), np.cos(phi)],
        axis=1,
    )


@lru_cache(maxsize=8)
def _cached_fibonacci_sphere(number_of_points: int) -> np.ndarray:
    return fibonacci_sphere(number_of_points)


def _kth_nearest_cosine(cosines: np.ndarray, multiplicity: int) -> np.ndarray:
    """k-th largest cosine for each row (k-th nearest satellite)."""
    number_of_satellites = cosines.shape[1]
    if multiplicity > number_of_satellites:
        return np.full(cosines.shape[0], -1.0)
    index = number_of_satellites - multiplicity
    return np.partition(cosines, index, axis=1)[:, index]


def _grid_covering_radius(
    points: np.ndarray,
    multiplicity: int,
    grid_points: int = DEFAULT_GRID_POINTS,
    refine: bool = True,
) -> tuple[float, np.ndarray]:
    """Fallback/validation coverage radius from a Fibonacci grid."""
    grid = _cached_fibonacci_sphere(grid_points)
    cosines = grid @ points.T
    kth = _kth_nearest_cosine(cosines, multiplicity)
    # The largest angular distance corresponds to the smallest k-th cosine.
    best_index = int(np.argmin(kth))
    best_center = grid[best_index]
    best_angle = math.acos(max(-1.0, min(1.0, float(kth[best_index]))))

    if refine:
        best_angle, best_center = _refine_sphere_point(
            points, best_center, multiplicity, best_angle
        )
    return math.degrees(best_angle), best_center


def _refine_sphere_point(
    points: np.ndarray,
    center: np.ndarray,
    multiplicity: int,
    current_angle: float,
    iterations: int = 4,
) -> tuple[float, np.ndarray]:
    """Local tangent-plane search around a candidate worst point."""
    center = center / np.linalg.norm(center)
    step = min(2.0 * math.degrees(current_angle), 10.0)
    if step <= 0.0:
        step = 1.0

    for _ in range(iterations):
        # Orthonormal tangent basis.
        helper = np.array([0.0, 0.0, 1.0])
        if abs(np.dot(helper, center)) > 0.9:
            helper = np.array([1.0, 0.0, 0.0])
        east = np.cross(helper, center)
        east /= np.linalg.norm(east)
        north = np.cross(center, east)

        angles = np.linspace(0.0, 2.0 * math.pi, 17, endpoint=False)
        radii = np.linspace(step, step / 4.0, 4)
        candidates = [center]
        for radius in radii:
            radius_rad = math.radians(radius)
            for angle in angles:
                direction = math.cos(radius_rad) * center + math.sin(radius_rad) * (
                    math.cos(angle) * east + math.sin(angle) * north
                )
                candidates.append(direction / np.linalg.norm(direction))
        candidates = np.asarray(candidates)

        cosines = candidates @ points.T
        kth = _kth_nearest_cosine(cosines, multiplicity)
        best_index = int(np.argmin(kth))
        candidate_angle = math.acos(max(-1.0, min(1.0, float(kth[best_index]))))
        if candidate_angle > current_angle:
            current_angle = candidate_angle
            center = candidates[best_index]
        step /= 10.0

    return current_angle, center


def _order_k_covering_radius(points: np.ndarray, multiplicity: int) -> float:
    """Exact k-fold coverage radius from order-k Voronoi vertices.

    A maximum of the k-th nearest-satellite distance is attained at the
    circumcenter of three satellites whose circle contains exactly ``k-1``
    other satellites.  Both the small circumcircle and its antipodal
    complement are checked.
    """
    number_of_satellites = len(points)
    if multiplicity > number_of_satellites:
        return 180.0

    best_radius = 0.0
    for i, j, k in combinations(range(number_of_satellites), 3):
        circumcenter = _triangle_circumcenter(points[i], points[j], points[k])
        if circumcenter is None:
            continue
        center, radius = circumcenter
        angles = np.arccos(np.clip(points @ center, -1.0, 1.0))
        # Strictly inside the small circle.  The three hull vertices sit on it.
        inside = int(np.sum(angles < radius - 1e-9))
        if inside == multiplicity - 1:
            best_radius = max(best_radius, radius)

        # The complement circle is centred at -center and has radius pi-radius.
        complement_radius = math.pi - radius
        inside_complement = number_of_satellites - 3 - inside
        if inside_complement == multiplicity - 1:
            best_radius = max(best_radius, complement_radius)

    return math.degrees(best_radius)


def coverage_radius_deg(
    points: np.ndarray,
    multiplicity: int = 1,
    grid_points: int = DEFAULT_GRID_POINTS,
    refine: bool = True,
) -> float:
    """Worst-case angular coverage radius of a set of subsatellite points.

    For ``multiplicity=1`` the exact result comes from the largest empty
    spherical circumcircle (Delaunay triangulation).  For higher multiplicities
    the exact order-k Voronoi construction is used for small constellations and
    a refined Fibonacci grid otherwise.
    """
    if multiplicity < 1:
        raise ValueError("multiplicity must be at least 1")
    points = np.asarray(points, dtype=float)
    if points.ndim != 2 or points.shape[1] != 3:
        raise ValueError("points must be an array of shape (N, 3)")
    points = points / np.linalg.norm(points, axis=1, keepdims=True)

    if len(points) < 4:
        return _grid_covering_radius(
            points, multiplicity, grid_points=max(grid_points, 5000), refine=refine
        )[0]

    if multiplicity == 1:
        hull_result = _max_hull_circumradius(points)
        if hull_result is not None:
            return hull_result[0]
        return _grid_covering_radius(points, multiplicity, grid_points, refine)[0]

    if len(points) <= DEFAULT_ORDER_K_MAX_SATELLITES:
        return _order_k_covering_radius(points, multiplicity)

    return _grid_covering_radius(points, multiplicity, grid_points, refine)[0]


def grid_coverage_radius_deg(
    points: np.ndarray,
    multiplicity: int = 1,
    grid_points: int = DEFAULT_GRID_POINTS,
    refine: bool = True,
) -> float:
    """Independent Fibonacci-grid coverage radius (mainly for validation)."""
    points = np.asarray(points, dtype=float)
    if points.ndim != 2 or points.shape[1] != 3:
        raise ValueError("points must be an array of shape (N, 3)")
    points = points / np.linalg.norm(points, axis=1, keepdims=True)
    return _grid_covering_radius(
        points, multiplicity, grid_points=grid_points, refine=refine
    )[0]


def evaluate_delta_design(
    total_satellites: int,
    planes: int,
    phasing_factor: int,
    inclination_deg: float,
    time_samples: int = DEFAULT_TIME_SAMPLES,
    coverage_multiplicity: int = 1,
    time_refinement_rounds: int = 1,
    raan_offset_deg: float = 0.0,
    argument_of_latitude_offset_deg: float = 0.0,
    grid_points: int = DEFAULT_GRID_POINTS,
    refine_time: bool = True,
) -> CoverageEvaluation:
    """Evaluate one ``T/P/F``/inclination geometry over one orbital period.

    The constellation is sampled at ``time_samples`` equally spaced phases.
    The worst and best samples are refined locally so the reported values do
    not depend on the sample grid.
    """
    if total_satellites % planes != 0:
        raise ValueError("planes must divide total_satellites")
    satellites_per_plane = total_satellites // planes
    if time_samples < 1:
        raise ValueError("time_samples must be at least 1")

    phases = np.linspace(0.0, 360.0, time_samples, endpoint=False)
    ranges = np.empty(time_samples, dtype=float)

    for index, phase in enumerate(phases):
        points = satellite_unit_vectors(
            planes=planes,
            satellites_per_plane=satellites_per_plane,
            phasing_factor=phasing_factor,
            inclination_deg=inclination_deg,
            time_phase_deg=float(phase),
            raan_offset_deg=raan_offset_deg,
            argument_of_latitude_offset_deg=argument_of_latitude_offset_deg,
        )
        ranges[index] = coverage_radius_deg(
            points,
            multiplicity=coverage_multiplicity,
            grid_points=grid_points,
        )

    worst_index = int(np.argmax(ranges))
    best_index = int(np.argmin(ranges))
    worst_phase = float(phases[worst_index])
    best_phase = float(phases[best_index])
    worst_range = float(ranges[worst_index])
    best_range = float(ranges[best_index])

    if refine_time and time_samples > 1:
        step = 360.0 / time_samples
        worst_phase, worst_range = _refine_time_phase(
            total_satellites=total_satellites,
            planes=planes,
            phasing_factor=phasing_factor,
            inclination_deg=inclination_deg,
            center_phase=worst_phase,
            step=step,
            rounds=time_refinement_rounds,
            coverage_multiplicity=coverage_multiplicity,
            raan_offset_deg=raan_offset_deg,
            argument_of_latitude_offset_deg=argument_of_latitude_offset_deg,
            grid_points=grid_points,
        )
        best_phase, best_range = _refine_time_phase(
            total_satellites=total_satellites,
            planes=planes,
            phasing_factor=phasing_factor,
            inclination_deg=inclination_deg,
            center_phase=best_phase,
            step=step,
            rounds=time_refinement_rounds,
            coverage_multiplicity=coverage_multiplicity,
            raan_offset_deg=raan_offset_deg,
            argument_of_latitude_offset_deg=argument_of_latitude_offset_deg,
            grid_points=grid_points,
            maximize=False,
        )

    uniformity = worst_range / best_range if best_range > 0.0 else 1.0
    return CoverageEvaluation(
        max_range_deg=float(worst_range),
        min_range_deg=float(best_range),
        worst_phase_deg=float(worst_phase % 360.0),
        best_phase_deg=float(best_phase % 360.0),
        time_uniformity=float(uniformity),
        time_samples=time_samples,
    )


def _range_at_phase(
    total_satellites: int,
    planes: int,
    phasing_factor: int,
    inclination_deg: float,
    phase: float,
    coverage_multiplicity: int,
    raan_offset_deg: float,
    argument_of_latitude_offset_deg: float,
    grid_points: int,
) -> float:
    points = satellite_unit_vectors(
        planes=planes,
        satellites_per_plane=total_satellites // planes,
        phasing_factor=phasing_factor,
        inclination_deg=inclination_deg,
        time_phase_deg=phase,
        raan_offset_deg=raan_offset_deg,
        argument_of_latitude_offset_deg=argument_of_latitude_offset_deg,
    )
    return coverage_radius_deg(
        points,
        multiplicity=coverage_multiplicity,
        grid_points=grid_points,
    )


def _refine_time_phase(
    total_satellites: int,
    planes: int,
    phasing_factor: int,
    inclination_deg: float,
    center_phase: float,
    step: float,
    rounds: int,
    coverage_multiplicity: int,
    raan_offset_deg: float,
    argument_of_latitude_offset_deg: float,
    grid_points: int,
    maximize: bool = True,
) -> tuple[float, float]:
    """Refine the worst (or best) time phase by repeated local sampling."""
    best_phase = center_phase
    best_value = _range_at_phase(
        total_satellites,
        planes,
        phasing_factor,
        inclination_deg,
        best_phase,
        coverage_multiplicity,
        raan_offset_deg,
        argument_of_latitude_offset_deg,
        grid_points,
    )

    for _ in range(rounds):
        offsets = np.linspace(-step, step, 11)
        for offset in offsets:
            phase = center_phase + float(offset)
            value = _range_at_phase(
                total_satellites,
                planes,
                phasing_factor,
                inclination_deg,
                phase,
                coverage_multiplicity,
                raan_offset_deg,
                argument_of_latitude_offset_deg,
                grid_points,
            )
            if (value > best_value) if maximize else (value < best_value):
                best_value = value
                best_phase = phase
        center_phase = best_phase
        step /= 10.0

    return best_phase, best_value


def coverage_range_for_altitude_deg(
    altitude_km: float, min_elevation_deg: float
) -> float:
    """Great-circle coverage range for a circular orbit at ``altitude_km``."""
    if altitude_km <= 0.0:
        raise ValueError("altitude_km must be positive")
    if not -90.0 < min_elevation_deg < 90.0:
        raise ValueError("min_elevation_deg must be between -90 and 90")
    ratio = RE_KM / (RE_KM + altitude_km) * math.cos(math.radians(min_elevation_deg))
    return math.degrees(math.acos(max(-1.0, min(1.0, ratio)))) - min_elevation_deg


def altitude_for_coverage_range_km(
    coverage_range_deg: float, min_elevation_deg: float
) -> float:
    """Altitude whose coverage circle reaches ``coverage_range_deg``.

    Inverts

    .. math::

        R = \\arccos\\left(\\frac{R_E}{R_E+h}\\cos e_{min}\\right) - e_{min}

    Raises ``ValueError`` when no finite altitude can satisfy the pair.
    """
    if not -90.0 < min_elevation_deg < 90.0:
        raise ValueError("min_elevation_deg must be between -90 and 90")
    if not 0.0 < coverage_range_deg < 180.0:
        raise ValueError("coverage_range_deg must be between 0 and 180")

    denominator = math.cos(math.radians(coverage_range_deg + min_elevation_deg))
    if denominator <= 1e-12:
        raise ValueError(
            "No finite altitude can provide this coverage range at the "
            "requested minimum elevation angle"
        )
    altitude = RE_KM * (math.cos(math.radians(min_elevation_deg)) / denominator - 1.0)
    if altitude <= 0.0:
        raise ValueError("The requested coverage requires a non-positive altitude")
    return altitude


def min_elevation_for_coverage_range_deg(
    coverage_range_deg: float, altitude_km: float
) -> float:
    """Minimum elevation at the edge of a coverage circle of radius ``R``."""
    if altitude_km <= 0.0:
        raise ValueError("altitude_km must be positive")
    if not 0.0 < coverage_range_deg < 180.0:
        raise ValueError("coverage_range_deg must be between 0 and 180")
    ratio = RE_KM / (RE_KM + altitude_km)
    # tan(e) = (cos R - RE/(RE+h)) / sin R
    elevation = math.atan2(
        math.cos(math.radians(coverage_range_deg)) - ratio,
        math.sin(math.radians(coverage_range_deg)),
    )
    return math.degrees(elevation)


def mean_motion_rev_per_day(altitude_km: float) -> float:
    """Circular mean motion in revolutions per solar day."""
    radius = RE_KM + altitude_km
    mean_motion = math.sqrt(MU_KM3_S2 / radius**3)
    return mean_motion * SECONDS_PER_DAY / (2.0 * math.pi)


def altitude_from_mean_motion_km(rev_per_day: float) -> float:
    """Altitude of a circular orbit with the given mean motion."""
    if rev_per_day <= 0.0:
        raise ValueError("rev_per_day must be positive")
    mean_motion = rev_per_day * 2.0 * math.pi / SECONDS_PER_DAY
    radius = (MU_KM3_S2 / mean_motion**2) ** (1.0 / 3.0)
    return radius - RE_KM


def orbital_period_hours(altitude_km: float) -> float:
    """Keplerian period of a circular orbit at ``altitude_km``."""
    radius = RE_KM + altitude_km
    period_seconds = 2.0 * math.pi * math.sqrt(radius**3 / MU_KM3_S2)
    return period_seconds / 3600.0


def intra_plane_link_altitude_km(
    satellites_per_plane: int,
    clearance_km: float = ATMOSPHERE_EXCLUSION_ZONE_KM,
    margin_km: float = 1.0,
) -> float:
    """Minimum altitude for adjacent same-plane ISLs to clear the atmosphere.

    Two adjacent satellites in a plane are separated by ``360 / Q`` degrees.
    The chord between them comes closest to Earth at ``r cos(180 / Q)``.  For
    the link to avoid the atmosphere, that distance must exceed
    ``RE + clearance``.  Returns ``inf`` for ``Q = 2`` (the two satellites are
    opposite each other and every chord passes through the Earth).
    """
    if satellites_per_plane <= 1:
        return 0.0
    if satellites_per_plane == 2:
        return math.inf
    half_angle = math.pi / satellites_per_plane
    return (RE_KM + clearance_km) / math.cos(half_angle) - RE_KM + margin_km


def _resolve_sizing_altitude(
    altitude_mode: str,
    fixed_altitude_km: Optional[float],
    coverage_range_deg: float,
    min_elevation_deg: float,
    satellites_per_plane: int,
    max_altitude_km: Optional[float],
    clearance_km: float = ATMOSPHERE_EXCLUSION_ZONE_KM,
) -> tuple[float, float]:
    """Resolve the sizing altitude while keeping same-plane ISLs clear.

    Coverage-driven altitude is a lower bound, not the final answer: if it is
    too low, adjacent satellites in the same plane cannot see each other over
    the Earth.  In solve mode the altitude is raised to the link-clearance
    value; in fixed mode an explicit error is raised.
    """
    if altitude_mode == "solve":
        altitude_km = altitude_for_coverage_range_km(
            coverage_range_deg, min_elevation_deg
        )
    else:
        if fixed_altitude_km is None:
            raise ValueError(
                "fixed_altitude_km is required when altitude_mode is 'fixed'"
            )
        altitude_km = float(fixed_altitude_km)

    required_altitude = intra_plane_link_altitude_km(satellites_per_plane, clearance_km)
    if altitude_km < required_altitude:
        if altitude_mode == "fixed":
            raise ValueError(
                "The fixed altitude of "
                f"{altitude_km:.1f} km is too low for adjacent same-plane "
                f"ISLs with {satellites_per_plane} satellites per plane. "
                f"Use at least {required_altitude:.1f} km, increase the number "
                "of satellites per plane, or use altitude_mode='solve'."
            )
        altitude_km = required_altitude

    achieved_min_elevation = min_elevation_for_coverage_range_deg(
        coverage_range_deg, altitude_km
    )

    if max_altitude_km is not None and altitude_km > max_altitude_km:
        raise ValueError(
            f"The design requires an altitude of {altitude_km:.1f} km, above "
            f"the configured maximum of {max_altitude_km:.1f} km. Same-plane "
            f"ISL clearance with {satellites_per_plane} satellites per plane "
            f"requires at least {required_altitude:.1f} km. Increase the "
            "ceiling, increase the satellites per plane, or relax the minimum "
            "elevation."
        )

    return altitude_km, achieved_min_elevation


def _select_plane_candidates(
    total_satellites: int,
    plane_counts: Optional[Iterable[int]],
    reference_planes: Optional[int],
    max_plane_candidates: int,
) -> list[int]:
    all_planes = [planes for planes, _ in factorizations(total_satellites)]
    if plane_counts is not None:
        requested = sorted({int(value) for value in plane_counts})
        for value in requested:
            if total_satellites % value != 0:
                raise ValueError(
                    f"plane count {value} does not divide {total_satellites}"
                )
        return requested

    if len(all_planes) <= max_plane_candidates:
        return all_planes

    if reference_planes is not None and total_satellites % reference_planes == 0:
        ordered = sorted(
            all_planes,
            key=lambda value: (abs(math.log(value / reference_planes)), value),
        )
    else:
        target = math.sqrt(total_satellites)
        ordered = sorted(
            all_planes, key=lambda value: (abs(math.log(value / target)), value)
        )
    selected = sorted(ordered[:max_plane_candidates])
    if reference_planes is not None and reference_planes not in selected:
        selected.append(reference_planes)
        selected.sort()
    return selected


def _fast_plane_shortlist(
    total_satellites: int,
    plane_counts: Optional[Iterable[int]],
    reference_planes: Optional[int],
    max_plane_candidates: int,
    max_altitude_km: Optional[float] = None,
) -> list[int]:
    """Pick a diverse, log-spaced set of plane counts for the fast search.

    Picking only the divisors closest to the reference can miss the better
    high-plane-count geometries (for 264 satellites, 33 planes beats 12).
    The shortlist is centred on ``sqrt(T)`` and scaled by 0.5 ... 3.0.
    """
    all_planes = [planes for planes, _ in factorizations(total_satellites)]
    if total_satellites > 12:
        all_planes = [planes for planes in all_planes if 1 < planes < total_satellites]
    if plane_counts is not None:
        available = sorted(
            {int(value) for value in plane_counts if total_satellites % int(value) == 0}
        )
        if not available:
            available = all_planes
    else:
        available = all_planes

    if max_altitude_km is not None:
        available = [
            planes
            for planes in available
            if total_satellites // planes >= 3
            and intra_plane_link_altitude_km(total_satellites // planes)
            <= max_altitude_km
        ]
        if not available:
            raise ValueError(
                "No plane count in the search set can keep same-plane ISLs "
                "clear of the atmosphere within max_altitude_km="
                f"{max_altitude_km:.1f} km."
            )

    if len(available) <= max_plane_candidates:
        return available

    target = math.sqrt(total_satellites)
    chosen: set[int] = set()
    if reference_planes in available:
        chosen.add(reference_planes)

    for scale in (0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0):
        desired = target * scale
        chosen.add(min(available, key=lambda value: abs(math.log(value / desired))))
        if len(chosen) >= max_plane_candidates:
            break

    for value in sorted(available, key=lambda value: abs(math.log(value / target))):
        if len(chosen) >= max_plane_candidates:
            break
        chosen.add(value)

    return sorted(chosen)[:max_plane_candidates]


def _select_phasing_factors(
    planes: int,
    phasing_factors: Optional[Iterable[int]],
    max_phasing_factors: int,
) -> list[int]:
    if phasing_factors is not None:
        requested = sorted({int(value) % planes for value in phasing_factors})
        return requested

    all_factors = list(range(planes))
    if len(all_factors) <= max_phasing_factors:
        return all_factors

    # Keep 0, 1, and evenly spaced values so large plane counts stay tractable.
    selected = {0, 1 % planes}
    stride = max(1, planes // max_phasing_factors)
    selected.update(range(0, planes, stride))
    selected.add(planes - 1)
    return sorted(selected)[:max_phasing_factors]


def _evaluate_candidate(
    total_satellites: int,
    planes: int,
    phasing_factor: int,
    inclination_deg: float,
    time_samples: int,
    coverage_multiplicity: int,
    time_refinement_rounds: int,
    raan_offset_deg: float,
    argument_of_latitude_offset_deg: float,
    grid_points: int,
    refine_time: bool,
) -> CoverageEvaluation:
    return evaluate_delta_design(
        total_satellites=total_satellites,
        planes=planes,
        phasing_factor=phasing_factor,
        inclination_deg=inclination_deg,
        time_samples=time_samples,
        coverage_multiplicity=coverage_multiplicity,
        time_refinement_rounds=time_refinement_rounds,
        raan_offset_deg=raan_offset_deg,
        argument_of_latitude_offset_deg=argument_of_latitude_offset_deg,
        grid_points=grid_points,
        refine_time=refine_time,
    )


def _fast_coverage_radius_deg(
    points: np.ndarray,
    multiplicity: int,
    grid_points: int,
) -> float:
    """Coverage radius on a cached Fibonacci grid, without local refinement.

    Ranking thousands of candidates with a convex hull per orbital phase is
    what made the original search slow.  A 1-4k point grid is enough to rank
    candidates; only the finalists are re-evaluated with the exact spherical
    Delaunay construction.
    """
    grid = _cached_fibonacci_sphere(grid_points)
    kth = _kth_nearest_cosine(grid @ points.T, multiplicity)
    return math.degrees(math.acos(max(-1.0, min(1.0, float(np.min(kth))))))


def _fast_evaluate_candidate(
    total_satellites: int,
    planes: int,
    phasing_factor: int,
    inclination_deg: float,
    time_samples: int,
    coverage_multiplicity: int,
    raan_offset_deg: float,
    argument_of_latitude_offset_deg: float,
    grid_points: int,
) -> tuple[float, float]:
    """Vectorised max-gap evaluation used only for ranking candidates."""
    phases = np.linspace(0.0, 360.0, time_samples, endpoint=False)
    positions = satellite_unit_vectors_many(
        planes=planes,
        satellites_per_plane=total_satellites // planes,
        phasing_factor=phasing_factor,
        inclination_deg=inclination_deg,
        time_phases_deg=phases,
        raan_offset_deg=raan_offset_deg,
        argument_of_latitude_offset_deg=argument_of_latitude_offset_deg,
    )
    grid = _cached_fibonacci_sphere(grid_points)

    # cosines[phase, grid_point, satellite]
    cosines = np.einsum("gk,pnk->pgn", grid, positions, optimize=True)
    if coverage_multiplicity == 1:
        kth = cosines.max(axis=2)
    else:
        index = positions.shape[1] - coverage_multiplicity
        kth = np.partition(cosines, index, axis=2)[:, :, index]

    worst_cosine = kth.min(axis=1)
    angles = np.rad2deg(np.arccos(np.clip(worst_cosine, -1.0, 1.0)))
    best_index = int(np.argmax(angles))
    return float(angles[best_index]), float(phases[best_index])


def _optimize_delta_fast(
    total_satellites: int,
    min_elevation_deg: float,
    coverage_multiplicity: int,
    altitude_mode: str,
    fixed_altitude_km: Optional[float],
    max_altitude_km: Optional[float],
    plane_counts: Optional[Iterable[int]],
    phasing_factors: Optional[Iterable[int]],
    reference_planes: Optional[int],
    reference_phasing_factor: Optional[int],
    inclination_min_deg: float,
    inclination_max_deg: float,
    inclination_step_deg: float,
    inclination_refine_steps_deg: Sequence[float],
    time_samples: int,
    time_refinement_rounds: int,
    max_plane_candidates: int,
    max_phasing_factors: int,
    max_evaluations: int,
    raan_offset_deg: float,
    argument_of_latitude_offset_deg: float,
    grid_points: int,
    finalists: int,
    verbose: bool,
) -> DeltaDesign:
    """Fast hierarchical search used by the default ``search_effort="fast"``.

    The expensive part of the exact method is a convex-hull coverage
    evaluation at every orbital phase.  Here, the shortlisted
    ``P x F x inclination`` grid is ranked on a coarse cached Fibonacci grid;
    only a narrow inclination scan and the final few geometries are evaluated
    with the exact Delaunay construction.  A 264-satellite fleet is designed
    in a few seconds.
    """
    if total_satellites <= 120:
        fast_time_samples = 120
        fast_grid_points = 1024
        finalists = min(finalists, 3)
        scan_configurations = 2
        scan_step = 0.5
        scan_time_samples = 360
    elif total_satellites <= 1000:
        fast_time_samples = 8
        fast_grid_points = 512
        finalists = min(finalists, 2)
        scan_configurations = 1
        scan_step = 0.5
        scan_time_samples = 90
        max_plane_candidates = min(max_plane_candidates, 7)
        max_phasing_factors = min(max_phasing_factors, 6)
    else:
        fast_time_samples = 6
        fast_grid_points = 512
        finalists = min(finalists, 2)
        scan_configurations = 1
        scan_step = 0.5
        scan_time_samples = 60
        max_plane_candidates = min(max_plane_candidates, 5)
        max_phasing_factors = min(max_phasing_factors, 4)

    fast_grid_points = max(256, min(fast_grid_points, grid_points))
    minimum_time_samples = 360 if total_satellites <= 120 else 1
    time_samples = max(time_samples, minimum_time_samples)
    fine_step = (
        max(float(min(inclination_refine_steps_deg)), 0.05)
        if inclination_refine_steps_deg
        else 0.1
    )

    plane_candidates = _fast_plane_shortlist(
        total_satellites,
        plane_counts,
        reference_planes,
        max_plane_candidates,
        max_altitude_km=max_altitude_km,
    )

    def factors_for(planes: int) -> list[int]:
        values = _select_phasing_factors(planes, phasing_factors, max_phasing_factors)
        if len(values) > max_phasing_factors:
            stride = max(1, len(values) // max_phasing_factors)
            values = sorted(set(values[::stride]))[:max_phasing_factors]
        if (
            reference_phasing_factor is not None
            and planes == reference_planes
            and reference_phasing_factor % planes not in values
        ):
            values = sorted(set(values) | {reference_phasing_factor % planes})
        return values

    ranking_step = max(inclination_step_deg, 10.0)
    span = inclination_max_deg - inclination_min_deg
    if span < ranking_step:
        ranking_step = max(inclination_step_deg, span / 2.0)
    inclination_grid = np.clip(
        np.arange(
            inclination_min_deg,
            inclination_max_deg + 0.5 * ranking_step,
            ranking_step,
        ),
        0.0,
        90.0,
    )
    scan_radius = max(ranking_step / 2.0, 2.0)

    # 1. Rank the full shortlisted P x F x inclination grid on the fast grid.
    scored: list[tuple[float, int, int, float]] = []
    search_truncated = False
    for planes in plane_candidates:
        for factor in factors_for(planes):
            for inclination in inclination_grid:
                if len(scored) >= max_evaluations:
                    search_truncated = True
                    break
                value, _ = _fast_evaluate_candidate(
                    total_satellites=total_satellites,
                    planes=planes,
                    phasing_factor=factor,
                    inclination_deg=float(inclination),
                    time_samples=fast_time_samples,
                    coverage_multiplicity=coverage_multiplicity,
                    raan_offset_deg=raan_offset_deg,
                    argument_of_latitude_offset_deg=argument_of_latitude_offset_deg,
                    grid_points=fast_grid_points,
                )
                scored.append((value, planes, factor, float(inclination)))
            if search_truncated:
                break
        if search_truncated:
            break

    if not scored:
        raise RuntimeError("No candidate could be evaluated")
    scored.sort(key=lambda item: item[0])

    # Best candidate for each distinct T/P/F configuration.
    best_by_configuration: dict[tuple[int, int], tuple[float, int, int, float]] = {}
    for item in scored:
        key = (item[1], item[2])
        if key not in best_by_configuration:
            best_by_configuration[key] = item
    ranked_configurations = sorted(
        best_by_configuration.values(), key=lambda item: item[0]
    )

    # 2. Exact inclination scan around the fast winner(s).
    exact_scan: list[tuple[float, int, int, float]] = []
    for _, planes, factor, best_inclination in ranked_configurations[
        :scan_configurations
    ]:
        inclinations = np.clip(
            np.arange(
                best_inclination - scan_radius,
                best_inclination + scan_radius + 0.5 * scan_step,
                scan_step,
            ),
            0.0,
            90.0,
        )
        for inclination in inclinations:
            evaluation = _evaluate_candidate(
                total_satellites=total_satellites,
                planes=planes,
                phasing_factor=factor,
                inclination_deg=float(inclination),
                time_samples=scan_time_samples,
                coverage_multiplicity=coverage_multiplicity,
                time_refinement_rounds=0,
                raan_offset_deg=raan_offset_deg,
                argument_of_latitude_offset_deg=argument_of_latitude_offset_deg,
                grid_points=grid_points,
                refine_time=False,
            )
            exact_scan.append(
                (
                    evaluation.max_range_deg,
                    planes,
                    factor,
                    float(inclination),
                )
            )

    exact_scan.sort(key=lambda item: item[0])
    _, best_planes, best_factor, best_inclination = exact_scan[0]

    # 3. Fine inclination scan around the exact winner.
    fine_inclinations = np.clip(
        np.arange(
            best_inclination - scan_step,
            best_inclination + scan_step + 0.5 * fine_step,
            fine_step,
        ),
        0.0,
        90.0,
    )
    for inclination in fine_inclinations:
        evaluation = _evaluate_candidate(
            total_satellites=total_satellites,
            planes=best_planes,
            phasing_factor=best_factor,
            inclination_deg=float(inclination),
            time_samples=scan_time_samples,
            coverage_multiplicity=coverage_multiplicity,
            time_refinement_rounds=0,
            raan_offset_deg=raan_offset_deg,
            argument_of_latitude_offset_deg=argument_of_latitude_offset_deg,
            grid_points=grid_points,
            refine_time=False,
        )
        exact_scan.append(
            (
                evaluation.max_range_deg,
                best_planes,
                best_factor,
                float(inclination),
            )
        )
    exact_scan.sort(key=lambda item: item[0])

    # 4. Full-time exact evaluation of the finalists.
    finalist_keys: list[tuple[int, int, float]] = []
    for _, planes, factor, inclination in exact_scan:
        key = (planes, factor, round(inclination, 6))
        if key not in finalist_keys:
            finalist_keys.append(key)
        if len(finalist_keys) >= max(1, finalists):
            break

    final_candidates: list[DeltaCandidate] = []
    final_evaluations: dict[DeltaCandidate, CoverageEvaluation] = {}
    for planes, factor, inclination in finalist_keys:
        evaluation = _evaluate_candidate(
            total_satellites=total_satellites,
            planes=planes,
            phasing_factor=factor,
            inclination_deg=inclination,
            time_samples=time_samples,
            coverage_multiplicity=coverage_multiplicity,
            time_refinement_rounds=time_refinement_rounds,
            raan_offset_deg=raan_offset_deg,
            argument_of_latitude_offset_deg=argument_of_latitude_offset_deg,
            grid_points=grid_points,
            refine_time=True,
        )
        final_candidate = DeltaCandidate(
            planes=planes,
            satellites_per_plane=total_satellites // planes,
            phasing_factor=factor,
            inclination_deg=inclination,
            max_coverage_range_deg=evaluation.max_range_deg,
            min_coverage_range_deg=evaluation.min_range_deg,
            worst_phase_deg=evaluation.worst_phase_deg,
        )
        final_evaluations[final_candidate] = evaluation
        final_candidates.append(final_candidate)

    final_candidates.sort(key=lambda candidate: candidate.max_coverage_range_deg)
    best_final = final_candidates[0]
    final_evaluation = final_evaluations[best_final]

    altitude_km, achieved_min_elevation = _resolve_sizing_altitude(
        altitude_mode=altitude_mode,
        fixed_altitude_km=fixed_altitude_km,
        coverage_range_deg=final_evaluation.max_range_deg,
        min_elevation_deg=min_elevation_deg,
        satellites_per_plane=best_final.satellites_per_plane,
        max_altitude_km=max_altitude_km,
    )

    design = DeltaDesign(
        total_satellites=total_satellites,
        planes=best_final.planes,
        satellites_per_plane=best_final.satellites_per_plane,
        phasing_factor=best_final.phasing_factor,
        inclination_deg=best_final.inclination_deg,
        altitude_km=altitude_km,
        mean_revolution_per_day=mean_motion_rev_per_day(altitude_km),
        min_elevation_deg=min_elevation_deg,
        achieved_min_elevation_deg=achieved_min_elevation,
        coverage_multiplicity=coverage_multiplicity,
        max_coverage_range_deg=final_evaluation.max_range_deg,
        min_coverage_range_deg=final_evaluation.min_range_deg,
        worst_phase_deg=final_evaluation.worst_phase_deg,
        best_phase_deg=final_evaluation.best_phase_deg,
        time_uniformity=final_evaluation.time_uniformity,
        orbital_period_hours=orbital_period_hours(altitude_km),
        altitude_mode=altitude_mode,
        time_samples=time_samples,
        raan_offset_deg=raan_offset_deg,
        argument_of_latitude_offset_deg=argument_of_latitude_offset_deg,
        candidates=tuple(final_candidates),
        search_truncated=search_truncated,
    )
    if verbose:
        print(
            f"  fast search: {len(scored)} ranking evaluations, "
            f"{len(exact_scan)} exact scan evaluations, "
            f"{len(final_candidates)} full-time finalists"
        )
        print(design.summary())
    return design


def optimize_delta_constellation(
    total_satellites: int,
    min_elevation_deg: float = DEFAULT_MIN_ELEVATION_DEG,
    coverage_multiplicity: int = 1,
    altitude_mode: str = "solve",
    fixed_altitude_km: Optional[float] = None,
    max_altitude_km: Optional[float] = None,
    plane_counts: Optional[Iterable[int]] = None,
    phasing_factors: Optional[Iterable[int]] = None,
    reference_planes: Optional[int] = None,
    reference_phasing_factor: Optional[int] = None,
    inclination_min_deg: float = 20.0,
    inclination_max_deg: float = 80.0,
    inclination_step_deg: float = 5.0,
    inclination_refine_steps_deg: Sequence[float] = (1.0, 0.1),
    time_samples: int = DEFAULT_TIME_SAMPLES,
    time_refinement_rounds: int = 1,
    max_plane_candidates: int = DEFAULT_MAX_PLANE_CANDIDATES,
    max_phasing_factors: int = DEFAULT_MAX_PHASING_FACTORS,
    max_evaluations: int = DEFAULT_MAX_EVALUATIONS,
    raan_offset_deg: float = 0.0,
    argument_of_latitude_offset_deg: float = 0.0,
    grid_points: int = DEFAULT_GRID_POINTS,
    finalists: int = 5,
    search_effort: str = "fast",
    verbose: bool = False,
) -> DeltaDesign:
    """Minimax design of a Walker Delta constellation.

    Parameters
    ----------
    total_satellites
        Fleet size ``T``.  All factorizations ``T = P Q`` are considered unless
        ``plane_counts`` is supplied.
    min_elevation_deg
        Minimum elevation angle used to select the altitude after the angular
        geometry has been optimized.
    coverage_multiplicity
        Number of satellites that must be visible at the worst-covered point
        (1 = Ballard's single-visibility problem).
    altitude_mode
        ``"solve"`` selects the altitude that makes ``R_max`` reachable at
        ``min_elevation_deg``.  ``"fixed"`` keeps ``fixed_altitude_km``.
    fixed_altitude_km
        Altitude used when ``altitude_mode == "fixed"``.
    max_altitude_km
        Optional operational ceiling.  The search raises when the altitude
        required to meet the minimum elevation exceeds it (for example the
        5880 km near-Earth/deep-space limit of the pyorbital movement model).
    plane_counts, phasing_factors
        Optional explicit search subsets.  In ``fast`` mode these lists are
        capped to keep the runtime bounded; use ``search_effort="thorough"``
        to evaluate them exhaustively.
    reference_planes, reference_phasing_factor
        Current values from the configuration.  They are kept in the shortlist
        when the search has to be pruned.
    inclination_min_deg, inclination_max_deg, inclination_step_deg
        Coarse inclination grid.
    inclination_refine_steps_deg
        Successive local refinement steps around the best inclination.
    time_samples
        Number of orbital phases used to evaluate a candidate.
    max_plane_candidates, max_phasing_factors
        Safety limits for large fleets.  They are ignored when explicit
        candidate lists are supplied.
    max_evaluations
        Hard budget on candidate evaluations.  The search stops early and sets
        ``search_truncated`` when it would be exceeded.
    finalists
        Number of best coarse candidates re-evaluated with the full time grid
        and time refinement.
    search_effort
        ``"fast"`` (default) uses a hierarchical grid-based ranking and
        re-evaluates only a few finalists with the exact Delaunay geometry.
        It returns a 264-satellite design in seconds.  ``"thorough"`` keeps the
        exhaustive ``P x F x inclination`` search and is intended for small
        fleets or offline studies.

    Notes
    -----
    Altitude does not enter the angular geometry: for circular, common-period
    constellations it only changes the elevation angle at which the coverage
    circle is seen.  The search is therefore performed once in angular space
    and the altitude is derived afterwards, exactly as in Ballard's paper.
    """
    if total_satellites < 1:
        raise ValueError("total_satellites must be a positive integer")
    if total_satellites < coverage_multiplicity:
        raise ValueError("coverage_multiplicity cannot exceed the number of satellites")
    if time_samples < 3:
        raise ValueError("time_samples must be at least 3")
    if inclination_min_deg >= inclination_max_deg:
        raise ValueError("inclination_min_deg must be smaller than the maximum")
    if altitude_mode not in {"solve", "fixed"}:
        raise ValueError("altitude_mode must be 'solve' or 'fixed'")
    if altitude_mode == "fixed":
        if fixed_altitude_km is not None and fixed_altitude_km <= 0.0:
            raise ValueError("fixed_altitude_km must be positive")
    if coverage_multiplicity < 1:
        raise ValueError("coverage_multiplicity must be at least 1")
    if search_effort not in {"fast", "thorough"}:
        raise ValueError("search_effort must be 'fast' or 'thorough'")

    if search_effort == "fast":
        return _optimize_delta_fast(
            total_satellites=total_satellites,
            min_elevation_deg=min_elevation_deg,
            coverage_multiplicity=coverage_multiplicity,
            altitude_mode=altitude_mode,
            fixed_altitude_km=fixed_altitude_km,
            max_altitude_km=max_altitude_km,
            plane_counts=plane_counts,
            phasing_factors=phasing_factors,
            reference_planes=reference_planes,
            reference_phasing_factor=reference_phasing_factor,
            inclination_min_deg=inclination_min_deg,
            inclination_max_deg=inclination_max_deg,
            inclination_step_deg=inclination_step_deg,
            inclination_refine_steps_deg=inclination_refine_steps_deg,
            time_samples=time_samples,
            time_refinement_rounds=time_refinement_rounds,
            max_plane_candidates=max_plane_candidates,
            max_phasing_factors=max_phasing_factors,
            max_evaluations=max_evaluations,
            raan_offset_deg=raan_offset_deg,
            argument_of_latitude_offset_deg=argument_of_latitude_offset_deg,
            grid_points=grid_points,
            finalists=finalists,
            verbose=verbose,
        )

    plane_candidates = _select_plane_candidates(
        total_satellites, plane_counts, reference_planes, max_plane_candidates
    )
    if max_altitude_km is not None:
        plane_candidates = [
            planes
            for planes in plane_candidates
            if total_satellites // planes >= 3
            and intra_plane_link_altitude_km(total_satellites // planes)
            <= max_altitude_km
        ]
        if not plane_candidates:
            raise ValueError(
                "No plane count can keep same-plane ISLs clear of the "
                "atmosphere within max_altitude_km="
                f"{max_altitude_km:.1f} km."
            )
    inclination_grid = np.arange(
        inclination_min_deg,
        inclination_max_deg + 0.5 * inclination_step_deg,
        inclination_step_deg,
    )
    inclination_grid = np.clip(inclination_grid, 0.0, 90.0)

    # Small constellations have narrow coverage peaks (Ballard's replication
    # property), so a coarse phase grid can miss the true worst instant.  Use
    # the full 360-sample grid for them regardless of the requested value.
    minimum_time_samples = 360 if total_satellites <= 120 else 1
    time_samples = max(time_samples, minimum_time_samples)

    # Coarse sampling is enough while ranking candidates; the finalists use the
    # requested time grid.  Large fleets have smoother coverage and can be
    # ranked on a smaller grid.
    coarse_time_samples = time_samples
    if total_satellites > 250:
        coarse_time_samples = min(time_samples, 60)
    elif total_satellites > 120:
        coarse_time_samples = min(time_samples, 120)

    evaluations = 0
    search_truncated = False
    coarse_candidates: list[DeltaCandidate] = []
    best: Optional[DeltaCandidate] = None
    best_evaluation: Optional[CoverageEvaluation] = None

    for planes in plane_candidates:
        f_candidates = _select_phasing_factors(
            planes, phasing_factors, max_phasing_factors
        )
        if (
            reference_phasing_factor is not None
            and reference_phasing_factor % planes not in f_candidates
        ):
            f_candidates = sorted(
                set(f_candidates) | {reference_phasing_factor % planes}
            )
        for phasing_factor in f_candidates:
            for inclination in inclination_grid:
                if evaluations >= max_evaluations:
                    search_truncated = True
                    warnings.warn(
                        "Ballard Delta search budget reached; returning the best "
                        "candidate found so far.",
                        RuntimeWarning,
                        stacklevel=2,
                    )
                    break
                evaluation = _evaluate_candidate(
                    total_satellites=total_satellites,
                    planes=planes,
                    phasing_factor=phasing_factor,
                    inclination_deg=float(inclination),
                    time_samples=coarse_time_samples,
                    coverage_multiplicity=coverage_multiplicity,
                    time_refinement_rounds=0,
                    raan_offset_deg=raan_offset_deg,
                    argument_of_latitude_offset_deg=argument_of_latitude_offset_deg,
                    grid_points=grid_points,
                    refine_time=False,
                )
                evaluations += 1
                candidate = DeltaCandidate(
                    planes=planes,
                    satellites_per_plane=total_satellites // planes,
                    phasing_factor=phasing_factor,
                    inclination_deg=float(inclination),
                    max_coverage_range_deg=evaluation.max_range_deg,
                    min_coverage_range_deg=evaluation.min_range_deg,
                    worst_phase_deg=evaluation.worst_phase_deg,
                )
                coarse_candidates.append(candidate)
                if (
                    best is None
                    or candidate.max_coverage_range_deg < best.max_coverage_range_deg
                ):
                    best = candidate
                    best_evaluation = evaluation
            if search_truncated:
                break
        if search_truncated:
            break

    if best is None or best_evaluation is None:
        raise RuntimeError("No candidate could be evaluated")

    # Inclination refinement around the best coarse candidate.
    best_inclination = best.inclination_deg
    for step in inclination_refine_steps_deg:
        offsets = np.linspace(-float(step), float(step), 9)
        for inclination in best_inclination + offsets:
            if inclination < 0.0 or inclination > 90.0:
                continue
            if evaluations >= max_evaluations:
                search_truncated = True
                break
            evaluation = _evaluate_candidate(
                total_satellites=total_satellites,
                planes=best.planes,
                phasing_factor=best.phasing_factor,
                inclination_deg=float(inclination),
                time_samples=coarse_time_samples,
                coverage_multiplicity=coverage_multiplicity,
                time_refinement_rounds=0,
                raan_offset_deg=raan_offset_deg,
                argument_of_latitude_offset_deg=argument_of_latitude_offset_deg,
                grid_points=grid_points,
                refine_time=False,
            )
            evaluations += 1
            candidate = DeltaCandidate(
                planes=best.planes,
                satellites_per_plane=total_satellites // best.planes,
                phasing_factor=best.phasing_factor,
                inclination_deg=float(inclination),
                max_coverage_range_deg=evaluation.max_range_deg,
                min_coverage_range_deg=evaluation.min_range_deg,
                worst_phase_deg=evaluation.worst_phase_deg,
            )
            coarse_candidates.append(candidate)
            if candidate.max_coverage_range_deg < best.max_coverage_range_deg:
                best = candidate
                best_evaluation = evaluation
        best_inclination = best.inclination_deg
        if search_truncated:
            break

    # Re-evaluate the best candidate of each distinct T/P/F configuration with
    # the full time grid so coarse sampling cannot hide a worse phase, and so
    # the comparison table shows different geometries rather than neighbouring
    # inclinations of the same one.
    best_per_configuration: dict[tuple[int, int, int], DeltaCandidate] = {}
    for candidate in coarse_candidates:
        key = (
            candidate.planes,
            candidate.phasing_factor,
            candidate.satellites_per_plane,
        )
        current = best_per_configuration.get(key)
        if (
            current is None
            or candidate.max_coverage_range_deg < current.max_coverage_range_deg
        ):
            best_per_configuration[key] = candidate
    candidates_to_recheck = sorted(
        best_per_configuration.values(),
        key=lambda candidate: candidate.max_coverage_range_deg,
    )[: max(1, finalists)]
    final_candidates: list[DeltaCandidate] = []
    final_evaluations: dict[DeltaCandidate, CoverageEvaluation] = {}

    for candidate in candidates_to_recheck:
        evaluation = _evaluate_candidate(
            total_satellites=total_satellites,
            planes=candidate.planes,
            phasing_factor=candidate.phasing_factor,
            inclination_deg=candidate.inclination_deg,
            time_samples=time_samples,
            coverage_multiplicity=coverage_multiplicity,
            time_refinement_rounds=time_refinement_rounds,
            raan_offset_deg=raan_offset_deg,
            argument_of_latitude_offset_deg=argument_of_latitude_offset_deg,
            grid_points=grid_points,
            refine_time=True,
        )
        final_candidate = DeltaCandidate(
            planes=candidate.planes,
            satellites_per_plane=candidate.satellites_per_plane,
            phasing_factor=candidate.phasing_factor,
            inclination_deg=candidate.inclination_deg,
            max_coverage_range_deg=evaluation.max_range_deg,
            min_coverage_range_deg=evaluation.min_range_deg,
            worst_phase_deg=evaluation.worst_phase_deg,
        )
        final_evaluations[final_candidate] = evaluation
        final_candidates.append(final_candidate)

    final_candidates.sort(key=lambda candidate: candidate.max_coverage_range_deg)
    best_final = final_candidates[0]
    final_evaluation = final_evaluations[best_final]

    altitude_km, achieved_min_elevation = _resolve_sizing_altitude(
        altitude_mode=altitude_mode,
        fixed_altitude_km=fixed_altitude_km,
        coverage_range_deg=final_evaluation.max_range_deg,
        min_elevation_deg=min_elevation_deg,
        satellites_per_plane=best_final.satellites_per_plane,
        max_altitude_km=max_altitude_km,
    )
    period_hours = orbital_period_hours(altitude_km)
    mean_motion = mean_motion_rev_per_day(altitude_km)

    design = DeltaDesign(
        total_satellites=total_satellites,
        planes=best_final.planes,
        satellites_per_plane=best_final.satellites_per_plane,
        phasing_factor=best_final.phasing_factor,
        inclination_deg=best_final.inclination_deg,
        altitude_km=altitude_km,
        mean_revolution_per_day=mean_motion,
        min_elevation_deg=min_elevation_deg,
        achieved_min_elevation_deg=achieved_min_elevation,
        coverage_multiplicity=coverage_multiplicity,
        max_coverage_range_deg=final_evaluation.max_range_deg,
        min_coverage_range_deg=final_evaluation.min_range_deg,
        worst_phase_deg=final_evaluation.worst_phase_deg,
        best_phase_deg=final_evaluation.best_phase_deg,
        time_uniformity=final_evaluation.time_uniformity,
        orbital_period_hours=period_hours,
        altitude_mode=altitude_mode,
        time_samples=time_samples,
        raan_offset_deg=raan_offset_deg,
        argument_of_latitude_offset_deg=argument_of_latitude_offset_deg,
        candidates=tuple(final_candidates),
        search_truncated=search_truncated,
    )

    if verbose:
        print(design.summary())
        print(
            f"Evaluated {evaluations} coarse candidates; "
            f"best of {len(final_candidates)} finalists rechecked."
        )

    return design


def optimize_delta_phasing(
    planes: int,
    satellites_per_plane: int,
    inclination_deg: float,
    mean_revolution_per_day: float,
    min_elevation_deg: float = DEFAULT_MIN_ELEVATION_DEG,
    coverage_multiplicity: int = 1,
    phasing_factors: Optional[Iterable[int]] = None,
    time_samples: int = DEFAULT_TIME_SAMPLES,
    time_refinement_rounds: int = 1,
    search_effort: str = "fast",
    raan_offset_deg: float = 0.0,
    argument_of_latitude_offset_deg: float = 0.0,
    grid_points: int = DEFAULT_GRID_POINTS,
    finalists: int = 3,
    verbose: bool = False,
) -> DeltaDesign:
    """Ballard distribution for a **fixed** ``P x Q``/inclination/altitude.

    This is the layout-only method: the plane count, satellites per plane,
    inclination and mean motion are taken as mission inputs and are never
    changed.  Only the inter-plane phasing factor ``F`` is selected, by
    minimising the worst-case coverage gap of the given geometry over one
    orbital period.  The resulting TLEs use

    .. math::

        u_{k,j} = 360 j / Q + 360 F k / (P Q)

    with uniformly spaced RAANs ``360 k / P``.

    """
    if planes < 1 or satellites_per_plane < 1:
        raise ValueError("planes and satellites_per_plane must be positive")
    if mean_revolution_per_day <= 0.0:
        raise ValueError("mean_revolution_per_day must be positive")
    if coverage_multiplicity < 1:
        raise ValueError("coverage_multiplicity must be at least 1")
    if search_effort not in {"fast", "thorough"}:
        raise ValueError("search_effort must be 'fast' or 'thorough'")

    total_satellites = planes * satellites_per_plane
    if coverage_multiplicity > total_satellites:
        raise ValueError("coverage_multiplicity cannot exceed the number of satellites")

    minimum_time_samples = 360 if total_satellites <= 120 else 1
    time_samples = max(time_samples, minimum_time_samples)

    if phasing_factors is None:
        candidates = list(range(planes))
    else:
        candidates = sorted({int(value) % planes for value in phasing_factors})
    if not candidates:
        raise ValueError("No phasing factor candidate to evaluate")

    evaluations: list[tuple[float, int]] = []
    if search_effort == "fast":
        if total_satellites <= 120:
            fast_samples, fast_grid = 120, 1024
        elif total_satellites <= 1000:
            fast_samples, fast_grid = 8, 512
        else:
            fast_samples, fast_grid = 6, 512
        fast_grid = max(256, min(fast_grid, grid_points))
        for factor in candidates:
            value, _ = _fast_evaluate_candidate(
                total_satellites=total_satellites,
                planes=planes,
                phasing_factor=factor,
                inclination_deg=inclination_deg,
                time_samples=fast_samples,
                coverage_multiplicity=coverage_multiplicity,
                raan_offset_deg=raan_offset_deg,
                argument_of_latitude_offset_deg=argument_of_latitude_offset_deg,
                grid_points=fast_grid,
            )
            evaluations.append((value, factor))
        evaluations.sort(key=lambda item: item[0])
        finalist_factors = [factor for _, factor in evaluations[: max(1, finalists)]]
    else:
        finalist_factors = candidates

    exact_evaluations: list[tuple[float, int, CoverageEvaluation]] = []
    for factor in finalist_factors:
        evaluation = _evaluate_candidate(
            total_satellites=total_satellites,
            planes=planes,
            phasing_factor=factor,
            inclination_deg=inclination_deg,
            time_samples=time_samples,
            coverage_multiplicity=coverage_multiplicity,
            time_refinement_rounds=time_refinement_rounds,
            raan_offset_deg=raan_offset_deg,
            argument_of_latitude_offset_deg=argument_of_latitude_offset_deg,
            grid_points=grid_points,
            refine_time=True,
        )
        exact_evaluations.append((evaluation.max_range_deg, factor, evaluation))
    exact_evaluations.sort(key=lambda item: item[0])

    best_range, best_factor, best_evaluation = exact_evaluations[0]
    altitude_km = altitude_from_mean_motion_km(mean_revolution_per_day)
    achieved_min_elevation = min_elevation_for_coverage_range_deg(
        best_range, altitude_km
    )

    candidates_out = tuple(
        DeltaCandidate(
            planes=planes,
            satellites_per_plane=satellites_per_plane,
            phasing_factor=factor,
            inclination_deg=inclination_deg,
            max_coverage_range_deg=evaluation.max_range_deg,
            min_coverage_range_deg=evaluation.min_range_deg,
            worst_phase_deg=evaluation.worst_phase_deg,
        )
        for _, factor, evaluation in exact_evaluations
    )

    design = DeltaDesign(
        total_satellites=total_satellites,
        planes=planes,
        satellites_per_plane=satellites_per_plane,
        phasing_factor=best_factor,
        inclination_deg=inclination_deg,
        altitude_km=altitude_km,
        mean_revolution_per_day=mean_revolution_per_day,
        min_elevation_deg=min_elevation_deg,
        achieved_min_elevation_deg=achieved_min_elevation,
        coverage_multiplicity=coverage_multiplicity,
        max_coverage_range_deg=best_evaluation.max_range_deg,
        min_coverage_range_deg=best_evaluation.min_range_deg,
        worst_phase_deg=best_evaluation.worst_phase_deg,
        best_phase_deg=best_evaluation.best_phase_deg,
        time_uniformity=best_evaluation.time_uniformity,
        orbital_period_hours=orbital_period_hours(altitude_km),
        altitude_mode="fixed",
        time_samples=time_samples,
        raan_offset_deg=raan_offset_deg,
        argument_of_latitude_offset_deg=argument_of_latitude_offset_deg,
        candidates=candidates_out,
    )
    if verbose:
        print(
            f"  layout search: {len(candidates)} F values ranked, "
            f"{len(exact_evaluations)} exact finalists; "
            f"P/Q/i/h preserved"
        )
        print(design.summary())
    return design


def validate_design(
    design: DeltaDesign,
    time_samples: int = DEFAULT_TIME_SAMPLES,
    grid_points: int = 200000,
    coverage_multiplicity: Optional[int] = None,
) -> dict:
    """Independent dense-grid validation of a design's angular coverage.

    The optimizer itself uses Delaunay triangulation.  This validation samples
    the sphere with a much denser Fibonacci grid and reports the worst gap, so
    the result does not rely solely on the same geometric construction.
    """
    multiplicity = coverage_multiplicity or design.coverage_multiplicity
    phases = np.linspace(0.0, 360.0, time_samples, endpoint=False)
    worst_range = 0.0
    worst_phase = 0.0

    for phase in phases:
        points = satellite_unit_vectors(
            planes=design.planes,
            satellites_per_plane=design.satellites_per_plane,
            phasing_factor=design.phasing_factor,
            inclination_deg=design.inclination_deg,
            time_phase_deg=float(phase),
            raan_offset_deg=design.raan_offset_deg,
            argument_of_latitude_offset_deg=design.argument_of_latitude_offset_deg,
        )
        value = _grid_covering_radius(
            points,
            multiplicity=multiplicity,
            grid_points=grid_points,
            refine=True,
        )[0]
        if value > worst_range:
            worst_range = value
            worst_phase = float(phase)

    return {
        "max_coverage_range_deg": _round(worst_range),
        "worst_phase_deg": _round(worst_phase),
        "time_samples": time_samples,
        "grid_points": grid_points,
        "coverage_multiplicity": multiplicity,
        "optimizer_max_coverage_range_deg": _round(design.max_coverage_range_deg),
        "difference_deg": _round(worst_range - design.max_coverage_range_deg),
    }
