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
    * [Performance 📈](#performance-)
  * [Installation 📃](#installation-)
    * [Install Main Version from GitLab](#install-main-version-from-gitlab)
    * [Install Main Version from GitHub](#install-main-version-from-github)
  * [Example 🖊️](#example-)
    * [Load a configuration](#load-a-configuration)
    * [Manage a Simulation](#manage-a-simulation)
      * [Export a Simulation](#export-a-simulation)
      * [I just want my constellation in the good format](#i-just-want-my-constellation-in-the-good-format)
  * [How to use satComTopology in my emulator 🧪](#how-to-use-satcomtopology-in-my-emulator-)
    * [Emulator workflow](#emulator-workflow)
    * [Complete example](#complete-example)
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

### Performance 📈
Bootstrap and tick time on Starlink Group 2, Starlink Group 7, OneWeb and Starlink Group 2 + SSO,
with 100 ground stations, broken down by stage: [performance page](docs/performance/README.md).
- [Performance Using Optical Links Basic Model](docs/performance/README.md#performance-using-optical-links-basic-model) (default)
- [Performance Using Optical Links Advanced Model](docs/performance/README.md#performance-using-optical-links-advanced-model) (optional)

Regenerate it with `python tests/performance_scripts/benchmark_constellations.py`.

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

## How to use satComTopology in my emulator 🧪
satComTopology computes **what the network looks like** at each instant: which satellites
and ground objects exist, which links are up, their length and duration. Your emulator
(containers, network namespaces, a network simulator...) applies it: it creates the
nodes, brings interfaces up and down, sets the link delays.

Two injection points connect both worlds, without changing satComTopology:

| What you inject | Into | So that | Docs |
|---|---|---|---|
| `topology_object_factories` | the configuration manager | the simulation is made of **your** classes (e.g. a `SatelliteRouter` with an IP address and interfaces) | [Inject your own topology objects](src/sat_com_builder/README.md#inject-your-own-topology-objects) |
| `event_bus` | the configuration manager | your emulator is **notified** of every change | [Events](src/sat_com_application/README.md#events) |
| `event_factories` | the configuration manager | the events carry **your** data (e.g. the IP addresses of both ends of a link) | [Customise events with event factories](src/sat_com_application/README.md#customise-events-with-event-factories) |

### Emulator workflow

```
configuration (JSON) ─► load_simulation() ─► TO_CREATED  ─► emulator: create the node
                                            ISL_CREATED ─► emulator: link up
         time_manager.tick(seconds) ───────► ISL_UPDATED ─► emulator: update the delay
                                            ISL_REMOVED ─► emulator: link down
                                            GSL_* / UTL_* (ground links, same idea)
```

### Complete example
This example is tested in [`tests/sat_com_topology_tests/test_emulator_tutorial.py`](tests/sat_com_topology_tests/test_emulator_tutorial.py).

**1. Your topology objects**: every satellite is a router, with an IPv4 address and one
interface per optical terminal.

```python
import ipaddress

from pydantic import BaseModel, Field

from sat_com_model.factories import AbstractSatelliteFactory
from sat_com_model.models import Satellite


class NetworkInterface(BaseModel):
    name: str
    mac_address: str
    is_up: bool = False


class NetworkMixin(BaseModel):
    ipv4_address: ipaddress.IPv4Address | None = None
    interfaces: list[NetworkInterface] = Field(default_factory=list)


class SatelliteRouter(Satellite, NetworkMixin):
    pass


class SatelliteRouterFactory(AbstractSatelliteFactory):
    def __init__(self, subnet: str = "10.0.0.0/16"):
        self._free_addresses = ipaddress.IPv4Network(subnet).hosts()

    def create_satellite(self, satellite_name, object_id, shell, movement_model, domain="public"):
        ipv4_address = next(self._free_addresses)
        satellite = SatelliteRouter(
            satellite_name=satellite_name,
            object_id=object_id,
            shell=shell,
            movement_model=movement_model,
            domain=domain,
            ipv4_address=ipv4_address,
        )
        mac_prefix = "02:" + ":".join(f"{byte:02x}" for byte in ipv4_address.packed)
        satellite.interfaces = [
            NetworkInterface(name=f"isl{index}", mac_address=f"{mac_prefix}:{index:02x}")
            for index, _ in enumerate(satellite.optical_link_terminals)
        ]
        return satellite
```

**2. Your events**: node events carry the network configuration, ISL events carry the
IP address of both ends.

```python
from sat_com_application.event_bus.events import ISLCreatedEvent, TopologyObjectCreatedEvent
from sat_com_application.event_bus.factories import (
    DefaultISLEventFactory,
    DefaultTopologyObjectEventFactory,
)
from sat_com_model.models import InterSatelliteLink, TopologyObject


class NetworkTopologyObjectEventFactory(DefaultTopologyObjectEventFactory):
    def created(self, topology_object: TopologyObject) -> TopologyObjectCreatedEvent:
        event = super().created(topology_object)
        if isinstance(topology_object, NetworkMixin):
            event.properties = {
                "ipv4_address": str(topology_object.ipv4_address),
                "interfaces": [i.model_dump() for i in topology_object.interfaces],
            }
        return event


class RoutedISLCreatedEvent(ISLCreatedEvent):
    satellite_a_ipv4: str
    satellite_b_ipv4: str


class RoutedISLEventFactory(DefaultISLEventFactory):
    def created(self, link: InterSatelliteLink) -> RoutedISLCreatedEvent:
        event = super().created(link)
        return RoutedISLCreatedEvent(
            **event.model_dump(),
            satellite_a_ipv4=str(link.get_satellite_source().ipv4_address),
            satellite_b_ipv4=str(link.get_satellite_destination().ipv4_address),
        )
```

**3. Your emulator**: subscribe to the events, inject everything, then drive the time.

```python
import json

from sat_com_application.event_bus.bus import EventBus
from sat_com_application.event_bus.events import EventType
from sat_com_application.event_bus.factories import EventFactories
from sat_com_builder.configuration_manager import BaseConfigurationManager
from sat_com_builder.factories import TopologyObjectFactories
from sat_com_builder.models import SimulationProperty


async def on_node_created(event: TopologyObjectCreatedEvent):
    print(f"create node {event.topology_object_uniq_id} {event.properties}")


async def on_link_created(event: RoutedISLCreatedEvent):
    print(f"[{event.sim_time}] link up {event.satellite_a_ipv4} <-> {event.satellite_b_ipv4} ({event.distance_km:.0f} km)")


event_bus = EventBus()
event_bus.subscribe(EventType.TO_CREATED, on_node_created)
event_bus.subscribe(EventType.ISL_CREATED, on_link_created)
# + EventType.ISL_UPDATED / ISL_REMOVED, GSL_*, UTL_* ...

with open("my_constellation.json") as file:
    simulation_property = SimulationProperty(**json.load(file))

simulation_manager = BaseConfigurationManager(
    simulation_property=simulation_property,
    event_bus=event_bus,
    event_factories=EventFactories(
        isl_event_factory=RoutedISLEventFactory(),
        topology_object_event_factory=NetworkTopologyObjectEventFactory(),
    ),
    topology_object_factories=TopologyObjectFactories(
        satellite_factory=SatelliteRouterFactory("10.0.0.0/16"),
    ),
).load_simulation()  # publishes TO_CREATED and ISL_CREATED for the initial topology

while simulation_manager.time_manager.current_time < simulation_manager.time_manager.end_date:
    simulation_manager.time_manager.tick(1)  # publishes the changes of this second
```

Tips:
- Subscribe **before** `load_simulation()`: the initial topology is published while it loads.
- Handlers are `async`. When the simulation runs inside an event loop, events are
  scheduled on it; otherwise each event is published synchronously.
- You only override what you need: factories you don't set keep their default.

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
