# sat_com_model Package

## Description

This package is the Python model of a satellite network topology. It provides the core building blocks
for describing constellations, inter-satellite links, ground infrastructure, and the optical terminal
system that governs how links are physically assigned.

A topology is a set of objects that exchange data through links. Every object is a **SpatialPoint** with
a real position (longitude, latitude, altitude). Defining the position is optional — you can work with
a virtual topology and never call the position system.

---

## Coordinate System

**SpatialPosition** holds the coordinates of any object: `longitude`, `latitude`, `altitude`.
Units for altitude are not enforced — km or meters depending on your implementation.

---

## Topology Objects

**TopologyObject** extends **SpatialPoint**. Every topology object carries:
- A `topology_uniq_id` assigned by the **Simulation** at insertion time.
- An `object_id` provided by the data source (e.g. satellite catalogue number).
- A `domain` string for multi-operator scenarios (default: `"public"`).
- A `links` list of all links connected to this object.

### Orbital objects

**OrbitalObject** adds a **MovementModel** — an abstract interface that your propagator must implement:

| Method | Description |
|---|---|
| `get_longitude_latitude_altitude(delta_t)` | Ground-projected position |
| `get_position_earth_general_inertial(delta)` | ECI position [km] |
| `get_velocity_earth_general_inertial(delta)` | ECI velocity [km/s] |
| `is_ascending()` | True if satellite is in ascending orbital phase |

**Satellite** 🛰 extends **OrbitalObject**. It belongs to a **Shell** and is automatically equipped
with **OpticalLinkTerminal**s at construction time based on the shell's **SatelliteConfiguration**.

### Ground objects

| Class | Description |
|---|---|
| **GroundStation** 📡 | Fixed station connected to the constellation and internet backbone |
| **UserTerminal** 📻 | Individual user device (dish, phone, etc.) |
| **PointOfPresence** | Internet backbone connection point |

---

## Shells

A **Shell** describes a group of satellites sharing the same orbital configuration.
Shells are immutable (`frozen=True`) and hashable via a `shell_id` UUID.

| Class | Use |
|---|---|
| **WalkerShell** | Walker delta or star constellation |
| **DawnDuskSSOShell** | Dawn-dusk sun-synchronous orbit ring |

Each shell carries a **SatelliteConfiguration** which lists one **OpticalTerminalInstallationConfiguration**
per terminal position. Every satellite in the shell is built with those terminals automatically.

---

## Optical Terminal System

### OpticalTerminalConfiguration

Physical constraints of one terminal (CONDOR gen1 defaults):

| Field | Default | Description |
|---|---|---|
| `max_azimuth_degrees` | 175° | Half-angle FoV from boresight |
| `min_elevation_degrees` | −25° | Lower elevation limit |
| `max_elevation_degrees` | +5° | Upper elevation limit |
| `maximum_range_distance_km` | 7800 km | Maximum ISL range |
| `maximum_angular_velocity_degree_per_second` | 1°/s | Max LOS angular rate |

These constraints are only used by the **advanced** optical link model (see
`OpticalInterSatelliteLinkModel` below). In the basic model, the default, a
terminal is a connection slot: only its orientation is used.

### OpticalLinkTerminal

One physical terminal mounted on a satellite. Key fields:

| Field | Description |
|---|---|
| `terminal_id` | Immutable UUID — used for hashing and equality |
| `host_satellite` | Back-reference to the owning satellite (frozen, excluded from serialisation) |
| `descriptor` | Primary orientation label (`INTRA_PLANE_FORWARD`, `INTER_PLANE_LEFT`, etc.) |
| `orientation_possibilities` | All link types this terminal can serve (e.g. also `INTER_SHELL_LEFT`) |
| `azimuth_angle_configuration` | Boresight azimuth in LVLH frame [°] |
| `elevation_angle_configuration` | Boresight elevation in LVLH frame [°] |
| `link` | The **InterSatelliteLink** currently bound to this terminal (`None` if free) |
| `target_optical_link_terminal` | Peer terminal on the other end of the active link |

Terminals are hashable via `terminal_id` and safe to use in sets and dict keys.

### InterSatelliteLinkOrientation

Enum describing the directional role of a terminal:

```
INTRA_PLANE_FORWARD / BACKWARD   — along-track neighbours
INTER_PLANE_LEFT / RIGHT         — cross-plane neighbours
INTER_SHELL_FORWARD / BACKWARD / LEFT / RIGHT  — cross-shell bridges
CROSS_PLANE_*                    — diagonal neighbours
```

---

## Links

**Link** is the base class for all connections. Every link carries:
- A `link_id` UUID — used for hashing and equality (links are safe to use in sets).
- `source` and `destination` topology objects.
- A `flows` list for traffic routing.
- `disabled` flag.

Links are bidirectional — source and destination are symmetric for routing purposes.

