# sat_com_builder Package
## Description
This package is used the build a simulation based on the sat_com_model.
It features:
- JSON / YAML / object dictionary configuration
- ground station, user terminal and point of presence generation (from a data file or inline)
- satellite generation (Walker delta, Walker star and dawn-dusk SSO shells)
- links generation
- movement model parameters
- injection of your own topology object classes (see [Inject your own topology objects](#inject-your-own-topology-objects))

## Example
These examples show how to load a simulation.

### From JSON
Examples: [single shell](examples/single_shell_configuration_example.json),
[multi shell](examples/multi_shell_configuration_example.json) (shows every V5 option).

```python
import json

from sat_com_builder.configuration_manager import BaseConfigurationManager
from sat_com_builder.models import SimulationProperty

with open("examples/multi_shell_configuration_example.json") as file:
    simulation_property = SimulationProperty(**json.load(file))

simulation_manager = BaseConfigurationManager(simulation_property).load_simulation()
```

### From YAML

```python
from sat_com_builder.configuration_manager import YamlConfigurationManager

yaml_configuration_manager = YamlConfigurationManager("examples/single_shell_configuration_example.yaml")

simulation_manager = yaml_configuration_manager.load_simulation()
```

### From object dictionary or Simulation Property
You can directly initialise a dictionary as long it respects SimulationProperty typing rules.
```python
from sat_com_builder.configuration_manager import BaseConfigurationManager
from sat_com_builder.models import SimulationProperty

object_configuration_manager = BaseConfigurationManager(SimulationProperty())

simulation_manager = object_configuration_manager.load_simulation()
```

### Ground objects
Each entry of `ground_objects_properties` is a set of ground objects (`ground_station`,
`user_terminal` or `point_of_presence`). Its objects come from a `data_file`
(one `id,label,latitude,longitude,altitude` per line), from `ground_objects` written
inline, or both (file first, then inline):

```json
{
  "identifier": "Inline Points of Presence",
  "type": "point_of_presence",
  "ground_objects": [
    {"id": 0, "label": "Paris", "latitude": 48.85, "longitude": 2.35, "altitude": 0.0}
  ],
  "connectivity_properties": {
    "elevation_above_horizon": 20,
    "ground_to_space_connections_strategy": "best-angle-until-disconnection"
  }
}
```

### Inter-satellite link options
Two `SimulationProperty` fields select how inter-satellite links are computed:

| Field | Values | Default |
|---|---|---|
| `inter_satellite_link_connection_strategy` | `intra-shell-static-connectivity`, `inter-shell-sso-priority` | `intra-shell-static-connectivity` |
| `optical_inter_satellite_link_model` | `basic`, `advanced` | `basic` |

- `basic`: links follow each shell addressing plan, no optical metric is computed
  and links are never dropped for geometry. Only the distance is computed.
- `advanced`: every link is checked against its optical terminals configuration
  (elevation, azimuth, range, angular velocity, line of sight) and carries its
  optical constraints.

With `inter-shell-sso-priority`, the inter-shell links are always computed with the
optical metrics; the model only applies to the intra-shell links. See
[sat_com_connectivity](../sat_com_connectivity/README.md#inter-satellite-link-connectivity).

```json
{
  "inter_satellite_link_connection_strategy": "inter-shell-sso-priority",
  "optical_inter_satellite_link_model": "advanced"
}
```

### Removed parameters
These parameters were never used. A configuration that still sets them loads, and each
one raises a `FutureWarning` (`Parameter X was never used and will be removed`):
- `static_ground_station_link_mode`
- in `orbital_connectivity_property`: `maximum_inter_satellite_count`,
  `maximum_inter_satellite_range_distance`, `maximum_ground_station_range`,
  `maximum_user_terminal_range`

### Create an Empty Simulation
```python
from sat_com_builder.configuration_manager import  EmptyConfigurationManager

empty_configuration_manager = EmptyConfigurationManager()

simulation_manager = empty_configuration_manager.load_simulation()
```

## Inject your own topology objects
The builder never instantiates `Satellite`, `GroundStation`, `UserTerminal` or
`PointOfPresence` directly: it asks a factory. Replace a factory to get your own
subclass in the simulation, with your own fields and methods. Everything else
(connectivity, events, exports) keeps working, because your class is still a `Satellite`.

| Object | Abstract factory (`sat_com_model.factories`) | Method | Default (`sat_com_builder.factories`) |
|---|---|---|---|
| Satellite | `AbstractSatelliteFactory` | `create_satellite(satellite_name, object_id, shell, movement_model, domain)` | `DefaultSatelliteFactory` |
| Ground station | `AbstractGroundStationFactory` | `create_ground_station(object_id, label, longitude, latitude, altitude, ground_object_domain)` | `DefaultGroundStationFactory` |
| User terminal | `AbstractUserTerminalFactory` | `create_user_terminal(...)` (same parameters) | `DefaultUserTerminalFactory` |
| Point of presence | `AbstractPointOfPresenceFactory` | `create_point_of_presence(...)` (same parameters) | `DefaultPointOfPresenceFactory` |

The four factories are grouped in `TopologyObjectFactories`. Any factory you don't set
keeps its default.

### Tutorial: satellites that are routers
An emulator needs every satellite to be a network node, with an IPv4 address and
interfaces. We build a `SatelliteRouter`: a `Satellite` plus a `NetworkMixin`.

**1. The network mixin and the router class.** Topology objects are pydantic models,
so the mixin must be a pydantic `BaseModel` too: its fields are then validated and
exported like the satellite ones.

```python
import ipaddress

from pydantic import BaseModel, Field

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
```

**2. The factory.** A factory is an object, so it can keep a state: here, the pool of
free addresses, shared by every shell of the constellation.

```python
from sat_com_model.factories import AbstractSatelliteFactory


class SatelliteRouterFactory(AbstractSatelliteFactory):
    def __init__(self, subnet: str = "10.0.0.0/16"):
        self._free_addresses = ipaddress.IPv4Network(subnet).hosts()

    def create_satellite(
        self, satellite_name, object_id, shell, movement_model, domain="public"
    ) -> SatelliteRouter:
        ipv4_address = next(self._free_addresses)
        satellite = SatelliteRouter(
            satellite_name=satellite_name,
            object_id=object_id,
            shell=shell,
            movement_model=movement_model,
            domain=domain,
            ipv4_address=ipv4_address,
        )

        # One interface per optical terminal. The terminals exist once the
        # satellite is built (they come from the shell satellite configuration).
        mac_prefix = "02:" + ":".join(f"{byte:02x}" for byte in ipv4_address.packed)
        satellite.interfaces = [
            NetworkInterface(name=f"isl{index}", mac_address=f"{mac_prefix}:{index:02x}")
            for index, _ in enumerate(satellite.optical_link_terminals)
        ]
        return satellite
```

**3. Inject it** in any configuration manager (`BaseConfigurationManager`,
`YamlConfigurationManager`), the same way as the event factories:

```python
from sat_com_builder.configuration_manager import BaseConfigurationManager
from sat_com_builder.factories import TopologyObjectFactories

simulation_manager = BaseConfigurationManager(
    simulation_property=simulation_property,
    topology_object_factories=TopologyObjectFactories(
        satellite_factory=SatelliteRouterFactory()
    ),
).load_simulation()

satellite = simulation_manager.get_satellites()[0]
print(type(satellite).__name__, satellite.ipv4_address)  # SatelliteRouter 10.0.0.1
print([interface.name for interface in satellite.interfaces])  # ['isl0', 'isl1', 'isl2', 'isl3']
```

### Ground objects
Ground object factories work the same way. Use `_configure_ground_object` to set the
position, label and domain shared by every ground object:

```python
from sat_com_model.factories import AbstractGroundStationFactory
from sat_com_model.models import GroundStation


class GroundStationRouter(GroundStation, NetworkMixin):
    pass


class GroundStationRouterFactory(AbstractGroundStationFactory):
    def create_ground_station(
        self, object_id, label="unknown", longitude=0.0, latitude=0.0,
        altitude=0.0, ground_object_domain=None,
    ) -> GroundStationRouter:
        ground_station = GroundStationRouter(
            object_id=object_id,
            domain=ground_object_domain.identifier if ground_object_domain else "public",
        )
        return self._configure_ground_object(
            ground_station, label, longitude, latitude, altitude, ground_object_domain
        )


factories = TopologyObjectFactories(
    satellite_factory=SatelliteRouterFactory("10.0.0.0/16"),
    ground_station_factory=GroundStationRouterFactory(),
)
```

### Notes
- Your subclass is a pydantic model: define its fields with type hints, and give them a
  default (the factory signature only passes the standard parameters).
- The generators (`generate_ground_stations_from_file`, `generate_satellites_from_walker_constellation`, ...)
  also take a `factory` / `satellite_factory` parameter, if you build a simulation without
  a configuration manager.
- To also customise the **events** published for your objects (for example to add the
  router IP address), see [event factories](../sat_com_application/README.md#customise-events-with-event-factories).
- Full working example: [How to use satComTopology in my emulator](../../README.md#how-to-use-satcomtopology-in-my-emulator-).

## Create your own configuration manager

```python
from sat_com_builder.configuration_manager import BaseConfigurationManager
from sat_com_application.simulation_manager import SimulationManager

class JsonConfigurationManager(BaseConfigurationManager):
    def load_simulation(self) -> SimulationManager:
        """Todo: Implement your code"""
        return SimulationManager(
            
        )

```
