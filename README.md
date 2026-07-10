# Welcome to the SatComTopology project 🛰️

**SatComTopology** is a project whose goal is to design satellite communication topologies.
Its objective is to generate a topology in order to **prepare a simulation**. Overall, it is a set of Python modules
that provide tools to build your future constellation environment.
The simulation model can be exported in different formats:
- **networkx**: a popular network library that allows you to compute routing and run standard graph algorithms.
- **Cesium**: a visualization tool that lets you watch your constellation in 3D 🌍.

This project is the laboratory 🔬 where you can **design** your topologies.

<!-- TOC -->
* [Welcome to the SatComTopology project 🛰️](#welcome-to-the-satcomtopology-project-)
  * [Features 📢](#features-)
    * [Packages 📦](#packages-)
  * [Installation 📃](#installation-)
    * [Install Main Version from GitLab](#install-main-version-from-gitlab)
    * [Install Main Version from GitHub](#install-main-version-from-github)
  * [Example 🖊️](#example-)
    * [Load a configuration](#load-a-configuration)
    * [Manage a Simulation](#manage-a-simulation)
      * [Export a Simulation](#export-a-simulation)
      * [Quick start: straight to NetworkX](#quick-start-straight-to-networkx)
  * [Tutorials 🎓](#tutorials-)
  * [Contributing](#contributing)
  * [License ⚖️](#license-)
<!-- TOC -->

## Features 📢
### Packages 📦
- `sat_com_model`: [Topology Model](src/sat_com_model/README.md)
- `sat_com_builder`: [Topology Simulation Builder](src/sat_com_builder/README.md)
- `sat_com_adapter`: [Topology Adapters](src/sat_com_adapter/README.md)
- `sat_com_trajectopy`: [Topology Physics Manager](src/sat_com_trajectopy/README.md)
- `sat_com_application`: [Topology Application](src/sat_com_application/README.md)
- `sat_com_traffic`: [Topology Traffic](src/sat_com_traffic/README.md) (Beta version)
- `sat_com_connectivity`: [Topology Connectivity](src/sat_com_connectivity/README.md)

## Installation 📃
Uninstall any existing version first:
```sh
pip uninstall sat_com_topology -y
```

### Install Main Version from GitLab
```sh
pip install git+https://gitlab.isae-supaero.fr/eqospace/sat-com-topology.git@main#egg=sat_com_topology
```

### Install Main Version from GitHub
```shell
pip install git+https://github.com/elbarbi/satComTopology.git@main#egg=sat_com_topology
```

## Example 🖊️
### Load a configuration
An example JSON configuration is available [here](src/sat_com_builder/examples/multi_shell_configuration_example.json).

```python
from sat_com_builder.models import SimulationProperty
from sat_com_builder.configuration_manager import BaseConfigurationManager

plain_config_walker = {
  "simulation_name": "Single Shell Simulation",
  "start_date": "2024-11-18 00:00:00.000000",
  "end_date": "2024-11-25 00:00:00.000000",
  "movement_model": "pyorbital",
  "distance_model": "sklearn",
  "ground_objects_properties": [
    {
      "identifier": "OneWeb Ground Station",
      "data_file": "../configurations/ground_stations.txt",
      "type": "ground_station",
      "connectivity_properties": {
        "elevation_above_horizon": 20
      }
    }
  ],
  "walker_shells": [
    {
      "type": "delta",
      "constellation_property": {
        "identifier": "Walker",
        "amount_of_orbit_plane": 40,
        "amount_of_satellite_per_orbit_plane": 40,
        "inclination": 70.0,
        "phase_difference_between_satellites": True,
        "mean_revolution_per_day": 15.5
      },
      "orbital_connectivity_property": {
        "adjacent_inter_satellite_shifting": 0,
        "maximum_inter_satellite_count": 4,
        "maximum_inter_satellite_range_distance": 1000,
        "maximum_ground_station_range": 5000,
        "maximum_user_terminal_range": 1000,
        "maximum_connected_ground_object": 10000,
        "maximum_connected_user_terminal": 1000,
        "maximum_connected_ground_station": 10
      },
      "ground_object_white_list": []
    }
  ]
}

simulation_properties = SimulationProperty(**plain_config_walker)

simulation_manager = BaseConfigurationManager(simulation_property=simulation_properties)
simulation_manager = simulation_manager.load_simulation()
```

### Manage a Simulation
The following example shows how to manually create a link between a satellite and a ground station.

```python
ground_station = simulation_manager.get_ground_station_by_object_id(0)

satellite = simulation_manager.get_satellite_by_object_id(0)

created_link = simulation_manager.create_and_add_ground_station_link_connection(
    satellite,
    ground_station
)

print(f"A new {created_link.type} has been created")
print(
    f"Source: {created_link.source.type} n° {created_link.source.object_id}, "
    f"topology id: {created_link.source.topology_uniq_id}"
)
print(
    f"Destination: {created_link.destination.type} n° {created_link.destination.object_id}, "
    f"topology id: {created_link.destination.topology_uniq_id}"
)
```

#### Export a Simulation
In most cases, a `satComTopology` user will want to load a simulation and export it to a new format.

```python
from sat_com_adapter.adapters import NetworkXAdapter

networkx_adapter = NetworkXAdapter(simulation_manager)

my_graph = networkx_adapter.create_full_networkx_graph()

networkx_adapter.adapt("OUTPUT_PATH")
```

#### Quick start: straight to NetworkX
Here's a copy-paste-friendly example showing how to generate your topology and export it directly to NetworkX.

```python
from sat_com_builder.configuration_manager import YamlConfigurationManager
from sat_com_adapter.adapters import NetworkXAdapter

yaml_configuration_manager = YamlConfigurationManager("/CONFIGURATION_PATH/old_configuration_example.yaml")

simulation_manager = yaml_configuration_manager.load_simulation()

networkx_adapter = NetworkXAdapter(simulation_manager)

my_graph = networkx_adapter.create_full_networkx_graph()

networkx_adapter.adapt("OUTPUT_PATH")
```

## Tutorials 🎓
Tutorials are available as Jupyter notebooks:
- [Create my first simulation](https://github.com/elbarbi/sat_com_topology_tutorials/blob/main/src/create_my_first_simulation.ipynb)
- [Learn to use satComTopology in depth](https://github.com/elbarbi/satComTopologyTutorials/blob/main/src/deeply_understand_sat_com_topology.ipynb)

These tutorials aren't on GitLab yet. To request access, contact:
louis.barbier [at] isae-supaero.fr

## Contributing
The contributing guide is available [here](https://github.com/elbarbi/satComTopology/blob/develop/CONTRIBUTING.md).

## License ⚖️
This project is licensed under the GNU General Public License v3.0.
