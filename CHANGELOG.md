# Changelog

All notable changes of satComTopology. Versions follow `pyproject.toml`.

## SatComTopology V5: emulator integration, SSO shells and optical links
**5.0.3, unreleased**

V5 makes satComTopology the topology engine of an emulator: you inject your own
classes and your own events, and the simulation pushes every change of the network
to you. It also brings dawn-dusk SSO shells, optical inter-satellite links with
their terminals, inter-shell links, and a much faster tick.

### Highlights
- **Emulator integration**: event bus, event factories and topology object factories,
  injected in the configuration manager. Tutorial: README, *How to use satComTopology in my emulator*.
- **New constellations and links**: dawn-dusk SSO shells, static addressing plans,
  optical terminals, inter-shell links.
- **Elevation-based ground connectivity**, with link duration and disconnection time.
- **Performance**: satellite state computed once per tick, batched ground links,
  optimized optical links. Optical metrics are opt-in. See [docs/performance](docs/performance/README.md).
- **NetworkX export**: link length always exported, lighter graph, optional full model.

### Added
#### Emulator integration
- **Event bus** (`EventBus`): `async` handlers subscribed per `EventType`. The simulation
  publishes `ISL_*`, `GSL_*`, `UTL_*` and topology object (`TO_*`) events on create /
  update / remove, during the load and at each tick. Events carry `sim_time`.
- **Event factories** (`EventFactories`): replace `isl_event_factory`, `gsl_event_factory`,
  `utl_event_factory` or `topology_object_event_factory` to publish your own event classes.
- **Topology object factories** (`TopologyObjectFactories`): replace `satellite_factory`,
  `ground_station_factory`, `user_terminal_factory` or `point_of_presence_factory` to build
  your own `Satellite` / `GroundStation` / `UserTerminal` / `PointOfPresence` subclasses.
  Abstract factories in `sat_com_model.factories`, defaults in `sat_com_builder.factories`.
- `BaseConfigurationManager` and `YamlConfigurationManager` accept `event_bus`,
  `event_factories` and `topology_object_factories`.
- Ground link events (`GSL_*`, `UTL_*`) carry `distance_km`, `elevation_angle`,
  `estimated_duration` (remaining time, refreshed at each update) and
  `estimated_disconnection_time` (absolute).

#### Constellations
- **Dawn-dusk sun-synchronous shells** (`dawn_dusk_sso_shells`): altitude, number of
  satellites, epoch (defaults to the simulation start).
- **Static addressing plans** per shell (`static_addressing_plan`):
  `CHECKERBOARD_WALKER_DELTA`, `CHECKERBOARD_WALKER_STAR`, `FULL_MESH_WALKER_DELTA`,
  `FULL_MESH_WALKER_STAR` (Walker default), `LINKED_SSO` (SSO default).
- Walker shell `type` is validated (`delta`, `star`).

#### Optical inter-satellite links
- **Optical terminals** per satellite, configured per shell
  (`satellite_property.optical_inter_satellite_link_installations`): mounting azimuth /
  elevation, descriptor, allowed orientations, and terminal limits (range, angular
  velocity, azimuth / elevation range, minimum contact duration, line of sight).
- **Optical link model** (`optical_inter_satellite_link_model`):
  - `basic` (default): links follow the addressing plans, only the distance is computed.
  - `advanced`: every link is checked against its terminals and carries azimuth,
    relative azimuth, elevation, angular velocity, range rate, line-of-sight minimum
    altitude (with atmosphere), estimated duration, and recovery time when it is
    temporarily unavailable.
- **ISL connection strategies** (`inter_satellite_link_connection_strategy`):
  `intra-shell-static-connectivity` (default) and `inter-shell-sso-priority`, which first
  assigns the inter-shell terminals, then each shell's addressing plan.
- ISL `direction`: `ORBITAL`, `ADJACENT`, `INTER_SHELL`.

#### Ground connectivity
- Elevation-based strategies: `best-angle`, `best-angle-ordered`,
  `best-angle-until-disconnection`, `best-angle-until-disconnection-ordered`,
  `best-angle-until-disconnection-prefer-bigger-shell`,
  `best-angle-until-disconnection-prefer-lower-shell`, `everything-visible`.
- Custom strategies through `GROUND_TO_SPACE_CONNECTION_STRATEGY_REGISTRY`.
- `shells_whitelist` per set of ground objects, and `maximum_connected_satellites`.
- **Points of presence** as a ground object type.
- **Inline ground objects** (`ground_objects`): ground objects written in the
  configuration, instead of or in addition to a `data_file`.

#### Tooling and documentation
- Benchmark script `tests/performance_scripts/benchmark_constellations.py`, generating
  [docs/performance](docs/performance/README.md) (Starlink G2, Starlink G7, OneWeb,
  Starlink G2 + SSO; basic and advanced models).
- JSON configuration examples with every V5 option
  (`src/sat_com_builder/examples/*.json`).
- Tutorials: emulator integration (main README), topology object factories
  (`sat_com_builder`), event factories (`sat_com_application`).
- Cesium: inter-shell link color, filtered ISLs.

### Changed
- **NetworkX export**:
  - every edge has `distance_km` (straight-line 3D distance computed by the simulation);
  - the default graph is lighter: nodes carry `type`, `object_id`, `topology_uniq_id`
    (+ `name`, `shell_id`, `orbital_phase` for satellites, `label`, `ground_domain` for
    ground objects); edges carry `type`, `source_id`, `destination_id`, `distance_km`,
    and the ISL `direction`;
  - the full model is optional (`export_model_data=True`), under `model_data`;
  - new option `export_grid_coordinates` (orbit plane / satellite number).
