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
  * [Install Main Version](#install-main-version)
  * [Example 🖊️](#example-)
    * [Load a configuration](#load-a-configuration)
    * [Manage a Simulation](#manage-a-simulation)
      * [Export a Simulation](#export-a-simulation)
      * [I just want my constellation in the good format](#i-just-want-my-constellation-in-the-good-format)
  * [Tutorials 🎓](#tutorials-)
  * [Urgent Todo 🚨](#urgent-todo-)
  * [License ⚖️](#license-)
<!-- TOC -->

## Features 📢
### Packages 📦
- sat_com_model: [Topology Model](src/sat_com_model/README.md)
- sat_com_builder: [Topology Simulation builder](src/sat_com_builder/README.md)
- sat_com_adapter: [Topology Adapters](src/sat_com_adapter/README.md)
- sat_com_trajectopy: [Topology Physic Manager](src/sat_com_trajectopy/README.md)
- sat_com_application: [Topology Application](src/sat_com_application/README.md)

## Installation 📃
## Install Main Version
```shell
pip uninstall sat_com_topology -y
pip install git+https://github.com/elbarbi/satComTopology.git@main#egg=sat_com_topology
```

## Example 🖊️
### Load a configuration
An example of a YAML configuration is located [here](src/sat_com_builder/examples/configuration_example.yaml).
```python
from sat_com_builder.configuration_manager import YamlConfigurationManager

yaml_configuration_manager = YamlConfigurationManager("/CONFIGURATION_PATH/configuration_example.yaml")

simulation_manager = yaml_configuration_manager.load_simulation()
```
### Manage a Simulation
The following code is an example of how to manually create a link between a satellite and a ground station.

```python
ground_station = simulation_manager.get_ground_station_by_object_id(0)

satellite = simulation_manager.get_satellite_by_object_id(0)

created_link = simulation_manager.create_ground_station_link_connection(
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

networkx_adapter = NetworkXAdapter(simulation_manager, "OUTPUT_PATH")

my_graph = networkx_adapter.create_full_networkx_graph()

networkx_adapter.adapt()

```
#### I just want my constellation in the good format
Here a copy-paste friendly example of how to generate your topology and export it to networkx.

```python
from sat_com_builder.configuration_manager import YamlConfigurationManager
from sat_com_adapter.adapters import NetworkXAdapter

yaml_configuration_manager = YamlConfigurationManager("/CONFIGURATION_PATH/configuration_example.yaml")

simulation_manager = yaml_configuration_manager.load_simulation()

networkx_adapter = NetworkXAdapter(simulation_manager, "OUTPUT_PATH")

my_graph = networkx_adapter.create_full_networkx_graph()

networkx_adapter.adapt()
```
## Tutorials 🎓
Here are some tutorials in the Jupyter Notebook format:
- [Create my first simulation](https://github.com/elbarbi/sat_com_topology_tutorials/blob/main/src/create_my_first_simulation.ipynb)
- [Learn to  deeply use satComTopology] coming soon...

## Urgent Todo 🚨
- Fixing networkx export, adapt() export a default topology, without data
- Search a new way to implement a Data generator (generate distance, delay, etc.), maybe in the sat_com_trajectopy.

## License ⚖️
The project is licensed under the GNU General Public License v3.0 license.