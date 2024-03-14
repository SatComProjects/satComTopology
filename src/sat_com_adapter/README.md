# sat_com_adapter Package

This package is used to implement features that transform topology into configuration files. In a layered architecture it is the presentation layer.

The implemented output are:
- NetworkX
  - Python graph
  - json export

Todo:
- Implement [Gonetem](https://github.com/mroy31/gonetem) support.
- Configure [Hypatia](https://github.com/snkas/hypatia) support.
- Configure output file in the YAML configuration file .

## Example

### NetworkX Adapter

#### With file export

```python
from sat_com_adapter.adapters import NetworkXAdapter
from sat_com_application.simulation_manager import SimulationManager
from sat_com_model.models import Simulation

my_example_simulation = Simulation()
example_simulation_manager = SimulationManager(my_example_simulation)

network_x_adapter = NetworkXAdapter(example_simulation_manager, "my_output_folder")

network_x_adapter.adapt()
```
Result:
```json
{
  "directed": false,
  "multigraph": false,
  "graph": {},
  "nodes": [
    {
      "type": "Satellite",
      "id": 0
    },
    {
      "type": "Satellite",
      "id": 1
    }
  ],
  "links": [
    {
      "type": "InterSatelliteLink",
      "direction": "ORBITAL",
      "source": 1,
      "target": 2
    },
    {
      "type": "InterSatelliteLink",
      "direction": "ADJACENT",
      "source": 1,
      "target": 24
    }
  ]
}
```
We have to improve the adapt() method, because now it returns a default networkx graph without any addition data.

### Without file export
```python
from sat_com_adapter.adapters import NetworkXAdapter
from sat_com_application.simulation_manager import SimulationManager
from sat_com_model.models import Simulation

my_example_simulation = Simulation()
example_simulation_manager = SimulationManager(my_example_simulation)

network_x_adapter = NetworkXAdapter(example_simulation_manager, "my_output_folder")

my_nx_graph = network_x_adapter.get_networkx_graph(export_link_length=True, export_object_position= True)

```
You can still use json_graph api from networkX to export a file later.

### Cesium Adapter
This adapter allow you to export your simulation as a Html File with Cesium. This adapter works with CesiumRenderer API.

#### With the default method
```python
from sat_com_application.simulation_manager import SimulationManager
from sat_com_model.models import Simulation
from sat_com_adapter.cesium_adapter.cesium_adapter import CesiumAdapter

my_example_simulation = Simulation()

simulation_manager = SimulationManager(my_example_simulation)

cesium_adapter = CesiumAdapter(simulation_manager, "my_out_put_folder")

renderer = cesium_adapter.create_cesium_renderer("MY_SUPER_SECRET_CESIUM_TOKEN_OR_NOTHING")

renderer.add_satellites()

cesium_adapter.adapt()
```

#### With the pre-build
```python
from sat_com_application.simulation_manager import SimulationManager
from sat_com_model.models import Simulation
from sat_com_adapter.cesium_adapter.cesium_adapter import CesiumAdapter

my_example_simulation = Simulation()

simulation_manager = SimulationManager(my_example_simulation)

cesium_adapter = CesiumAdapter(simulation_manager, "my_out_put_folder")

renderer = cesium_adapter.build_renderer_simulation_with_links("MY_SUPER_SECRET_CESIUM_TOKEN_OR_NOTHING")

cesium_adapter.adapt()
```
### With custom render
```python
from sat_com_application.simulation_manager import SimulationManager
from sat_com_model.models import Simulation
from sat_com_adapter.cesium_adapter.cesium_renderer import CesiumRenderer
from sat_com_adapter.cesium_adapter.cesium_adapter import CesiumAdapter

my_example_simulation = Simulation()

simulation_manager = SimulationManager(my_example_simulation)

cesium_adapter = CesiumAdapter(simulation_manager, "my_out_put_folder")

custom_renderer = CesiumRenderer(simulation_manager, "MY_SUPER_SECRET_CESIUM_TOKEN_OR_NOTHING")

custom_renderer.add_satellites()

custom_renderer.add_ground_stations()

cesium_adapter.set_custom_renderer(custom_renderer)

cesium_adapter.adapt()
```

![Satellite topology generated with CesiumJS](./cesium_adapter/example/topology-render-example.png "Example of Satellite Topology")