# sat_com_application Package

## Description

This package provides the main API for managing a satellite constellation simulation.
The **SimulationManager** is the single entry point for all state mutations — topology objects,
links, optical terminals, and connectivity strategies are all managed through it.
Models in `sat_com_model` are never mutated directly outside of the manager.

---

## Instantiation

```python
from sat_com_application.simulation_manager import SimulationManager
from sat_com_model.models import Simulation

simulation = Simulation()
manager = SimulationManager(simulation)
```

Optionally attach an **EventBus** to receive topology events:

```python
from sat_com_application.event_bus.bus import EventBus

bus = EventBus()
manager = SimulationManager(simulation, event_bus=bus)
```

---

## Adding Topology Objects

Every object must be added through the manager so it receives a unique `topology_uniq_id`.

```python
from sat_com_model.models import Satellite, GroundStation, UserTerminal, WalkerShell

manager.add_satellite(satellite)
manager.add_ground_station(ground_station)
manager.add_user_terminals(user_terminal)
manager.add_point_of_presence(point_of_presence)

# Bulk helpers
manager.add_all_satellites(list_of_satellites)
manager.add_all_ground_stations(list_of_ground_stations)
manager.add_all_user_terminals(list_of_user_terminals)

# Shell registration
manager.add_walker_shell(walker_shell)
manager.add_sso_shell(sso_shell)
```

---

## Querying Topology Objects

```python
# By object_id (business identifier)
satellite      = manager.get_satellite_by_object_id(object_id=42)
ground_station = manager.get_ground_station_by_object_id(object_id=1)
user_terminal  = manager.get_user_terminal_by_object_id(object_id=7)

# By topology_uniq_id (simulation identifier)
obj = manager.get_topology_object_from_uniq_id(uniq_id=105)

# Collections
all_satellites      = manager.get_satellites()
all_ground_stations = manager.get_ground_stations()
all_user_terminals  = manager.get_user_terminals()
all_topology        = manager.get_all_topology_objects()
all_ground_objects  = manager.get_all_ground_objects()

# Filtered by shell type
walker_satellites = manager.get_walker_shell_satellites()
sso_satellites    = manager.get_sso_shell_satellites()

# Filtered by orbital phase
ascending  = manager.get_ascending_satellites()
descending = manager.get_descending_satellites()
```

Domain lookups raise `TopologyObjectNotFoundError` when the object is not found.

---

## Managing Links

### Inter-Satellite Links (ISL)

```python
# Create — terminals and constraints are optional
link = manager.create_and_add_inter_satellite_link_connection(
    satellite_a=sat_a,
    satellite_b=sat_b,
    terminal_a=terminal_a,                          # OpticalLinkTerminal, optional
    terminal_b=terminal_b,                          # OpticalLinkTerminal, optional
    satellite_a_constraint=optical_constraint_a,    # OpticalConstraint, optional
    satellite_b_constraint=optical_constraint_b,    # OpticalConstraint, optional
    inter_satellite_link_direction=InterSatelliteLinkDirection.ORBITAL,
)

# Bind optical terminals to an existing link
manager.bind_optical_inter_satellite_links(
    satellite_a=sat_a,
    satellite_b=sat_b,
    terminal_a=terminal_a,
    terminal_b=terminal_b,
    link=link,
)

# Update optical constraints on an existing link
manager.update_inter_satellite_link(
    inter_satellite_link=link,
    optical_constraint_a_to_b=constraint_a,
    optical_constraint_b_to_a=constraint_b,
)

# Remove — unbinds terminals, clears flows, removes from satellite link lists
manager.remove_inter_satellite_link(link)
```

`bind_optical_inter_satellite_links` raises:
- `LinkNotFoundError` if the link is not registered in the simulation.
- `OpticalLinkTerminalNotFoundError` if a terminal does not belong to the given satellite.

### Ground Station Links (GSL)

```python
link = manager.create_and_add_ground_station_link_connection(
    satellite=satellite,
    ground_station=ground_station,
    elevation_above_horizon_angle=25.0,   # degrees, optional
    estimated_link_duration=300.0,        # seconds, optional
)

manager.update_ground_station_link(
    ground_to_space_link=link,
    connection_info={
        "elevation_above_horizon_angle": 28.5,
        "estimated_link_duration": 280.0,
        "distance_km": 850.0,
    },
)

manager.remove_ground_station_link(link)
```

### User Terminal Links (UTL)

```python
link = manager.create_and_add_user_terminal_link_connection(
    satellite=satellite,
    user_terminal=user_terminal,
    elevation_above_horizon_angle=15.0,
    estimated_link_duration=120.0,
)

manager.update_user_terminal_link(
    user_terminal_link=link,
    connection_info={
        "elevation_above_horizon_angle": 18.0,
        "estimated_link_duration": 115.0,
        "distance_km": 1200.0,
    },
)

manager.remove_user_terminal_link(link)
```

### Generic link removal

```python
# Dispatches to the correct remove method based on link type
manager.remove_link(link)
```

### Querying links

