# EmulatorAdapter

## Overview

`EmulatorAdapter` is a passive listener that sits on top of the simulation event bus and records every link lifecycle event into a structured timeline, one entry per topology node. It does not drive the simulation — it only reacts to what the bus delivers.

The output can be serialised to JSON or exported as a ready-to-run Mininet Python script.

---

## Architecture

```
EventBus (wired at simulation construction)
    │
    ├── SimulationManager  →  publishes GSLCreatedEvent, ISLRemovedEvent, ...
    │
    └── EmulatorAdapter    →  subscribes, records into timeline
```

The critical constraint is that the adapter must subscribe **before** `load_simulation` is called, so that initial link creation events are captured:

```python
event_bus = EventBus()
adapter = EmulatorAdapter(event_bus=event_bus)          # subscribe first

simulation_manager = BaseConfigurationManager(
    simulation_property=properties,
    event_bus=event_bus,                                # same bus
).load_simulation()
```

---

## Event types recorded

| Bus event | LinkEventType recorded |
|---|---|
| `GSLCreatedEvent` | `LINK_CONNECTED` |
| `GSLUpdatedEvent` | `LINK_UPDATED` |
| `GSLRemovedEvent` | `LINK_DISCONNECTED` |
| `UTLCreatedEvent` | `LINK_CONNECTED` |
| `UTLUpdatedEvent` | `LINK_UPDATED` |
| `UTLRemovedEvent` | `LINK_DISCONNECTED` |
| `ISLCreatedEvent` | `LINK_CONNECTED` |
| `ISLUpdatedEvent` | `LINK_UPDATED` |
| `ISLRemovedEvent` | `LINK_DISCONNECTED` |

Each event is recorded **symmetrically** — both endpoints of a link receive an entry pointing to the other. Duplicate events at the same timestamp are silently dropped.

---

## Timeline structure

```python
{
    56: [
        LinkEvent(sim_time=t0, event_type=LINK_CONNECTED,    peer_id=3,  metadata={"elevation_angle": 32.1, "estimated_duration": 412.0}),
        LinkEvent(sim_time=t1, event_type=LINK_UPDATED,      peer_id=3,  metadata={"elevation_angle": 41.5, "distance_km": 820.3}),
        LinkEvent(sim_time=t2, event_type=LINK_DISCONNECTED, peer_id=3,  metadata={}),
        LinkEvent(sim_time=t3, event_type=LINK_CONNECTED,    peer_id=17, metadata={"elevation_angle": 22.0, "estimated_duration": 600.0}),
    ],
    3: [
        ...  # mirror of node 56's events, with peer_id=56
    ]
}
```

- **Key**: `topology_uniq_id` of the node
- **Value**: chronologically sorted list of `LinkEvent`
- **peer_id**: `topology_uniq_id` of the other endpoint

---

## Running the simulation

The adapter does not tick the simulation. Ticking is done externally. Because `SimulationManager.__publish_event` calls `asyncio.run()` directly, events are delivered synchronously during each tick — no event loop yielding is required:

```python
while (
    simulation_manager.time_manager.current_time
    < simulation_manager.time_manager.end_date
):
    simulation_manager.time_manager.tick(granularity_seconds)
```

---

## Full usage example

```python
import asyncio
from sat_com_application.event_bus.bus import EventBus
from sat_com_adapter.emulator_adapter import EmulatorAdapter
from sat_com_builder.configuration_manager import BaseConfigurationManager
from sat_com_builder.models import SimulationProperty

# 1. Create the shared event bus
event_bus = EventBus()

# 2. Subscribe the adapter BEFORE load_simulation fires any events
adapter = EmulatorAdapter(event_bus=event_bus)

# 3. Build and load the simulation with the same bus
simulation_manager = BaseConfigurationManager(
    simulation_property=SimulationProperty(**config),
    event_bus=event_bus,
).load_simulation()

# 4. Tick the simulation externally
while (
    simulation_manager.time_manager.current_time
    < simulation_manager.time_manager.end_date
):
    simulation_manager.time_manager.tick(60.0)
    # Events are delivered synchronously inside each tick via asyncio.run()

# 5. Inspect the timeline
timeline = adapter.timeline          # raw defaultdict
sorted_tl = adapter.get_sorted_timeline()  # chronologically sorted

# 6. Export
json_data   = adapter.to_dict()              # JSON-serialisable dict
mininet_py  = adapter.to_mininet_script()    # Mininet replay script
```

---

## Exports

### `to_dict()`

Returns a JSON-serialisable dictionary keyed by node id (as string):

```json
{
  "56": [
    {
      "sim_time":   "2024-11-18T00:01:00",
      "event_type": 1,
      "peer_id":    3,
      "metadata":   { "elevation_angle": 32.1, "estimated_duration": 412.0 }
    }
  ]
}
```

### `to_mininet_script(start_time=None)`

Generates a Python script that replays the topology changes in a live Mininet network. Time offsets are computed relative to `start_time` (defaults to the first recorded event).

```python
# Auto-generated Mininet event script
import time

def replay(net, start_time):
    time.sleep(max(0, start_time + 0.000 - time.time()))
    net.addLink(node_3, node_56)
    time.sleep(max(0, start_time + 412.000 - time.time()))
    net.delLink(net.linksBetween(node_3, node_56)[0])
    ...
```

Node names follow the convention `node_<topology_uniq_id>`. Only one command is emitted per pair (from the lower id), preventing duplicate `addLink`/`delLink` calls.

---

## Design constraints

| Constraint | Rationale |
|---|---|
| Adapter takes only `EventBus` as input | Decoupled from `SimulationManager` — can listen to any producer |
| Simulation state is never mutated by the adapter | Follows the rule that only `SimulationManager` modifies simulation data |
| Adapter must be created before `load_simulation` | Initial link creation events must be captured from the start |
| `__publish_event` uses `asyncio.run()` | Events are delivered synchronously inside each tick — no running loop required |
| Duplicates are silently dropped | The simulation can fire multiple events for the same pair at the same tick in some strategies |
