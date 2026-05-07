import networkx as nx

from sat_com_application.simulation_manager import SimulationManager
from sat_com_model.models import TopologyObject, Link, Satellite
from sat_com_trajectopy.grid_mesh_calculator import calculate_satellite_mesh_coordinates


class NetworkxBuilder:
    simulation_manager: SimulationManager
    graph: nx.Graph

    enable_export_positions: bool
    enable_export_link_length: bool

    def __init__(self, simulation_manager: SimulationManager, **kwargs):
        """
        Create a Networkx Builder.
        :param simulation_manager:
        :param kwargs:
            :arg export_positions: Enable export the satellite position
            :arg export_link_length: Enable export the satellite link length (ground distance between links)
            :arg enable_export_flows_data: Enable the export of the flow metric
            :arg export_grid_coordinates: Enable the export of the grid coordinates for walker shells
        """
        self.simulation_manager = simulation_manager
        simulation_date_as_str = simulation_manager.time_manager.current_time.strftime(
            "%Y-%m-%d %H:%M:%S.%f"
        )[:-3]

        simulation_configuration = simulation_manager.configuration
        self.graph = nx.Graph(
            current_simulation_date=simulation_date_as_str,
            simulation_configuration=simulation_configuration,
        )

        self.enable_export_positions = kwargs.get("export_positions", False)

        self.enable_export_link_length = kwargs.get("export_link_length", False)

        self.enable_export_flows_data = kwargs.get("enable_export_flows_data", False)

        self.enable_export_grid_coordinates = kwargs.get(
            "export_grid_coordinates", False
        )

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

        if self.enable_export_grid_coordinates and isinstance(
            topology_object, Satellite
        ):
            coordinates_on_grid = calculate_satellite_mesh_coordinates(
                topology_object.object_id,
                topology_object.walker_shell.amount_of_orbit_plane,
                topology_object.walker_shell.amount_of_satellite_per_orbit_plane,
                topology_object.walker_shell.adjacent_inter_satellite_shifting,
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

        if export link length is exported, the distance meter will be exported, accessible from the
        key "distance"
        if used_capacity_between_previous_and_last_hop is enabled the unidirectional used capacity
        will be exported, accessible from the key "used_capacity_between_previous_and_last_hop", with the
        following structure:
        For link with source=1 and destination=2:
        The Key will always be the first node from the edge.
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

        data.update(type=link.type)

        if self.enable_export_link_length:
            distance = self.simulation_manager.simulation.get_distance_model().get_3d_distance_meters(
                source.spatial_position, destination.spatial_position
            )
            data.update(distance=distance)

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
            data = dict()
            data.update(
                orbital_phase=(
                    "ascending" if satellite.is_ascending() else "descending"
                )
            )
            self.add_topology_object(satellite, data)

        return self

    def add_ground_stations(self) -> "NetworkxBuilder":
        """
        Add Ground Stations to the Networkx Builder.
        :return: Networkx Builder instance.
        """
        for ground_station in self.simulation_manager.get_ground_stations():
            data = dict()
            data.update(label=ground_station.label)
            self.add_topology_object(ground_station, data)

        return self

    def add_user_terminals(self) -> "NetworkxBuilder":
        """
        Add User Terminals to the Networkx Builder.
        :return: Networkx Builder instance.
        """
        for user_terminal in self.simulation_manager.get_user_terminals():
            data = dict()
            data.update(label=user_terminal.label)

            self.add_topology_object(user_terminal, data)

        return self

    def add_point_of_presences(self) -> "NetworkxBuilder":
        """
        Add Point of Presences to the Networkx Builder.
        :return: Networkx Builder instance.
        """
        for point_of_presence in self.simulation_manager.get_point_of_presences():
            data = dict()
            data.update(label=point_of_presence.label)
            self.add_topology_object(point_of_presence, data)

        return self

    def add_ground_station_links(self, without_disabled=False) -> "NetworkxBuilder":
        """
        Add Ground Station Links to the Networkx Builder.
        :return: Networkx Builder instance.
        """
        for ground_station_link in self.simulation_manager.get_ground_stations_links():

            if not without_disabled or (
                without_disabled and not ground_station_link.disabled
            ):
                self.add_link(
                    ground_station_link, {"disabled": ground_station_link.disabled}
                )

        return self

    def add_user_terminal_links(self) -> "NetworkxBuilder":
        """
        Add User Terminal Links to the Networkx Builder.
        :return: Networkx Builder instance.
        """
        for user_terminal_link in self.simulation_manager.get_user_terminal_links():
            self.add_link(user_terminal_link, {})

        return self

    def add_inter_satellite_links(self) -> "NetworkxBuilder":
        """
        Add Inter Satellite Links to the Networkx Builder.
        :return: Networkx Builder instance.
        """
        for (
            inter_satellite_link
        ) in self.simulation_manager.get_inter_satellites_links():
            data = dict()
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
            self.add_link(static_ground_object_link, {})

        return self

    def add_topology_objects(self) -> "NetworkxBuilder":
        """
        Add Topology Objects to the Networkx Builder.
        :return: Networkx Builder instance.
        """
        self.add_satellites()
        self.add_ground_stations()
        self.add_user_terminals()

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
