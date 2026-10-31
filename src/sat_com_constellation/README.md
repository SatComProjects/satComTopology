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