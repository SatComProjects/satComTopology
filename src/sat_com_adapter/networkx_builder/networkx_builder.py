"""
NetworkX graph of a simulation.

Default content, kept small so the graph stays light and easy to use:

- graph: `current_simulation_date`, `simulation_configuration`
- every node: `type`, `object_id`, `topology_uniq_id`, plus
  - satellite: `name`, `shell_id`, `orbital_phase`
  - ground station, user terminal, point of presence: `label`, `ground_domain`
- every edge: `type`, `source_id`, `destination_id`, `distance_km`, plus
  - inter-satellite link: `direction`

`source_id` / `destination_id` keep the link orientation (the graph is
undirected, and the `source` / `target` keys of a node-link export follow the
adjacency order, not the link). `distance_km` is the straight-line distance of
the link, computed by the simulation; when a link has none (ground-to-ground
links, static ground station mode), it is computed from both positions.

Options (constructor keyword arguments, all False by default):

- `export_positions`: node `position` (longitude, latitude, altitude)
- `export_grid_coordinates`: Walker satellites `orbit_plane_id` / `satellite_number`
- `enable_export_flows_data`: edge flow figures
- `export_model_data`: full pydantic dump of every node and edge, in `model_data`
"""

import warnings

import networkx as nx
import numpy as np

from sat_com_application.simulation_manager import SimulationManager
from sat_com_connectivity.utils import latitude_longitude_altitude_to_x_y_z
from sat_com_model.models import (
    TopologyObject,
    Link,
    Satellite,
    InterSatelliteLink,
    WalkerShell,
)
from sat_com_trajectopy.grid_mesh_calculator import calculate_satellite_mesh_coordinates


def link_distance_km(link: Link) -> float:
    """
    Distance of a link: the one computed by the simulation, or the straight-line
    distance between both positions when the link has none (None or -1).
    """
    if link.distance_km is not None and link.distance_km >= 0:
        return float(link.distance_km)

    source = latitude_longitude_altitude_to_x_y_z(
        *link.source.get_coordinates().to_latitude_longitude_altitude()
    )
    destination = latitude_longitude_altitude_to_x_y_z(
        *link.destination.get_coordinates().to_latitude_longitude_altitude()
    )
    return float(np.linalg.norm(np.subtract(source, destination))) / 1000.0


def _ground_domain(ground_object) -> str | None:
    domain = getattr(ground_object, "ground_object_domain", None)
    return domain.identifier if domain else None


