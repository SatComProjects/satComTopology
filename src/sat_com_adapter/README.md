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
#### NetworkX Builder
NetworkX builder is the object used to create networkX graph, it will be used in the NetworkXAdapter. NetworkX Builder
will define what we want to export in the adapter. 
The adapter is the layer that export the Builder into a file.

##### Content
By default the graph only holds light, useful data:

| Element | Data |
|---|---|
| graph | `current_simulation_date`, `simulation_configuration` |
| every node | `type`, `object_id`, `topology_uniq_id` |
| satellite | `name`, `shell_id`, `orbital_phase` |
| ground station, user terminal, point of presence | `label`, `ground_domain` |
| every edge | `type`, `source_id`, `destination_id`, `distance_km` |
| inter-satellite link | `direction` (`ORBITAL`, `ADJACENT`, `INTER_SHELL`) |

- `distance_km` is the straight-line distance of the link computed by the
  simulation. A link without one (ground-to-ground links, static ground station
  mode) gets the straight-line distance between both positions.
- `source_id` / `destination_id` keep the link orientation: the graph is
  undirected, and the `source` / `target` keys of a JSON export follow the
  adjacency order, not the link.

##### Available options
All `False` by default:
- `export_positions`: node `position` (longitude, latitude, altitude in meters)
- `export_grid_coordinates`: Walker satellites `orbit_plane_id` / `satellite_number`
- `enable_export_flows_data`: amount of flows crossing each link in both directions
- `export_model_data`: full model of every node and edge, under `model_data` (heavy)

`export_link_length` is deprecated: the distance is always exported. It is still
accepted and emits a `FutureWarning`.

##### Code
```py
from sat_com_adapter.networkx_builder.networkx_builder import NetworkxBuilder
from sat_com_adapter.adapters import NetworkXAdapter

network_x_builder = NetworkxBuilder(simulation_manager,
                                    export_positions=True,
                                    enable_export_flows_data=True,
                                    )
network_x_builder.add_topology_objects().add_links()
my_networkx_graph = network_x_builder.build()

networkx_adapter = NetworkXAdapter(simulation_manager)
networkx_adapter.set_networkx_builder(network_x_builder)
networkx_adapter.adapt("my_graph.json")  # Export the graph (not mandatory)
```

#### Graph Structure
Default export of a 10 × 10 Walker shell with ground stations (one node and one
edge of each kind):
```json
{
  "directed": false,
  "multigraph": false,
  "graph": {
    "current_simulation_date": "2026-01-01 00:00:00.000",
    "simulation_configuration": {"...": "..."}
  },
  "nodes": [
    {
      "name": "Walker Test 0",
      "orbital_phase": "descending",
      "shell_id": "Walker Test",
      "type": "Satellite",
      "object_id": 0,
      "topology_uniq_id": 0,
      "id": 0
    },
    {
      "label": "Tokyo",
      "ground_domain": "Ground Stations",
      "type": "GroundStation",
      "object_id": 0,
      "topology_uniq_id": 100,
      "id": 100
    }
  ],
  "edges": [
    {
      "direction": "ORBITAL",
      "type": "InterSatelliteLink",
      "source_id": 0,
      "destination_id": 1,
      "distance_km": 4720.702951429366,
      "source": 0,
      "target": 1
    },
    {
      "type": "GroundStationLink",
      "source_id": 0,
      "destination_id": 172,
      "distance_km": 2239.7174047501844,
      "source": 0,
      "target": 172
    }
  ]
}
```
With `enable_export_flows_data`, each edge also has:
```json
"used_capacity_between_previous_and_last_hop": {"0": 150, "1": 200},
"total_used_capacity_crossing_link": 350,
"unidirectional_link_maximum_capacity": 1000
```
(`"0": 150` is the capacity used from node 0 to node 1.)

#### With file export
`adapt()` builds the default graph if none was built before, and writes it as a
node-link JSON (edges under `"edges"`) on every supported networkx version.
```python
from sat_com_adapter.adapters import NetworkXAdapter

network_x_adapter = NetworkXAdapter(simulation_manager)
network_x_adapter.adapt("my_graph.json")
```

### Without file export

```python
from sat_com_adapter.adapters import NetworkXAdapter

network_x_adapter = NetworkXAdapter(simulation_manager)

my_nx_graph = network_x_adapter.create_full_networkx_graph(
    export_object_position=True,
    export_model_data=False,  # True: full model of every node and edge
)
```
You can still use json_graph api from networkX to export a file later.

### Cesium Adapter
This adapter allow you to export your simulation as a Html File with Cesium. This adapter works with CesiumRenderer API.

#### With the default method

```python
from sat_com_application.simulation_manager import SimulationManager
from sat_com_model.models import Simulation
from sat_com_adapter.adapters import CesiumAdapter

my_example_simulation = Simulation()

simulation_manager = SimulationManager(my_example_simulation)

cesium_adapter = CesiumAdapter(simulation_manager)

renderer = cesium_adapter.create_cesium_renderer("MY_SUPER_SECRET_CESIUM_TOKEN_OR_NOTHING")

renderer.add_satellites()

cesium_adapter.adapt("my_folder")
```

#### With the pre-build

```python
from sat_com_application.simulation_manager import SimulationManager
from sat_com_model.models import Simulation
from sat_com_adapter.adapters import CesiumAdapter

my_example_simulation = Simulation()

simulation_manager = SimulationManager(my_example_simulation)

cesium_adapter = CesiumAdapter(simulation_manager)

renderer = cesium_adapter.build_renderer_simulation_with_links("MY_SUPER_SECRET_CESIUM_TOKEN_OR_NOTHING")

cesium_adapter.adapt("my_out_put_folder")
```
### With custom render

Customize your renderer with the CesiumRenderer API, then set it in the adapter before calling adapt() method.
You can access to CesiumRenderer docs here: [CesiumRenderer API](cesium_renderer/README.md).

```python
from sat_com_application.simulation_manager import SimulationManager
from sat_com_model.models import Simulation
from sat_com_adapter.cesium_renderer.renderers import CesiumRenderer
from sat_com_adapter.adapters import CesiumAdapter
from sat_com_adapter.cesium_renderer.models import CesiumProperty

my_example_simulation = Simulation()

simulation_manager = SimulationManager(simulation=my_example_simulation)

cesium_adapter = CesiumAdapter(
  simulation_manager=simulation_manager
)

cesium_property = CesiumProperty()

cesium_property.cesium_token = "MY_SUPER_SECRET_CESIUM_TOKEN_OR_NOTHING"

custom_renderer = CesiumRenderer(
  simulation_manager=simulation_manager, 
  cesium_renderer_property=cesium_property
)

custom_renderer.add_satellites()

custom_renderer.add_ground_stations()

cesium_adapter.set_custom_renderer(cesium_renderer=custom_renderer)

cesium_adapter.adapt("my_file_name.html")

```

![Satellite topology generated with CesiumJS](cesium_renderer/example/topology-render-example.png "Example of Satellite Topology")