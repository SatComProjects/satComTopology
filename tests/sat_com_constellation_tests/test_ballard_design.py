import math

import numpy as np
import pytest

from sat_com_constellation.models import (
    DeltaDesignProperty,
    WalkerConstellationProperty,
    WalkerDeltaConstellation,
    WalkerStarConstellation,
)
from sat_com_constellation.walker_constellation.ballard_design import (
    _triangle_circumradius_deg,
    altitude_from_mean_motion_km,
    coverage_radius_deg,
    evaluate_delta_design,
    fibonacci_sphere,
    grid_coverage_radius_deg,
    intra_plane_link_altitude_km,
    min_elevation_for_coverage_range_deg,
    optimize_delta_constellation,
    optimize_delta_phasing,
    orbital_period_hours,
    satellite_unit_vectors,
    satellite_unit_vectors_many,
    validate_design,
)
from sat_com_builder.links.inter_satellite_link_generator import (
    _walker_delta_wrap_shift,
    generate_walker_delta_constellation_grid,
)
from sat_com_model.constants import ATMOSPHERE_EXCLUSION_ZONE_KM, RE_KM
from sat_com_model.models import InterSatelliteLinkDirection
from sat_com_constellation.walker_constellation.walker_propagation import (
    generate_two_line_elements,
)


def test_ballard_equidistance_formula_matches_plane_geometry():
    points = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ]
    )
    radii, valid = _triangle_circumradius_deg(points, np.array([[0, 1, 2]]))

    assert valid[0]
    assert radii[0] == pytest.approx(math.degrees(math.acos(1.0 / math.sqrt(3.0))))


def test_ballard_12_3_1_reproduces_published_worst_case():
    """Ballard's Table I: 12/3/1 at 50.73 deg gives Rmax = 47.90 deg."""
    evaluation = evaluate_delta_design(
        total_satellites=12,
        planes=3,
        phasing_factor=1,
        inclination_deg=50.73,
        time_samples=360,
        time_refinement_rounds=1,
    )

    assert evaluation.max_range_deg == pytest.approx(47.90, abs=0.05)
    assert evaluation.min_range_deg == pytest.approx(46.96, abs=0.05)
    assert evaluation.time_uniformity == pytest.approx(1.020, abs=0.002)
    # The replication interval is 30 deg and the critical phase is 15 deg.
    assert evaluation.worst_phase_deg % 30.0 == pytest.approx(15.0, abs=0.5)


def test_ballard_altitude_and_period_are_consistent():
    coverage_range = 47.90
    altitude = altitude_from_mean_motion_km(6.7553)

    assert altitude == pytest.approx(5440.0, abs=20.0)
    assert altitude / 6378.135 == pytest.approx(0.853, abs=0.002)
    assert orbital_period_hours(altitude) == pytest.approx(3.55, abs=0.02)
    assert min_elevation_for_coverage_range_deg(
        coverage_range, altitude
    ) == pytest.approx(10.0, abs=0.01)


def test_layout_phasing_selects_the_ballard_reference_factor():
    """Layout mode keeps the geometry and selects F=1 for the 12/3/1 rosette."""
    constellation = WalkerDeltaConstellation(
        WalkerConstellationProperty(
            identifier="Ballard Reference",
            amount_of_orbit_plane=3,
            amount_of_satellite_per_orbit_plane=4,
            inclination=50.73,
            phase_difference_between_satellites=False,
            mean_revolution_per_day=6.7553,
            design=DeltaDesignProperty(time_samples=360),
        )
    )

    assert constellation.design_result is not None
    assert constellation.design_result.altitude_mode == "fixed"
    assert constellation.amount_of_orbit_plane == 3
    assert constellation.amount_of_satellite_per_orbit_plane == 4
    assert constellation.inclination == 50.73
    assert constellation.mean_revolution_per_day == 6.7553
    assert constellation.phasing_factor == 1
    assert constellation.design_result.max_coverage_range_deg == pytest.approx(
        47.90, abs=0.05
    )
    assert constellation.design_result.meets_elevation_requirement
    assert len(constellation.generated_two_line_elements) == 12

    mean_anomalies = [
        round(float(tle.line2[43:51]), 3)
        for tle in constellation.generated_two_line_elements
    ]
    assert mean_anomalies[:8] == [
        0.0,
        90.0,
        180.0,
        270.0,
        30.0,
        120.0,
        210.0,
        300.0,
    ]


