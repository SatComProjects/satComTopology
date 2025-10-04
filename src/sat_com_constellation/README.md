# sat_com_constellation Package

## Description
This package is the python library that generates constellations sets of two elements

## How To Use ?
Do you need to design a constellation ? A Walker Constellation ?
Walker Constellation: satellite constellation composed of one or multiple orbits with multiple satellites.

### Satellite Distribution Model
The library relies on the `generate_two_line_elements` helper to place satellites inside each orbital plane. The implementation follows the Walker geometry described by D.C. Beste in *“Design of Satellite
Constellations for Optimal Continuous Coverage”*.

- **Polar tailoring**: for high-inclination constellations (≈80°–100°) the algorithm refines the RAAN spacing using Beste’s equal-coverage construction: it computes the half cone angle from the minimum elevation constraint, derives the inter-plane separation `phi`, and distributes planes accordingly to soften coverage overlap near the poles.

These rules ensure the generated Two-Line Elements reflect Walker constellations that respect the phase relationships and coverage geometry documented by Beste.

### Two Constellations Exists
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
