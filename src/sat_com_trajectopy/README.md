from sat_com_application.time_managers import TimeManagerfrom sat_com_application.time_managers import TimeManager

# sat_com_trajectopy Package
### Description
This package implement physics management. It implements movements models and provide distance calculation model.
Implemented movement models:
- PyOrbital: a library that calculate satellite position by date

Implemented Distance Model:
- GeopyDistanceModel: a library that compute distances.

Todo:
- Implement static movement model
- PyOrbitalModel should be renamed PyOrbitalMovementModel

### Example
This is an example for a lonely usage, but consider that it should be passed to a OrbitalObject
in sat_com_topology_model

```python
from sat_com_trajectopy.orbital_models import PyOrbitalModel
from sat_com_application.time_managers import TimeManager

your_two_line_element_dict = {"line1": "", "line2": ""}

time_manager = TimeManager()

orbital_model = PyOrbitalModel(your_two_line_element_dict, time_manager)

my_position = orbital_model.get_longitude_latitude_altitude()
```
With sat_com_model:
get_coordinates() method will call the MovementModel.
```python
from sat_com_trajectopy.orbital_models import PyOrbitalModel
from sat_com_model.models import Satellite
from sat_com_application.time_managers import TimeManager

your_two_line_element_dict = {"line1": "", "line2": ""}

time_manager = TimeManager()

orbital_model = PyOrbitalModel(your_two_line_element_dict, time_manager=time_manager)

example_satellite = Satellite(satellite_name="satellite_1")
example_satellite.set_movement_model(orbital_model)

actual_satellite_position = example_satellite.get_coordinates()
```