def test_layout_phasing_can_pin_a_factor_and_preserves_inputs():
    constellation = WalkerDeltaConstellation(
        WalkerConstellationProperty(
            identifier="Pinned Layout",
            amount_of_orbit_plane=3,
            amount_of_satellite_per_orbit_plane=4,
            inclination=53.0,
            phase_difference_between_satellites=True,
            mean_revolution_per_day=15.5,
            design=DeltaDesignProperty(phasing_factors=[1], time_samples=360),
        )
    )

    assert constellation.amount_of_orbit_plane == 3
    assert constellation.amount_of_satellite_per_orbit_plane == 4
    assert constellation.inclination == 53.0
    assert constellation.mean_revolution_per_day == 15.5
    assert constellation.phasing_factor == 1
    assert len(constellation.generated_two_line_elements) == 12


def test_layout_phasing_searches_without_changing_inputs():
    constellation = WalkerDeltaConstellation(
        WalkerConstellationProperty(
            identifier="Searched Layout",
            amount_of_orbit_plane=3,
            amount_of_satellite_per_orbit_plane=4,
            inclination=53.0,
            phase_difference_between_satellites=True,
            mean_revolution_per_day=15.5,
            design=DeltaDesignProperty(time_samples=360, finalists=1),
        )
    )

    assert constellation.amount_of_orbit_plane == 3
    assert constellation.amount_of_satellite_per_orbit_plane == 4
    assert constellation.inclination == 53.0
    assert constellation.mean_revolution_per_day == 15.5
    assert constellation.phasing_factor in {0, 1, 2}
    assert len(constellation.generated_two_line_elements) == 12


def test_sizing_recovers_the_ballard_12_3_1_design():
    design = optimize_delta_constellation(
        total_satellites=12,
        min_elevation_deg=10.0,
        plane_counts=[3],
        phasing_factors=[1],
        inclination_min_deg=48.0,
        inclination_max_deg=54.0,
        inclination_step_deg=2.0,
        inclination_refine_steps_deg=(1.0, 0.1),
        time_samples=360,
    )

    assert design.walker_notation == "12/3/1"
    assert design.inclination_deg == pytest.approx(50.7, abs=0.2)
    assert design.max_coverage_range_deg == pytest.approx(47.9, abs=0.1)
    assert design.altitude_km == pytest.approx(5440.0, abs=30.0)
    assert design.orbital_period_hours == pytest.approx(3.55, abs=0.03)
    assert design.meets_elevation_requirement


def test_sizing_mode_can_change_geometry():
    constellation = WalkerDeltaConstellation(
        WalkerConstellationProperty(
            identifier="Sizing Mode",
            amount_of_orbit_plane=3,
            amount_of_satellite_per_orbit_plane=4,
            inclination=53.0,
            phase_difference_between_satellites=True,
            mean_revolution_per_day=15.5,
            design=DeltaDesignProperty(
                mode="sizing",
                plane_counts=[3],
                phasing_factors=[1],
                inclination_min_deg=48.0,
                inclination_max_deg=54.0,
                inclination_step_deg=2.0,
                time_samples=360,
            ),
        )
    )

    assert constellation.design_result is not None
    assert constellation.design_result.walker_notation == "12/3/1"
    assert constellation.amount_of_orbit_plane == 3
    assert constellation.amount_of_satellite_per_orbit_plane == 4
    assert constellation.inclination == pytest.approx(50.7, abs=0.2)
    assert constellation.mean_revolution_per_day == pytest.approx(6.75, abs=0.05)
    assert constellation.phasing_factor == 1
    assert len(constellation.generated_two_line_elements) == 12


