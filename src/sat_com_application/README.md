# sat_com_application Package
This package provide the main API that will be used to manage constellation.
Maybe the name should be changed to API.

## Example
How to instantiate your simulation manager. 

```python
from sat_com_application.simulation_manager import SimulationManager
from sat_com_model.models import Simulation

your_simulation = Simulation()

simulation_manager = SimulationManager(your_simulation)

```
How to use your simulation manager.

```python

simulation_manager.get_satellites()

simulation_manager.disconnect_every_ground_stations()

my_topology_object_1 = simulation_manager.get_topology_object_from_uniq_id(1)

my_topology_object_2 = simulation_manager.get_topology_object_from_uniq_id(2)

my_link_connecting_1_2 = simulation_manager.get_link_connecting_topology_objects(
    my_topology_object_1,
    my_topology_object_2
)


```