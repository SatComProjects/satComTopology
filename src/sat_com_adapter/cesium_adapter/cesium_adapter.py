import os

from sat_com_adapter.adapters import Adapter
from sat_com_adapter.cesium_adapter.cesium_renderer import CesiumRenderer
from sat_com_application.simulation_manager import SimulationManager
import datetime

from sat_com_model.models import TopologyObject


class CesiumAdapter(Adapter):
    output_directory: str
    simulation_manager: SimulationManager
    cesium_renderer: CesiumRenderer

    def __init__(
        self, simulation_manager: SimulationManager, output_directory: str = None
    ):
        self.simulation = simulation_manager
        self.output_directory = output_directory

    def set_custom_renderer(self, cesium_renderer: CesiumRenderer):
        self.cesium_renderer = cesium_renderer

    def build_renderer_simulation_without_links(self) -> str:
        self.cesium_renderer = CesiumRenderer(self.simulation_manager)

        self.cesium_renderer.add_topology_objects()

        return self.cesium_renderer.render()

    def build_renderer_simulation_with_links(self) -> str:
        self.cesium_renderer = CesiumRenderer(self.simulation_manager)

        self.cesium_renderer.add_topology_objects()
        self.cesium_renderer.add_links()

        return self.cesium_renderer.render()

    def build_renderer_with_routes(
        self, topology_object_list: list[TopologyObject], **kwargs
    ) -> str:
        self.cesium_renderer = CesiumRenderer(self.simulation_manager)

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

        # Todo: Add routing part

        return self.cesium_renderer.render()

    def adapt(self):
        if self.output_directory is None:
            raise Exception("No output directory provided")

        export_date = datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")

        output_export_name = "{}-{}-{}".format(
            self.simulation_manager.simulation.simulation_name,
            "cesium_output",
            export_date,
        )
        output_path = os.path.join(self.output_directory, output_export_name)

        if not os.path.exists(output_path):
            os.makedirs(output_path)

        output_path = os.path.join(output_path, "topology.html")
        with open(output_path, "w") as file:
            if self.cesium_renderer is None:
                raise Exception(
                    "Cesium Renderer not defined, you should be your render first"
                )
            file.write(self.cesium_renderer.render())