```python
all_links = manager.get_all_links()                   # ISL + GSL + UTL + GroundObjectLink

isl_links = manager.get_inter_satellites_links()
gsl_links = manager.get_ground_stations_links()
utl_links = manager.get_user_terminal_links()
gol_links = manager.get_static_ground_object_links()

# Find the link between two specific objects
link = manager.get_link_connecting_topology_objects(topology_object_a, topology_object_b)

# All links attached to one object
connected = manager.get_link_connected_to_topology_object(topology_object)

# Ground station links connected to a specific ground station (enabled only)
gsl = manager.get_ground_station_links_connected_to_a_ground_station(ground_station_id)
```

---

## Removing Topology Objects (Cascade)

Cascade removal removes the object **and all links connected to it**.
For satellites, this also unbinds all optical terminals.

```python
# By object reference
manager.remove_cascade_topology_object(satellite)
manager.remove_cascade_topology_object(ground_station)
manager.remove_cascade_topology_object(user_terminal)

# By topology_uniq_id — returns list of removed objects and links
removed = manager.remove_cascade_topology_object_by_id(topology_uniq_id=105)

# Bulk removal
manager.remove_all_satellites()
manager.remove_all_ground_stations()
manager.remove_all_terminal_users()
manager.remove_all_point_of_presences()
```

---

## ISL Connectivity Strategy

The ISL update loop delegates all link assignment decisions to a pluggable strategy.
The strategy is pure — it only computes what should change and returns a result object.
The manager applies those changes.

```python
from sat_com_connectivity.inter_satellite_link_connectivity.strategies import (
    InterShellSSOPriorityConnectivity,
    IntraShellStaticConnectivity,
)

strategy = InterShellSSOPriorityConnectivity(
    satellites=manager.get_satellites(),
    shell_and_plans=manager.shell_addressing_plans,
)

manager.inter_satellite_link_connection_strategy = strategy

# Trigger manually
manager.update_inter_satellite_links()
```

On each call `update_inter_satellite_links()` will:
1. Call `strategy.compute_strategy()` to get new / obsolete / updated link associations.
2. Remove every obsolete link (unbinding terminals first).
3. Update optical constraints on every updated link.
4. Create every new link with its terminals and constraints bound.

Raises `ValueError` if no strategy has been set.

---

## Ground Connectivity Strategies

Ground-to-space links are updated per ground object using registered strategies.

```python
manager.update_ground_station_links()   # re-evaluates all GSLs
manager.update_user_terminal_links()    # re-evaluates all UTLs
```

Set `static_ground_station_link_mode = True` to use a static mode that disables
out-of-range links rather than removing and recreating them each tick.

---

## Routing and Flow Management

```python
# Reconstruct a path and attach a Flow object to each link along it
links_with_flow = manager.reconstruct_path_to_and_add_flow(
    topology_object_id_list=[sat_a_id, sat_b_id, gs_id]
)

# Reconstruct the path without adding flows
links = manager.reconstruct_path(
    topology_object_id_list=[sat_a_id, sat_b_id, gs_id]
)

# Append multiple flow paths at once
touched_links = manager.append_flows(list_of_flow_paths)
```

---

## Distance Queries

Requires a `DistanceModel` to be set on the simulation.

```python
km_ground  = manager.get_distance_between_two_topology_object_km(obj_a, obj_b)
km_3d      = manager.get_3d_distance_between_two_topology_object_km(obj_a, obj_b)
closest    = manager.get_closest_satellite_to_a_ground_station(ground_station)
```

---

## Update Protocol

The default update protocol runs on every simulation tick in this order:

```
1. update_satellites              — calls satellite.update() on all satellites
2. update_ground_stations         — calls ground_station.update() on all ground stations
3. update_user_terminal           — calls user_terminal.update() on all user terminals
4. update_ground_station_links    — re-evaluates GSLs via strategy
5. update_user_terminal_links     — re-evaluates UTLs via strategy
6. update_inter_satellite_links   — re-evaluates ISLs via strategy
```

Customise the protocol:

```python
# Replace entirely
manager.set_callable_protocol([
    manager.update_satellites,
    manager.update_inter_satellite_links,
])

# Append a custom step
manager.add_to_update_protocol(my_custom_function)

# Remove a step
manager.remove_from_update_protocol(manager.update_user_terminal_links)
```

Attach a time manager to drive the tick loop automatically:

```python
manager.set_time_manager(time_manager)
```

---

## Events

When an **EventBus** is provided, the manager publishes events on every state change:

| Event | Trigger |
|---|---|
| `ISLCreatedEvent` | ISL created |
| `ISLRemovedEvent` | ISL removed |
| `ISLUpdatedEvent` | ISL constraints updated |
| `GSLCreatedEvent` | GSL created |
| `GSLRemovedEvent` | GSL removed |
| `GSLUpdatedEvent` | GSL elevation / duration updated |
| `UTLCreatedEvent` | UTL created |
| `UTLRemovedEvent` | UTL removed |
| `UTLUpdatedEvent` | UTL elevation / duration updated |

Events carry `sim_time` automatically if a time manager is attached.

---

## Shell and Domain Lookups

```python
shell  = manager.get_walker_shell(identifier="andromeda")
shells = manager.get_walker_shells()
ssos   = manager.get_sso_shells()

domain = manager.get_ground_object_domain(identifier="public")
```

Both raise descriptive errors (`WalkerShellNotFoundError`, `GroundObjectDomainNotFoundError`)
if the identifier is not found.