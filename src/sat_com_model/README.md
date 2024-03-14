# sat_com_model Package

## Description
This package is the python model of the Topology. It features basics specification of the topology.

A topology is a set of object that will exchange data through links. Each object is a 
**SpatialPoint**, it must have a real position in the topology, but you're defining this position
is not mandatory (you can have a virtual topology and never use position).
A **SpatialPoint** have a **SpatialPosition**: this is the coordinates system (longitude, latitude, altitude).
Altitude isn't defined, it can be km or meter, it will depend on your implementation.

#### **TopologyObject** is a subclass of **SpatialPoint**. TopologyObject has children:
- OrbitalObject: Object that are in orbit, **Satellite** (TelecomSatellite), space station, telescope, etc.
  - **Satellite** 🛰: Space router that can connect to ground station, user terminal and other **Satellite**s
- **GroundStation**📡: Station connected to the constellation and to the internet backbones
- **UserTerminal**📻: Individual User connected to the constellation by a terminal (**Satellite** dish, phone, etc.)'

#### Each topology object can connect through Links (**Link**)
- **Link** 🌐: Parent class, define every link
  - **InterSatelliteLink**: Link between two satellites
  - **GroundStationLink**: Link between a **GroundStation** and a **Satellite**
  - **UserTerminalLink**: link between a **UserTerminal** and a **Satellite**

_NB: Today, those links are bidirectional. Attributes source and destination aren't relevant._

#### The **Simulation**
The Simulation is an object that will regroup every information about a topology simulation:
- Topology objects
- Links
- names and indexes
**A simulation will attribute an uniq identifier for every TopologyObject, therefore it is easy to manage
- the simulation and view the result.** 
---
Todo:
- update object types, we should use snake_case instead of CamelCase
- Think about distances, links length, etc.
- Create a visual diagram