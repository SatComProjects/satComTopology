import datetime
import json
import os

import networkx as nx
from networkx.readwrite import json_graph

from sat_com_application.simulation_manager import SimulationManager
from sat_com_model.models import InterSatelliteLink


class Adapter:
    def adapt(self):
        """
        Create the output compatible with the implemented format
        :return:
        """
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

    def get_networkx_graph(
        self, export_link_length: bool = False, export_object_position: bool = False
    ) -> nx.Graph:
        """
        Return the networkx graph of the simulation.
        Todo:
            - Should be refactored
            - Improve data builder, maybe using **kwargs
        :param export_link_length: if true the link length will be added to data
        :param export_object_position: if true the object position will be exported to data
        :return: nx.Graph containing the simulation
        """
        G = nx.Graph()
        for topology_object in self.simulation_manager.get_all_topology_objects():
            data = dict()

            data.update(type=topology_object.get_type())

            if export_object_position:
                position = topology_object.get_coordinates()
                data.update(
                    position={
                        "longitude": position.longitude,
                        "latitude": position.latitude,
                        "altitude": position.altitude,
                    }
                )

            G.add_node(topology_object.topology_uniq_id, **data)

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
        """
        /!\\ todo: Rework the get_net_work_x_graph system
        :return:
        """
        if self.output_directory is None:
            raise Exception("No output directory provided")

        export_date = datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")

        G = self.get_networkx_graph()

        output_export_name = "{}-{}-{}.json".format(
            self.simulation_manager.simulation.simulation_name, "networkx", export_date
        )

        if not os.path.exists(self.output_directory):
            os.makedirs(self.output_directory)

        output_path = os.path.join(self.output_directory, output_export_name)
        with open(output_path, "w") as file:
            file.write(json.dumps(json_graph.node_link_data(G)))
