# Welcome to the SatComTopology project 🛰️

The **satComTopology** is a project that have for goal to design a satellite communication topology.
The objective is to generate a topology in order to **prepare a simulation**. The overall is a set of python module which 
provides tools to build your future constellation environment. 
The Simulation model can be exported in different format:
- networkx: A famous network library that will allow you to compute routing, and execute basic algorithms.
- Cesium : A visualization software that allow you to watch your constellation in 3D 🌍.

This project si the laboratory 🔬 where you can **design** your topologies.

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
      * [I just want my constellation in the good format](#i-just-want-my-constellation-in-the-good-format)
  * [Tutorials 🎓](#tutorials-)
  * [Contributing](#contributing)
  * [License ⚖️](#license-)
<!-- TOC -->

## Features 📢
### Packages 📦
- sat_com_model: [Topology Model](src/sat_com_model/README.md)
- sat_com_builder: [Topology Simulation builder](src/sat_com_builder/README.md)
- sat_com_adapter: [Topology Adapters](src/sat_com_adapter/README.md)
- sat_com_trajectopy: [Topology Physic Manager](src/sat_com_trajectopy/README.md)
- sat_com_application: [Topology Application](src/sat_com_application/README.md)
- sat_com_topology_traffic: [Topology Traffic](src/sat_com_traffic/README.md) (Bêta version)
- sat_com_connectivity: [Topology Connectivity](src/sat_com_connectivity/README.md)

## Installation 📃
Uninstall if already installed:
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
An example of a JSON configuration is located [here](src/sat_com_builder/examples/multi_shell_configuration_example.json).
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
The following code is an example of how to manually create a link between a satellite and a ground station.

```python
ground_station = simulation_manager.get_ground_station_by_object_id(0)

satellite = simulation_manager.get_satellite_by_object_id(0)

created_link = simulation_manager.create_and_add_ground_station_link_connection(
  satellite,
  ground_station
)

print(f"A new {created_link.type} has been created")
print(
  f"Source: {created_link.source.type} n° {created_link.source.object_id}, topology id: {created_link.source.topology_uniq_id}"
)
print(
  f"Destination: {created_link.destination.type} n° {created_link.destination.object_id}, topology id: {created_link.source.topology_uniq_id}"
)
```
#### Export a Simulation
In most of the cases, sat com topology user will need to load a simulation and export it as
a new format.

```python
from sat_com_adapter.adapters import NetworkXAdapter

networkx_adapter = NetworkXAdapter(simulation_manager)

my_graph = networkx_adapter.create_full_networkx_graph()

networkx_adapter.adapt("OUTPUT_PATH")

```
#### I just want my constellation in the good format
Here a copy-paste friendly example of how to generate your topology and export it to networkx.

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
Here are some tutorials in the Jupyter Notebook format:
- [Create my first simulation](https://github.com/elbarbi/sat_com_topology_tutorials/blob/main/src/create_my_first_simulation.ipynb)
- [Learn to  deeply use satComTopology](https://github.com/elbarbi/satComTopologyTutorials/blob/main/src/deeply_understand_sat_com_topology.ipynb)

The tutorials aren't on gitlab yet, to have an access:
louis.barbier at isae-supaero.fr

## Contributing
The contributing guide is [here](https://github.com/elbarbi/satComTopology/blob/develop/CONTRIBUTING.md).

## License ⚖️
The project is licensed under the GNU General Public License v3.0 license.
