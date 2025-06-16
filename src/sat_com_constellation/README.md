# sat_com_constellation Package

## Description
This package is the python library that generates constellations sets of two elements

## How To Use ?
DO you need to design a constellation ? A Walker Constellation ?
Walker Constellation: satellite constellation composed of one or multiple orbits with multiple satellites.

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