| Class | Connects | Extra fields |
|---|---|---|
| **InterSatelliteLink** | Satellite ↔ Satellite | `inter_satellite_direction`, `source_constraint`, `destination_constraint`, `source_optical_terminal`, `destination_optical_terminal`, `optical_link_model`, `distance_km` |
| **GroundStationLink** | Satellite ↔ GroundStation | `elevation_above_horizon_angle`, `estimated_link_duration` |
| **UserTerminalLink** | Satellite ↔ UserTerminal | `elevation_above_horizon_angle`, `estimated_link_duration` |
| **GroundObjectLink** | GroundObject ↔ GroundObject | Static ground-to-ground backbone |

### InterSatelliteLink lifecycle

**Connecting:**
```python
link.connect(
    source=satellite_a,
    destination=satellite_b,
    source_optical_terminal=terminal_a,
    destination_optical_terminal=terminal_b,
    source_constraint=optical_constraint_a,
    destination_constraint=optical_constraint_b,
    inter_satellite_direction=InterSatelliteLinkDirection.ORBITAL,
)
```

**Binding terminals explicitly** (after `connect`):
```python
link.bind_terminals(
    source_terminal=terminal_a,
    destination_terminal=terminal_b,
    source_constraint=constraint_a,
    destination_constraint=constraint_b,
)
```
`bind_terminals` wires all back-references atomically:
`link → terminals`, `terminal.link → link`, `terminal.target_optical_link_terminal → peer`.

**Unbinding** (call before removing the link so terminals return to the free pool):
```python
link.unbind_terminals()
```

### InterSatelliteLinkDirection

| Value | Meaning |
|---|---|
| `ORBITAL` | Along-track (same orbital plane) |
| `ADJACENT` | Cross-plane (adjacent orbital plane) |
| `INTER_SHELL` | Cross-shell (different constellation layer) |
| `UNDEFINED` | Not yet assigned |

### OpticalInterSatelliteLinkModel

How optical inter-satellite links are computed, set for the whole simulation by
`SimulationProperty.optical_inter_satellite_link_model`:

| Value | Meaning |
|---|---|
| `BASIC` (default) | Links follow the addressing plans. No optical metric is computed: `source_constraint` and `destination_constraint` are `None` by design. |
| `ADVANCED` | Links are checked against their terminals configuration every tick. The constraints are always set. |

Each **InterSatelliteLink** records the model it was computed with in
`optical_link_model`, and `has_optical_metrics` is `True` for `ADVANCED`. A `None`
constraint is therefore expected on a basic link and never happens on an advanced
one. In a basic simulation, a strategy that needs the metrics (inter-shell links)
still produces advanced links.

`distance_km` is the straight-line distance between the two satellites, set by the
`SimulationManager` at every update: computed from the satellites positions for a
basic link, the range of the constraints for an advanced one.

### OpticalConstraint

Snapshot of the physical link state at the time of assignment (advanced model only):

| Field | Description |
|---|---|
| `azimuth_angle_degree` | Actual azimuth from terminal A to terminal B [°] |
| `elevation_angle_degree` | Actual elevation [°] |
| `range_distance_km` | Link distance [km] |
| `angular_velocity_rate_degree_per_second` | LOS angular rate [°/s] |

---

## Simulation

**Simulation** is the registry that holds everything:

```
satellites                — list[Satellite]
inter_satellite_links     — list[InterSatelliteLink]
ground_stations           — list[GroundStation]
ground_station_links      — list[GroundStationLink]
user_terminals            — list[UserTerminal]
user_terminal_links       — list[UserTerminalLink]
point_of_presences        — list[PointOfPresence]
walker_shells             — list[WalkerShell]
down_dusk_sso_shells      — list[DawnDuskSSOShell]
ground_object_domains     — list[GroundObjectDomain]
ground_object_links       — list[GroundObjectLink]
```

`simulation.request_an_id()` returns the next sequential `topology_uniq_id` and increments the counter.
Every topology object must be registered through the **SimulationManager** so it receives its id — never
set `topology_uniq_id` manually outside tests.

---

## Class Hierarchy Summary

```
SpatialPoint
└── TopologyObject
    ├── OrbitalObject
    │   └── Satellite[T_Shell]       ← has list[OpticalLinkTerminal]
    └── GroundObject
        ├── GroundStation
        ├── UserTerminal
        └── PointOfPresence

Link
├── InterSatelliteLink               ← bind_terminals / unbind_terminals
├── GroundToSpaceLink
│   ├── GroundStationLink
│   └── UserTerminalLink
└── GroundObjectLink

Shell (frozen, hashable)
├── WalkerShell
└── DawnDuskSSOShell
```

---

## Notes

- All Pydantic models use `topology_uniq_id`-based equality for **TopologyObject** and
  `terminal_id`-based equality for **OpticalLinkTerminal** — not Python object identity.
- **Link** equality and hashing is based on `link_id`, making links safe to store in sets
  across the connectivity ledger.
- `Shell` is frozen — all fields are immutable after construction.
- Back-reference fields (`link`, `host_satellite`, `target_optical_link_terminal`) are excluded
  from Pydantic serialisation to prevent circular reference errors.
