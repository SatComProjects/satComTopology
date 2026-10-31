# sat_com_connectivity Package
This package computes the connectivity of the simulation. It features:
- Ground object to space connectivity (ground station and user terminal links)
- Inter-satellite link (ISL) connectivity: addressing plans and strategies, with a
  basic and an advanced optical link model
- A satellite state cache shared by every connectivity computation of a simulation
- The ground-to-space geometry utilities (`sat_com_connectivity.utils`)

The strategies never modify the simulation: they compute what should change and
return a result. The `SimulationManager` (sat_com_application) applies it. Breaking
this rule ends up in circular dependencies and bugs.

Todo:
- Ground to ground connectivity management

## Geometry utilities (`sat_com_connectivity.utils`)
Ground-to-space geometry, moved from `sat_com_trajectopy.angle_utils` (the old
functions still exist there, emit a `FutureWarning` and call these ones).

Earth model: the **WGS72 ellipsoid**, the frame of the TLEs and of the SGP4
propagator (constants in `sat_com_model.constants`). Cartesian positions are ECEF,
in meters.

| Function | Description |
|---|---|
| `latitude_longitude_altitude_to_x_y_z(lat, lon, alt_m)` | Geodetic to ECEF on the WGS72 ellipsoid. The single geodetic conversion of the project. |
| `ground_to_up_vector(gnd_coords)` | Local vertical (normal to the ellipsoid) at a ground location |
| `get_elevation_angle(sat, gnd)` | Elevation angle [°] of a satellite seen from the ground |
| `get_elevation_angle_and_distance(sat, gnd)` | Elevation [°] and straight-line distance [m], from the same vector |
| `satellites_to_ecef(satellites)` | ECEF positions of a list of satellites, shape (N, 3) |
| `compute_elevations(sat_ecef, gnd_ecef, up)` | Vectorised elevations [°] |
| `compute_elevations_and_distances(sat_ecef, gnd_ecef, up)` | Vectorised elevations [°] and distances [m] |

A satellite exactly at zenith gets 90° (the `arcsin` input is clipped to [-1, 1]).

## Satellite state cache (`satellite_state_cache.py`)
One `SatelliteStateCache` per simulation, owned by the `SimulationManager`
(`manager.satellite_state_cache`). Ground strategies, ISL strategies and addressing
plans read satellite state through it, so each satellite is converted at most once
per time step, whatever the number of ground objects, shells or phases.

| Method | Content |
|---|---|
| `eci(dt)` | `EciCache` for the finite-difference step `dt`: ECI position, velocity and LVLH frame at `t` and `t + dt`, used by the optical link metrics. One cache per `dt`: a cache is refused (`ValueError`) by the optical helpers if used with another `dt`. |
| `ground_ecef(satellites)` | ECEF positions used by the ground visibility, computed once per satellite list |
| `distances_km(pairs)` | Straight-line distance [km] between the satellites of each pair, from their ECI positions |
| `invalidate()` | Drops every entry |

Validity: every entry belongs to one simulation time, read from the satellites
movement model clock. When the time changes, the cache is dropped. The
`SimulationManager` also invalidates it at the start of each tick. Cached arrays are
read-only, so a shared array cannot be modified by mistake.

Used outside a simulation (no cache given), the strategies and plans build a private
cache for each computation.

## Ground Object To Space Connectivity
This part manages the connectivity between ground objects and space objects.
It implements strategies, used by a ground object to establish a connection with a space object.
We base our limits on the ground side.

⚠️ Ground to space connectivity strategies are saved in the GroundObjectDomain of each GroundObject. The strategy will be the
same for every object of the same "domain".

The name of the strategy is stored in the main model, see
`GroundObjectDomain.ground_to_space_connections_strategy` in [models](../sat_com_model/models.py).

The strategies are instantiated by the simulation manager when loading the simulation, and executed when updating the simulation.
The manager gives every strategy its `state_cache` attribute (the simulation satellite state cache).

### GroundToSpaceConnectionStrategy

To implement a new strategy, implement the `compute_ground_object_connection_strategy` method:
```python
    def compute_ground_object_connection_strategy(
        self,
        ground_object: "GroundObject",
        satellites: list["Satellite"],
    ) -> ComputedGroundObjectConnectionsResult:
        raise NotImplementedError(
            "compute_ground_object_connection_strategy must be implemented in the subclass"
        )
```

It does not modify the simulation, it only computes the connectivity and returns the result:
```python
class ComputedGroundObjectConnectionsResult(BaseModel):
    new_ground_object_connections: list[GroundToSpaceConnection] = Field(default_factory=list)
    updated_links: list[GroundToSpaceUpdate] = Field(default_factory=list)
    obsolete_links: list[GroundToSpaceLink] = Field(default_factory=list)
```

To compute visibility, use `get_visible_satellites(satellites, ground_object, state_cache=self.state_cache)`:
the satellite positions are then shared with every other ground object, and each
returned `VisibleSatellite` carries its elevation and its distance (`distance_km`).