def test_sizing_rejects_plane_counts_with_no_link_clearance():
    with pytest.raises(ValueError, match="No plane count"):
        optimize_delta_constellation(
            total_satellites=9,
            min_elevation_deg=10.0,
            plane_counts=[3],
            phasing_factors=[1],
            inclination_min_deg=50.0,
            inclination_max_deg=60.0,
            inclination_step_deg=10.0,
            time_samples=360,
            max_altitude_km=5880.0,
        )


def test_intra_plane_link_altitude_for_eight_satellites():
    required = intra_plane_link_altitude_km(8)
    assert required == pytest.approx(613.1, abs=1.0)
    assert intra_plane_link_altitude_km(22) < 200.0


def test_sizing_keeps_same_plane_links_clear_of_earth():
    design = optimize_delta_constellation(
        total_satellites=264,
        min_elevation_deg=10.0,
        plane_counts=[33],
        phasing_factors=[15],
        inclination_min_deg=70.0,
        inclination_max_deg=80.0,
        inclination_step_deg=5.0,
        time_samples=360,
        max_altitude_km=5880.0,
    )

    assert design.planes == 33
    assert design.satellites_per_plane == 8
    assert design.altitude_km >= intra_plane_link_altitude_km(8)

    radius = RE_KM + design.altitude_km
    closest_approach = radius * math.cos(math.pi / design.satellites_per_plane)
    assert closest_approach > RE_KM + ATMOSPHERE_EXCLUSION_ZONE_KM


def test_sizing_fixed_altitude_rejects_earth_crossing_same_plane_links():
    with pytest.raises(ValueError, match="too low for adjacent same-plane"):
        optimize_delta_constellation(
            total_satellites=264,
            min_elevation_deg=10.0,
            plane_counts=[33],
            phasing_factors=[15],
            inclination_min_deg=70.0,
            inclination_max_deg=80.0,
            inclination_step_deg=5.0,
            time_samples=90,
            altitude_mode="fixed",
            fixed_altitude_km=470.0,
        )


def test_dense_grid_validation_agrees_with_delaunay():
    design = optimize_delta_phasing(
        planes=3,
        satellites_per_plane=4,
        inclination_deg=50.73,
        mean_revolution_per_day=6.7553,
        phasing_factors=[1],
        time_samples=360,
    )

    validation = validate_design(design, time_samples=180, grid_points=100000)

    assert validation["difference_deg"] == pytest.approx(0.0, abs=0.1)


def test_coverage_radius_handles_gaps_larger_than_a_hemisphere():
    # Eight satellites clustered on a small cap leave a very large empty region.
    rng = np.random.default_rng(7)
    vectors = rng.normal(size=(8, 3))
    vectors[:, 2] = np.abs(vectors[:, 2]) + 1.0
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)

    hull_radius = coverage_radius_deg(vectors, multiplicity=1)
    grid_radius = grid_coverage_radius_deg(vectors, multiplicity=1, grid_points=100000)

    assert hull_radius > 90.0
    assert hull_radius == pytest.approx(grid_radius, abs=0.2)


def test_higher_multiplicity_agrees_with_dense_grid():
    points = satellite_unit_vectors(
        planes=4,
        satellites_per_plane=3,
        phasing_factor=1,
        inclination_deg=53.0,
    )

    exact = coverage_radius_deg(points, multiplicity=3)
    grid = grid_coverage_radius_deg(points, multiplicity=3, grid_points=100000)

    assert exact == pytest.approx(grid, abs=0.2)


def test_walker_phasing_wrap_shift_avoids_earth_crossing():
    # IRIS2: 12 planes x 22 satellites, F=5. The last->first plane seam needs
    # a phase-aware index shift; otherwise one adjacent-plane link spans ~61 deg
    # and its chord passes through the Earth.
    assert _walker_delta_wrap_shift(12, 22, 5) == 5
    assert _walker_delta_wrap_shift(12, 22, None) == 0

    grid = generate_walker_delta_constellation_grid(
        number_orbits=12,
        number_satellites_per_orbit=22,
        isl_shift=0,
        phasing_factor=5,
    )
    max_adjacent_angle = 0.0
    for phase in range(0, 360, 10):
        positions = satellite_unit_vectors_many(
            planes=12,
            satellites_per_plane=22,
            phasing_factor=5,
            inclination_deg=53.0,
            time_phases_deg=np.array([phase]),
        )[0]
        for a, b, direction in grid:
            if direction != InterSatelliteLinkDirection.ADJACENT:
                continue
            angle = math.degrees(
                math.acos(float(np.clip(positions[a] @ positions[b], -1.0, 1.0)))
            )
            max_adjacent_angle = max(max_adjacent_angle, angle)

    # At 742 km the chord intersects the Earth above ~52.8 deg.
    assert max_adjacent_angle < 52.8


