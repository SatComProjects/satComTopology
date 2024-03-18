import networkx as nx

from sat_com_application.simulation_manager import SimulationManager
from sat_com_model.models import TopologyObject, Link


class NetworkxBuilder:
    simulation_manager: SimulationManager
    graph: nx.Graph

    enable_export_positions: bool
    enable_export_link_length: bool

    def __init__(self, simulation_manager: SimulationManager, **kwargs):
        self.simulation_manager = simulation_manager
        self.graph = nx.Graph()

        self.enable_export_positions = kwargs.get("export_positions", False)

        self.enable_export_link_length = kwargs.get("export_link_length", False)

    def add_topology_object(
        self, topology_object: TopologyObject, data: dict = {}
    ) -> "NetworkxBuilder":
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
            type=topology_object.get_type(), object_id=topology_object.object_id
        )

        self.graph.add_node(topology_object.topology_uniq_id, **data)

        return self

    def add_link(self, link: Link, data: dict = {}) -> "NetworkxBuilder":
        source = link.source
        destination = link.destination

        data.update(type=link.type)

        if self.enable_export_link_length:
            distance = self.simulation_manager.simulation.get_distance_model().get_distance_meters(
                source.spatial_position, destination.spatial_position
            )
            data.update(distance=distance)

        self.graph.add_edge(
            source.topology_uniq_id, destination.topology_uniq_id, **data
        )

        return self

    def add_satellites(self) -> "NetworkxBuilder":
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
        for ground_station in self.simulation_manager.get_ground_stations():
            data = dict()
            data.update(city=ground_station.city)
            self.add_topology_object(ground_station, data)

        return self

    def add_user_terminals(self) -> "NetworkxBuilder":
        for user_terminal in self.simulation_manager.get_user_terminals():
            data = dict()
            data.update(user_name=user_terminal.user_name)

            self.add_topology_object(user_terminal, data)

        return self

    def add_ground_station_links(self) -> "NetworkxBuilder":
        for ground_station_link in self.simulation_manager.get_ground_stations_links():
            self.add_link(ground_station_link, {})

        return self

    def add_user_terminal_links(self) -> "NetworkxBuilder":
        for user_terminal_link in self.simulation_manager.get_user_terminal_links():
            self.add_link(user_terminal_link, {})

        return self

    def add_inter_satellite_links(self) -> "NetworkxBuilder":
        for (
            inter_satellite_link
        ) in self.simulation_manager.get_inter_satellites_links():
            data = dict()
            data.update(direction=inter_satellite_link.inter_satellite_direction.name)
            self.add_link(inter_satellite_link, data)

        return self

    def add_topology_objects(self) -> "NetworkxBuilder":
        self.add_satellites()
        self.add_ground_stations()
        self.add_user_terminals()

        return self

    def add_links(self) -> "NetworkxBuilder":
        self.add_inter_satellite_links()
        self.add_ground_station_links()
        self.add_user_terminal_links()

        return self

    def build(self) -> nx.Graph:
        return self.graph