class NetworkxBuilder:
    simulation_manager: SimulationManager
    graph: nx.Graph

    enable_export_positions: bool
    enable_export_grid_coordinates: bool
    enable_export_flows_data: bool
    enable_export_model_data: bool

    def __init__(self, simulation_manager: SimulationManager, **kwargs):
        """
        Create a Networkx Builder. See the module docstring for the graph content.
        :param simulation_manager:
        :param kwargs: all False by default
            :arg export_positions: export the node positions
            :arg export_grid_coordinates: export the grid coordinates of Walker satellites
            :arg enable_export_flows_data: export the flow figures of the links
            :arg export_model_data: export the full model of every node and edge
            :arg export_link_length: deprecated, the distance is always exported
        """
        self.simulation_manager = simulation_manager
        simulation_date_as_str = simulation_manager.time_manager.current_time.strftime(
            "%Y-%m-%d %H:%M:%S.%f"
        )[:-3]

        self.graph = nx.Graph(
            current_simulation_date=simulation_date_as_str,
            simulation_configuration=simulation_manager.configuration,
        )

        self.enable_export_positions = kwargs.get("export_positions", False)
        self.enable_export_grid_coordinates = kwargs.get(
            "export_grid_coordinates", False
        )
        self.enable_export_flows_data = kwargs.get("enable_export_flows_data", False)
        self.enable_export_model_data = kwargs.get("export_model_data", False)

        if "export_link_length" in kwargs:
            warnings.warn(
                "export_link_length is deprecated and ignored: every edge now has "
                "its distance in 'distance_km'.",
                FutureWarning,
                stacklevel=2,
            )

    def _model_data(self, model) -> dict:
        if not self.enable_export_model_data:
            return {}
        return {"model_data": model.model_dump(mode="json")}

    def add_topology_object(
        self, topology_object: TopologyObject, data: dict = None
    ) -> "NetworkxBuilder":
        """
        Add a TopologyObject to the Networkx Builder.
        :param topology_object: TopologyObject to be added.
        :param data: Dictionary of data to be added to the node.
        :return: Networkx Builder instance.
        """
        if data is None:
            data = dict()

        if self.enable_export_positions:
            position = topology_object.get_coordinates()
            data.update(
                position={
                    "longitude": position.longitude,
                    "latitude": position.latitude,
                    "altitude": position.altitude,
                }
            )
        data.update(
            type=topology_object.get_type(),
            object_id=topology_object.object_id,
            topology_uniq_id=topology_object.topology_uniq_id,
        )

        if (
            self.enable_export_grid_coordinates
            and isinstance(topology_object, Satellite)
            and isinstance(topology_object.shell, WalkerShell)
        ):
            coordinates_on_grid = calculate_satellite_mesh_coordinates(
                topology_object.object_id,
                topology_object.shell.amount_of_orbit_plane,
                topology_object.shell.amount_of_satellite_per_orbit_plane,
                topology_object.shell.adjacent_inter_satellite_shifting,
            )
            data.update(
                orbit_plane_id=coordinates_on_grid[0],
                satellite_number=coordinates_on_grid[1],
            )

        self.graph.add_node(topology_object.topology_uniq_id, **data)

        return self

    def add_link(self, link: Link, data: dict = None) -> "NetworkxBuilder":
        """
        Add a Link to the Networkx Builder.

        If enable_export_flows_data is enabled, the unidirectional used capacity
        is exported under "used_capacity_between_previous_and_last_hop", keyed by
        the first node of each direction. For a link with source=1 and destination=2:
        "used_capacity_between_previous_and_last_hop": {
             1: x, # for 1 -> 2
             2: y, # for 2 -> 1
        }
        :param link: Link to be added.
        :param data: Dictionary of data to be added to the edge.
        :return: Networkx Builder instance.
        """
        if data is None:
            data = dict()

        source = link.source
        destination = link.destination

        data.update(
            type=link.type,
            source_id=source.topology_uniq_id,
            destination_id=destination.topology_uniq_id,
            distance_km=link_distance_km(link),
        )

        if self.enable_export_flows_data:
            flows = dict()
            flows[source.topology_uniq_id] = (
                link.get_used_capacity_between_hops_unidirectional(
                    link.source, link.destination
                )
            )
            flows[destination.topology_uniq_id] = (
                link.get_used_capacity_between_hops_unidirectional(
                    link.destination, link.source
                )
            )
            data.update({"used_capacity_between_previous_and_last_hop": flows})
            data.update(
                {
                    "total_used_capacity_crossing_link": link.total_capacity_between_hops_bidirectional()
                }
            )
            data.update(
                {"unidirectional_link_maximum_capacity": link.link_maximum_capacity}
            )
        self.graph.add_edge(
            source.topology_uniq_id, destination.topology_uniq_id, **data
        )

        return self

    def add_satellites(self) -> "NetworkxBuilder":
        """
        Add Satellites to the Networkx Builder.
        :return: Networkx Builder instance.
        """
        for satellite in self.simulation_manager.get_satellites():
            data = self._model_data(satellite)
            data.update(
                name=satellite.satellite_name,
                orbital_phase=(
                    "ascending" if satellite.is_ascending() else "descending"
                ),
                shell_id=satellite.shell.identifier if satellite.shell else None,
            )
            self.add_topology_object(satellite, data)

        return self

    def _add_ground_objects(self, ground_objects) -> "NetworkxBuilder":
        for ground_object in ground_objects:
            data = self._model_data(ground_object)
            data.update(
                label=ground_object.label,
                ground_domain=_ground_domain(ground_object),
            )
            self.add_topology_object(ground_object, data)

        return self

    def add_ground_stations(self) -> "NetworkxBuilder":
        """
        Add Ground Stations to the Networkx Builder.
        :return: Networkx Builder instance.
        """
        return self._add_ground_objects(self.simulation_manager.get_ground_stations())

    def add_user_terminals(self) -> "NetworkxBuilder":
        """
        Add User Terminals to the Networkx Builder.
        :return: Networkx Builder instance.
        """
        return self._add_ground_objects(self.simulation_manager.get_user_terminals())

    def add_point_of_presences(self) -> "NetworkxBuilder":
        """
        Add Point of Presences to the Networkx Builder.
        :return: Networkx Builder instance.
        """
        return self._add_ground_objects(
            self.simulation_manager.get_point_of_presences()
        )

    def add_ground_station_links(self, without_disabled=False) -> "NetworkxBuilder":
        """
        Add Ground Station Links to the Networkx Builder.
        :param without_disabled: skip the disabled links (static ground station mode)
        :return: Networkx Builder instance.
        """
        for ground_station_link in self.simulation_manager.get_ground_stations_links():
            if without_disabled and ground_station_link.disabled:
                continue
            self.add_link(ground_station_link, self._model_data(ground_station_link))

        return self

    def add_user_terminal_links(self) -> "NetworkxBuilder":
        """
        Add User Terminal Links to the Networkx Builder.
        :return: Networkx Builder instance.
        """
        for user_terminal_link in self.simulation_manager.get_user_terminal_links():
            self.add_link(user_terminal_link, self._model_data(user_terminal_link))

        return self

    def add_inter_satellite_links(self) -> "NetworkxBuilder":
        """
        Add Inter Satellite Links to the Networkx Builder.
        :return: Networkx Builder instance.
        """
        for (
            inter_satellite_link
        ) in self.simulation_manager.get_inter_satellites_links():
            data = self._model_data(inter_satellite_link)
            data.update(direction=inter_satellite_link.inter_satellite_direction.name)
            self.add_link(inter_satellite_link, data)

        return self

    def add_static_ground_object_links(self) -> "NetworkxBuilder":
        """
        Add Static Ground Object Links to the Networkx Builder.
        :return: Networkx Builder instance.
        """
        for (
            static_ground_object_link
        ) in self.simulation_manager.get_static_ground_object_links():
            self.add_link(
                static_ground_object_link,
                self._model_data(static_ground_object_link),
            )

        return self

    def add_topology_objects(self) -> "NetworkxBuilder":
        """
        Add Topology Objects to the Networkx Builder.
        :return: Networkx Builder instance.
        """
        self.add_satellites()
        self.add_ground_stations()
        self.add_user_terminals()
        # Ground-to-ground links reach the points of presence: without this,
        # their nodes would be created by the edges, with no data.
        self.add_point_of_presences()

        return self

    def add_links(self) -> "NetworkxBuilder":
        """
        Add Links to the Networkx Builder.
        :return: Networkx Builder instance.
        """
        self.add_inter_satellite_links()
        self.add_ground_station_links()
        self.add_user_terminal_links()
        self.add_static_ground_object_links()

        return self

    def build(self) -> nx.Graph:
        """
        Return the graph
        Todo: Should implement a better builder system, the build method will be used to assemble the graph
        :return:
        """
        return self.graph