def test_walker_phasing_is_written_to_the_tles():
    tles = generate_two_line_elements(
        constellation_name="BALLARD",
        number_of_orbits=3,
        number_of_satellites_per_plane=4,
        phase_difference=False,
        inclination_degree=50.73,
        mean_motion_revolution_per_day=6.7553,
        phasing_factor=1,
    )

    mean_anomalies = [round(float(tle.line2[43:51]), 3) for tle in tles]
    raans = [round(float(tle.line2[17:25]), 3) for tle in tles]

    assert mean_anomalies == [
        0.0,
        90.0,
        180.0,
        270.0,
        30.0,
        120.0,
        210.0,
        300.0,
        60.0,
        150.0,
        240.0,
        330.0,
    ]
    assert raans == [0.0] * 4 + [120.0] * 4 + [240.0] * 4


def test_legacy_walker_phasing_is_unchanged_when_no_factor_is_given():
    tles = generate_two_line_elements(
        constellation_name="LEGACY",
        number_of_orbits=3,
        number_of_satellites_per_plane=4,
        phase_difference=True,
        inclination_degree=53.0,
        mean_motion_revolution_per_day=15.5,
    )

    mean_anomalies = [round(float(tle.line2[43:51]), 3) for tle in tles]

    # Historical odd-plane shift: 360 / (2 * Q) = 45 deg on the middle plane.
    assert mean_anomalies == [
        0.0,
        90.0,
        180.0,
        270.0,
        45.0,
        135.0,
        225.0,
        315.0,
        0.0,
        90.0,
        180.0,
        270.0,
    ]


def test_precomputed_design_uses_phasing_factor_without_optimizing():
    constellation = WalkerDeltaConstellation(
        WalkerConstellationProperty(
            identifier="Precomputed",
            amount_of_orbit_plane=3,
            amount_of_satellite_per_orbit_plane=4,
            inclination=50.73,
            phase_difference_between_satellites=True,
            mean_revolution_per_day=6.7553,
            phasing_factor=1,
        )
    )

    assert constellation.design_result is None
    mean_anomalies = [
        round(float(tle.line2[43:51]), 3)
        for tle in constellation.generated_two_line_elements
    ]
    assert mean_anomalies[:8] == [
        0.0,
        90.0,
        180.0,
        270.0,
        30.0,
        120.0,
        210.0,
        300.0,
    ]


def test_star_constellation_rejects_a_design_block():
    with pytest.raises(ValueError, match="only supported for Walker Delta"):
        WalkerStarConstellation(
            WalkerConstellationProperty(
                identifier="Star with design",
                amount_of_orbit_plane=3,
                amount_of_satellite_per_orbit_plane=4,
                inclination=86.4,
                phase_difference_between_satellites=True,
                mean_revolution_per_day=13.0,
                design=DeltaDesignProperty(),
            )
        )


def test_projection_is_on_the_unit_sphere():
    points = satellite_unit_vectors(
        planes=3,
        satellites_per_plane=4,
        phasing_factor=1,
        inclination_deg=50.73,
    )
    assert np.allclose(np.linalg.norm(points, axis=1), 1.0)
    assert points.shape == (12, 3)


def test_fibonacci_grid_is_on_the_unit_sphere():
    points = fibonacci_sphere(1000)
    assert np.allclose(np.linalg.norm(points, axis=1), 1.0)
    assert math.isclose(float(np.mean(points[:, 2])), 0.0, abs_tol=0.02)
