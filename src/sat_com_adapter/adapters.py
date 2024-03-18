import datetime
import json
import os

import networkx as nx
from networkx.readwrite import json_graph

from sat_com_adapter.cesium_renderer.cesium_renderer import CesiumRenderer
from sat_com_adapter.networkx_builder.networkx_builder import NetworkxBuilder
from sat_com_application.simulation_manager import SimulationManager


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
    networkx_builder: NetworkxBuilder

    def __init__(
        self, simulation_manager: SimulationManager, output_directory: str = None
    ):
        self.simulation_manager = simulation_manager
        self.output_directory = output_directory

    def set_networkx_builder(self, networkx_builder: NetworkxBuilder):
        self.networkx_builder = networkx_builder

    def create_full_networkx_graph(
        self, export_link_length: bool = False, export_object_position: bool = False
    ) -> nx.Graph:
        """
        Return the networkx graph of the simulation.
        :param export_link_length: if true the link length will be added to data
        :param export_object_position: if true the object position will be exported to data
        :return: nx.Graph containing the simulation
        """
        self.networkx_builder = NetworkxBuilder(
            simulation_manager=self.simulation_manager,
            export_link_length=export_link_length,
            export_positions=export_object_position,
        )

        self.networkx_builder.add_topology_objects()
        self.networkx_builder.add_links()

        return self.networkx_builder.build()

    def adapt(self):
        """
        Create the networkX as a JSON file.
        A default networkx graph will be created if the method get_networkx_graph() isn't previously called
        :return:
        """
        if self.output_directory is None:
            raise Exception("No output directory provided")

        export_date = datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")

        if self.networkx_builder is None:
            self.create_full_networkx_graph()

        output_export_name = "{}-{}-{}.json".format(
            self.simulation_manager.simulation.simulation_name, "networkx", export_date
        )

        if not os.path.exists(self.output_directory):
            os.makedirs(self.output_directory)

        output_path = os.path.join(self.output_directory, output_export_name)
        with open(output_path, "w") as file:
            file.write(
                json.dumps(json_graph.node_link_data(self.networkx_builder.build()))
            )


class CesiumAdapter(Adapter):
    """
    Cesium Adapter is an adapter that will create a Cesium Html page using CesiumJS library.
    CesiumRender can be used separately. This adapter implement some useful building method.
    """

    output_directory: str
    simulation_manager: SimulationManager
    cesium_renderer: CesiumRenderer
    cesium_token: str

    def __init__(
        self,
        simulation_manager: SimulationManager,
        output_directory: str = None,
    ):
        self.simulation_manager = simulation_manager
        self.output_directory = output_directory

    def create_cesium_renderer(self, cesium_token: str = str()):
        """
        Create a cesium renderer if you don't want to create a custom one.
        :param cesium_token: Cesium Token, mandatory to watch the result, but not mandatory to generate the code
        :return: CesiumRenderer instance
        """
        self.cesium_token = cesium_token
        return CesiumRenderer(self.simulation_manager, self.cesium_token)

    def set_custom_renderer(self, cesium_renderer: CesiumRenderer):
        """
        Set custom renderer if you created your own.
        :param cesium_renderer:
        :return:
        """
        self.cesium_renderer = cesium_renderer

    def build_renderer_simulation_without_links(self, cesium_token: str = str()) -> str:
        """
        Build a CesiumRenderer without any topology link.
        :param cesium_token: Cesium token
        :return: Html code in string format
        """
        self.cesium_renderer = self.create_cesium_renderer(cesium_token)

        self.cesium_renderer.add_topology_objects()

        return self.cesium_renderer.render()

    def build_renderer_simulation_with_links(self, cesium_token: str = str()) -> str:
        """
        Build a CesiumRenderer with topology links.
        :param cesium_token: Cesium token
        :return: Html code in string format
        """
        self.cesium_renderer = self.create_cesium_renderer(cesium_token)

        self.cesium_renderer.add_topology_objects()
        self.cesium_renderer.add_links()

        return self.cesium_renderer.render()

    def build_renderer_with_routes(
        self, topology_object_list_id: list[int], cesium_token: str = str(), **kwargs
    ) -> str:
        """
        Build a CesiumRenderer with routes.
        Todo: We shoudld replace int list by TopologyObject list...
        :param topology_object_list_id: List of topology object id
        :param cesium_token: Your Cesium token
        :param kwargs: What you want to display (ground_stations: bool, satellites:bool, user_terminals:bool, etc)
        :return: Html code in string format
        """
        self.cesium_renderer = self.create_cesium_renderer(cesium_token)

        if "ground_stations" in kwargs and kwargs["ground_stations"] is True:
            self.cesium_renderer.add_ground_stations()

        if "satellites" in kwargs and kwargs["satellites"] is True:
            self.cesium_renderer.add_satellites()

        if "user_terminals" in kwargs and kwargs["user_terminals"] is True:
            self.cesium_renderer.add_terminal_users()

        if "user_terminals_links" in kwargs and kwargs["user_terminals_links"] is True:
            self.cesium_renderer.add_user_terminal_links()

        if (
            "inter_satellite_links" in kwargs
            and kwargs["inter_satellite_links"] is True
        ):
            self.cesium_renderer.add_inter_satellite_links()

        if (
            "ground_stations_links" in kwargs
            and kwargs["ground_stations_links"] is True
        ):
            self.cesium_renderer.add_ground_stations()

        path = self.simulation_manager.reconstruct_path(topology_object_list_id)

        self.cesium_renderer.add_all_routes_from_links(path)

        return self.cesium_renderer.render()

    def adapt(self):
        if self.output_directory is None:
            raise Exception("No output directory provided")

        export_date = datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")

        output_export_name = "{}-{}-{}.html".format(
            self.simulation_manager.simulation.simulation_name,
            "cesium_output",
            export_date,
        )

        if not os.path.exists(self.output_directory):
            os.makedirs(self.output_directory)

        output_path = os.path.join(self.output_directory, output_export_name)
        with open(output_path, "w") as file:
            if self.cesium_renderer is None:
                raise Exception(
                    "Cesium Renderer not defined, you should be your render first"
                )
            file.write(self.cesium_renderer.render())