- 3D distances are in **kilometers** (`get_3d_distance_km`), no longer meters.
- The ground link duration is estimated in batch, only when a link is created; the
  remaining duration is refreshed at each update.
- `data_file` is optional on a ground object set (`data_file`, `ground_objects` or both).
- Satellites are created with their movement model (`create_satellite(..., movement_model)`).
- Configuration enum values (`static_addressing_plan`, terminal orientations, shell type)
  are case-insensitive.

### Deprecated
These still work, and will be removed in a future version:
- Distance-based ground strategies (`everything-in-range`, `best-range-until-disconnection`,
  `best-range-until-disconnection-ordered`): they ignore the elevation angle. Use an
  elevation-based strategy (`FutureWarning`).
- NetworkX `export_link_length`: the distance is always exported (`FutureWarning`).
- `shell_white_lists`: renamed `shells_whitelist` (`FutureWarning`). When both are set,
  `shell_white_lists` is ignored.
- `create_satellite`, `create_ground_station`, `create_user_terminal` and
  `create_point_of_presence` in `sat_com_model.models` (`DeprecationWarning`): use the
  factories.

### Removed
- `static_ground_station_link_mode` (connected every satellite to every ground object),
  with `connect_every_satellite_with_every_ground_stations`,
  `connect_every_satellite_with_every_ground_stations_and_disable_un_connected` and
  `connect_every_satellite_with_every_user_terminals_and_disable_un_connected`.
- Never-used `orbital_connectivity_property` parameters: `maximum_inter_satellite_count`,
  `maximum_inter_satellite_range_distance`, `maximum_ground_station_range`,
  `maximum_user_terminal_range`.

  A configuration that still sets one of them loads: the parameter is ignored with a
  `FutureWarning` (`Parameter X was never used and will be removed`).
- `configure_access_to_group_packages.sh`.

### Fixed
- Inter-shell strategy: when the satellite at one end of an inter-shell link removed it, the terminal at the
  other end was skipped for the tick instead of freed, so it stayed unlinked for one tick at every handover.
- Optical constraints were reversed by the ISL update.
- Wrong constraint used for terminal B.
- Angular velocity was dropped from the ISL metrics.
- The adjacent ISL shift (`adjacent_inter_satellite_shifting`) was not passed to the builder.
- Minimum elevation was not taken from the ground object domain, which broke elevations below 10°.
- Distances computed from tuples instead of spatial positions.
- Ground links were only computed for Walker satellites (SSO satellites were ignored).
- A simulation manager function returned a set instead of a list.
- YAML configuration manager and Cesium formatter errors; Cesium link width could not be changed.
- Loading points of presence from a file crashed.
- A `Satellite` (or other topology object) subclass defined outside `sat_com_model`
  failed at creation (unresolved `Link` forward reference).
- YAML examples did not load (trailing commas).
- The full model in the NetworkX node data broke some NetworkX operations
  (now under `model_data`).

### Performance
- Satellite positions are computed **once per tick** and shared by every connectivity
  computation: ground links, ISLs, every shell (`satellite_state_cache`).
- Ground links: batched computation, sets instead of lists, link duration only
  estimated at creation.
- Optical links: faster link creation, optimized constraint checks, faster addressing
  plan initialisation.
- Optical metrics are only computed with the `advanced` model (or for inter-shell links).

Mean tick on one core, 100 ground stations, 60 s ticks:

| Constellation | Satellites | Load | Tick, basic | Tick, advanced |
|---|---|---|---|---|
| Starlink G2 | 720 | 0.28 s | 0.15 s | 0.37 s |
| Starlink G7 | 3,360 | 1.17 s | 0.78 s | 1.62 s |
| OneWeb | 588 | 0.24 s | 0.13 s | 0.30 s |
| Starlink G2 + SSO | 801 | 0.37 s | 0.20 s | 0.49 s |

### Upgrading from V4
- **Old configurations keep loading.** Removed parameters are ignored with a warning;
  check your logs for `FutureWarning`.
- Replace distance-based ground strategies with an elevation-based one
  (`best-range-until-disconnection` → `best-angle-until-disconnection`).
- Rename `shell_white_lists` to `shells_whitelist`.
- 3D distances are now in kilometers: check code that used the meter values.
- NetworkX: the graph no longer contains the full model. Add `export_model_data=True` if
  you read it, and read it under `model_data`. Drop `export_link_length`.
- Replace `sat_com_model.models.create_*` with the factories of `sat_com_builder.factories`.
- The ISL behavior of V4 is the `basic` model, which is the default: nothing to change.

## SatComTopology V4.2 : Connectivity strategies
We can change implement new connection strategies for ground-to-space connectivity.

## SatComTopology V4: Multi shell constellations
### Major changes
#### Sat Com Topology Simulation
- Possibility to directly create whole constellation from the configuration (SATGPT4 implemented) (Implemented)
- Possibility to create  sets of ground objects (Implemented)
  - Suppression of User Terminal (on going)
  - Each ground object set can have networks parameters
    - Physical parameters (link length, white list, etc.) (implemented, except for white-list)
    - Network parameters (link capacity ) (on going)
    - Movement model (allowing to have maritime user and roaming users)
#### Sat Com Topology X Cesium (not started yet)
- Possibility to make advanced personalisation
  - Shell colors 
  - Ascending / descending colors
  - Links colors 
  - Optimizing performances
### Minors Changes
#### Optimization
- Replace list by sets
  - Implement equals / hash methods
