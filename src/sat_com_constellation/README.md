# sat_com_constellation Package

## Description
This package is the python library that generates constellations sets of two elements

## Earth constants
The TLEs are generated with the SGP4 `WGS72` gravity model. Every Earth constant
used to prepare them (gravitational parameter `MU_KM3_S2`, radius `RE_KM`, `J2`,
`J4`) comes from `sat_com_model.constants`, where they are defined once with the
WGS72 values of SGP4. No Earth constant is hard-coded in this package.

## How To Use ?
Do you need to design a constellation ? A Walker Constellation ?
Walker Constellation: satellite constellation composed of one or multiple orbits with multiple satellites.

### Satellite Distribution Model
The library relies on the `generate_two_line_elements` helper to place satellites inside each orbital plane. The implementation follows the Walker geometry described by D.C. Beste in *“Design of Satellite
Constellations for Optimal Continuous Coverage”*.

- **Polar tailoring**: for high-inclination constellations (≈80°–100°) the algorithm refines the RAAN spacing using Beste’s equal-coverage construction: it computes the half cone angle from the minimum elevation constraint, derives the inter-plane separation `phi`, and distributes planes accordingly to soften coverage overlap near the poles.

These rules ensure the generated Two-Line Elements reflect Walker constellations that respect the phase relationships and coverage geometry documented by Beste.

### Two Walker Constellations Exists
- Walker Star Constellation: constellation where orbit planes are distributed around 180°
- Walker Delta Constellation: constellation where orbits planes are distributed around 360°

 ```python
from sat_com_constellation.models import WalkerDeltaConstellation, WalkerConstellationProperty

constellation_properties = WalkerConstellationProperty(
    inclination=55,
    identifier="StarLink",
    amount_of_satellite_per_orbit_plane=40,
    amount_of_orbit_plane=20,
    phase_difference_between_satellites=True,
    mean_revolution_per_day=15.5,
)

walker_delta_constellation = WalkerDeltaConstellation(
    constellation_properties
)

for two_line_set in walker_delta_constellation.generated_two_line_elements:
    print("Satellite Name: ", two_line_set.satellite_name)
    print("Line 1:", two_line_set.line1)
    print("Line 2", two_line_set.line2)
 ```

```python
from sat_com_constellation.models import WalkerStarConstellation, WalkerConstellationProperty

constellation_properties = WalkerConstellationProperty(
    inclination=55,
    identifier="StarLink",
    amount_of_satellite_per_orbit_plane=40,
    amount_of_orbit_plane=20,
    phase_difference_between_satellites=True,
    mean_revolution_per_day=15.5,
)

walker_star_constellation = WalkerStarConstellation(
    constellation_properties
)

for two_line_set in walker_star_constellation.generated_two_line_elements:
    print("Satellite Name: ", two_line_set.satellite_name)
    print("Line 1:", two_line_set.line1)
    print("Line 2", two_line_set.line2)
```

### Numerical Delta design (Ballard rosettes)

The Ballard block has two modes:

- `mode: "layout"` (default) distributes the configured constellation. The
  plane count, satellites per plane, inclination and mean motion are fixed
  inputs; only the inter-plane phasing `F` is selected. Input values are never
  changed.
- `mode: "sizing"` co-designs the constellation. It may change the `T/P/Q`
  factorization, inclination and altitude. The default fast search returns a
  264-satellite design in about 3 seconds.

Given `T = P x Q` satellites, the distribution is:

- RAAN of plane `k`: `360 k / P`
- argument of latitude of satellite `j` in plane `k`:
  `360 j / Q + 360 F k / T`

`F` is selected by evaluating that exact geometry over one orbital period and
minimising the worst-case coverage gap (largest empty spherical circumcircle
of the subsatellite points). For the published 12-satellite rosette, with the
inputs fixed at `3 x 4`, `50.73 deg` and `6.7553 rev/day`, the block selects
`F=1` and obtains `Rmax = 47.90 deg`.

```yaml
walker_shells:
  - type: "delta"
    constellation_property:
      identifier: "Ballard Delta Layout"
      amount_of_orbit_plane: 3
      amount_of_satellite_per_orbit_plane: 4
      inclination: 50.73
      phase_difference_between_satellites: false
      mean_revolution_per_day: 6.7553
      design:
        method: "ballard"
        min_elevation_deg: 10.0
        coverage_multiplicity: 1
        time_samples: 360
        search_effort: "fast"
```

The shell built by `BaseConfigurationManager` keeps the same `P`, `Q`,
inclination and mean motion. Only `phasing_factor` is added to the generated
TLEs. `design_result.meets_elevation_requirement` reports whether the fixed
geometry reaches the requested elevation; the distribution does **not** change
the altitude to force it.

