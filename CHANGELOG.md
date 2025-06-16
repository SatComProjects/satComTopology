# SatComTopology V4.2 : Connectivity strategies
We can change implement new connection strategies for ground-to-space connectivity.

# SatComTopology V4: Multi shell constellations
## Major changes
### Sat Com Topology Simulation
- Possibility to directly create whole constellation from the configuration (SATGPT4 implemented) (Implemented)
- Possibility to create  sets of ground objects (Implemented)
  - Suppression of User Terminal (on going)
  - Each ground object set can have networks parameters
    - Physical parameters (link length, white list, etc.) (implemented, except for white-list)
    - Network parameters (link capacity ) (on going)
    - Movement model (allowing to have maritime user and roaming users)
### Sat Com Topology X Cesium (not started yet)
- Possibility to make advanced personalisation
  - Shell colors 
  - Ascending / descending colors
  - Links colors 
  - Optimizing performances
## Minors Changes
### Optimization
- Replace list by sets
  - Implement equals / hash methods