### Registry
We use a registry to register the strategies. This allows us to easily add new strategies without modifying the code.
Registry is automatically checked by the sat_com_builder package when loading a simulation.
You can manually register a strategy by using the `register_ground_to_space_connectivity_strategy` decorator or manually
register it using the dictionary `GROUND_TO_SPACE_CONNECTION_STRATEGY_REGISTRY`.
```python
from sat_com_connectivity import register_ground_to_space_connectivity_strategy

@register_ground_to_space_connectivity_strategy
class DummyTestStrategy(GroundToSpaceConnectionStrategy):
    strategy_name = "dummy_test_strategy"

    def compute_ground_object_connection_strategy(self, ground_object, satellites):
        pass  # your implementation here
```

### GroundToSpaceConnectionStrategies explained
- **GroundToSpaceConnectionStrategy**: Base class for all ground to space connection strategies.
- **ConnectToBestAngleUntilDisconnectionStrategy**: Connects to the satellite with the best angle until disconnection. Name: **best-angle-until-disconnection**.
- **ConnectToEverythingVisibleStrategy**: Connects to all visible satellites. Name: **everything-visible**.
- **ConnectToTheBestAngleStrategy**: Connects to the satellite with the best angle (Handover each time a best angle satellite is found). Name: **best-angle**.

Every strategy above decides visibility from the elevation angle. The
ground-to-satellite distance (`distance_km` on the link) is the straight-line
distance computed with that elevation, from the same vector: it is not computed
a second time.

#### Deprecated strategies
These decide visibility from the ground distance only and ignore the elevation
angle. They emit a `FutureWarning` on first use and will be removed.
- **everything-in-range** (ConnectToEverythingInRangeStrategy): use **everything-visible**.
- **best-range-until-disconnection** (ConnectToBestRangeUntilDisconnectionStrategy): use **best-angle-until-disconnection**.
- **best-range-until-disconnection-ordered** (ConnectToBestRangeUntilDisconnectionStrategyOrdered): use **best-angle-until-disconnection-ordered**.

## Inter-Satellite Link Connectivity
Optical inter-satellite links (OISL) are computed by two components:
- **Addressing plans** (`addressing_plans.py`): one per shell, they describe which
  satellite connects to which (the grid) and on which terminal.
- **Strategies** (`strategies.py`): they call the plans, manage the links that span
  several shells, and return the new / updated / obsolete links to the manager.

### Optical link model: basic (default) or advanced
Selected by `SimulationProperty.optical_inter_satellite_link_model`
(`sat_com_model.models.OpticalInterSatelliteLinkModel`), given to every addressing plan.

| | `basic` (default) | `advanced` |
|---|---|---|
| Terminal choice | once, from the terminals orientations only: forward ↔ backward for orbital links, any free inter-plane terminal for adjacent links | from the geometry, checked against the terminals configuration |
| Optical constraints | `None` by design | computed every tick |
| Links dropped for geometry | never | yes, when a constraint breaks |

In the basic model the terminals are only connection slots: their pointing
configuration is not used. Each `LinkAssociation` returned by a plan or a strategy
records its model (`optical_link_model`), and the manager refuses an `advanced`
link without constraints.

### Addressing plans
Built from the shell configuration (`AvailableAddressingPlans`):

| Name | Plan | Shell |
|---|---|---|
| `FULL_MESH_WALKER_DELTA` | 4 ISL: 2 orbital + 2 adjacent per satellite | Walker Delta |
| `FULL_MESH_WALKER_STAR` | 4 ISL, no link across the seam (3 for the planes bordering it) | Walker Star |
| `CHECKERBOARD_WALKER_DELTA` | 3 ISL: 2 orbital + 1 adjacent per satellite | Walker Delta (even planes and satellites per plane) |
| `CHECKERBOARD_WALKER_STAR` | 3 ISL, no link across the seam (2 for the planes bordering it) | Walker Star |
| `LINKED_SSO` | orbital ring | Dawn-dusk SSO |
| `EMPTY` | no ISL | Walker |

```python
plan = AvailableAddressingPlans.FULL_MESH_WALKER_DELTA.build(
    walker_shell=shell,
    optical_link_model=OpticalInterSatelliteLinkModel.ADVANCED,  # default: BASIC
)
associations = plan.get_link_associations(shell_satellites, state_cache=state_cache)
```

### Strategies
| Strategy | Type | Optical metrics |
|---|---|---|
| **IntraShellStaticConnectivity** | `intra-shell-static-connectivity` | none of its own: the plans follow the simulation model |
| **InterShellSSOPriorityConnectivity** | `inter-shell-sso-priority` | always computed for the inter-shell links |

A strategy that needs the optical metrics declares `requires_oisl_metrics = True`
and computes them for the links it manages, whatever the simulation model.
`InterShellSSOPriorityConnectivity` works in two phases:
1. Inter-shell: existing inter-shell links are checked (and kept for a short
   tolerance window when temporarily unavailable), then free inter-shell capable
   terminals of the SSO and Walker shells are paired.
2. Intra-shell: every shell addressing plan is applied. An association whose
   terminal was booked in phase 1 is dropped: the strategy has the last word.

Both strategies take the simulation `state_cache`; the configuration manager gives
them `manager.satellite_state_cache`:
```python
strategy = InterShellSSOPriorityConnectivity(
    satellites=manager.get_satellites(),
    shell_and_plans=manager.shell_addressing_plans,
    state_cache=manager.satellite_state_cache,
)
```
