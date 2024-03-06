import datetime
import json
import os

import networkx as nx
from networkx.readwrite import json_graph

from sat_com_application.simulation_manager import SimulationManager
from sat_com_model.models import InterSatelliteLink


class Adapter:
    def adapt(self):
        pass


class NetworkXAdapter(Adapter):
    simulation_manager: SimulationManager
    output_directory: str
    G: nx.Graph

    def __init__(
        self, simulation_manager: SimulationManager, output_directory: str = None
    ):
        self.simulation_manager = simulation_manager
        self.output_directory = output_directory

    def get_networkx_graph(self, export_link_length: bool = False) -> nx.Graph:
        G = nx.Graph()
        for topology_object in self.simulation_manager.get_all_topology_objects():
            G.add_node(
                topology_object.topology_uniq_id, type=topology_object.get_type()
            )

        for link in self.simulation_manager.get_all_links():
            source = link.source
            destination = link.destination

            data = {}

            data.update(type=link.type)

            if export_link_length:
                distance = self.simulation_manager.simulation.get_distance_model().get_distance_meters(
                    source.spatial_position, destination.spatial_position
                )
                data.update(distance=distance)

            if isinstance(link, InterSatelliteLink):
                data.update(direction=link.inter_satellite_direction.name)

            G.add_edge(source.topology_uniq_id, destination.topology_uniq_id, **data)

        return G

    def adapt(self):
        if self.output_directory is None:
            raise Exception("No output directory provided")

        export_date = datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        G = self.get_networkx_graph()
        output_export_name = "{}-{}-{}".format(
            self.simulation_manager.simulation.simulation_name, "networkx", export_date
        )
        output_path = os.path.join(self.output_directory, output_export_name)

        if not os.path.exists(output_path):
            os.makedirs(output_path)

        output_path = os.path.join(output_path, "topology.json")
        with open(output_path, "w") as file:
            file.write(json.dumps(json_graph.node_link_data(G)))