To pin a specific phasing instead of selecting one, set
`phasing_factors: [F]` in the design block. A precomputed distribution can be
used without a design block:

```yaml
constellation_property:
  identifier: "Ballard Delta"
  amount_of_orbit_plane: 3
  amount_of_satellite_per_orbit_plane: 4
  inclination: 50.73
  phase_difference_between_satellites: false
  mean_revolution_per_day: 6.755
  phasing_factor: 1
```

`phasing_factor` alone requests the classical Walker Delta phasing
`360 F k / T`; the legacy odd-plane and polar heuristics are disabled.

#### `mode: "sizing"` — optimize the geometry

Sizing differs from layout: it searches plane counts, phasing, inclination and
(for `altitude_mode: "solve"`) the altitude required to meet the minimum
elevation. It is useful when the fleet size is fixed but the shell geometry is
not.

```yaml
design:
  method: "ballard"
  mode: "sizing"
  min_elevation_deg: 10.0
  coverage_multiplicity: 1
  altitude_mode: "solve"            # or "fixed" with altitude_km
  max_altitude_km: 5880.0
  inclination_min_deg: 20.0
  inclination_max_deg: 80.0
  inclination_step_deg: 5.0
  time_samples: 360
  search_effort: "fast"
```

In sizing mode the constellation object replaces `amount_of_orbit_plane`,
`amount_of_satellite_per_orbit_plane`, `inclination`,
`phasing_factor` and `mean_revolution_per_day` with the result before the TLEs
are generated. `search_effort: "thorough"` keeps the exhaustive search.

Sizing also enforces same-plane ISL clearance. Adjacent satellites in a plane
are separated by `360 / Q`; if the coverage-driven altitude is too low for that
chord to clear the atmosphere, the altitude is raised to the clearance value
(fixed-altitude mode raises an error instead). For IRIS2 `264` satellites, the
`33 x 8` geometry at `76.7°` needs about **613 km** instead of the 469 km pure
coverage altitude, so its `45°` same-plane links clear the Earth. Plane counts
whose required clearance exceeds `max_altitude_km` are skipped.

#### Performance

Layout mode ranks `F in [0, P)` on a cached Fibonacci grid and re-evaluates a
few finalists with the exact Delaunay geometry. Sizing mode ranks the
shortlisted `P x F x inclination` grid the same way, then re-evaluates a narrow
inclination scan and a few finalists exactly. `search_effort: "fast"` is the
default for both; `search_effort: "thorough"` evaluates the full candidate set.
A 264-satellite sizing design takes about 3 seconds.

> **Near-Earth propagation.** Layout mode preserves the input altitude; sizing
> mode can change it. The `pyorbital` movement model cannot propagate deep-space
> TLEs (period >= 225 min). In sizing mode, set `max_altitude_km: 5880` to turn
> that into an explicit design error.

### Sun Synchronous Constellation (Dawn Dusk SSO)
## Sun-Synchronous Constellation (Dawn-Dusk SSO)

A **Dawn-Dusk Sun-Synchronous Orbit (SSO) Constellation** is designed to maintain a near-constant local solar time for each satellite’s orbit, which is ideal for:

- Earth observation
- Remote sensing
- Imaging satellites
- **Space datacenter simulations** — e.g., constellations optimized for continuous solar power and low-latency coverage

### Satellite Distribution Model

The library relies on `generate_sso_dawn_dusk` to compute TLEs for the given number of satellites, orbit altitude, and epoch. It automatically calculates the correct RAAN spacing to achieve dawn-dusk coverage for the entire constellation, which is useful for simulating satellites that need **constant sunlight exposure**, such as space-based data centers.

### Example — Dawn-Dusk SSO

```python
from datetime import datetime
from sat_com_constellation.models import (
    DawnDuskSunSynchronousOrbitConstellation,
    DawnDuskSunSynchronousOrbitConstellationProperty,
)

sso_properties = DawnDuskSunSynchronousOrbitConstellationProperty(
    identifier="SpaceDatacenter",
    altitude_in_km=600,
    amount_of_satellite=12,
    epoch=datetime.utcnow()
)

dawn_dusk_constellation = DawnDuskSunSynchronousOrbitConstellation(
    sso_properties
)

for two_line_set in dawn_dusk_constellation.generated_two_line_elements:
    print("Satellite Name:", two_line_set.satellite_name)
    print("Line 1:", two_line_set.line1)
    print("Line 2:", two_line_set.line2)
```
### Updating Epoch

To update the constellation epoch and regenerate TLEs:

```python
from datetime import datetime

new_epoch = datetime.utcnow()
dawn_dusk_constellation.update_constellation(epoch=new_epoch)
```
This will adjust the satellite positions to reflect the new epoch while keeping the dawn-dusk, space datacenter optimized configuration.