from datetime import datetime

import yaml

from sat_com_application.simulation_manager import SimulationManager
from sat_com_builder.ground_stations.generate_ground_stations import (
    generate_ground_stations_from_file,
)
from sat_com_builder.links.ground_station_link_generator import (
    generate_ground_station_link_with_position,
)
from sat_com_builder.links.inter_satellite_link_generator import (
    create_inter_satellite_link_from_two_line_element,
)
from sat_com_builder.two_line_elements.generate_satellites_from_two_line_element_file import (
    generate_satellites_from_two_line_element,
)
from sat_com_builder.two_line_elements.two_line_element_file import (
    parse_two_line_element_to_instance,
    TwoLineElementFile,
)
from sat_com_model.models import Simulation
from sat_com_trajectopy.distance_models import GeopyDistanceModel
from sat_com_trajectopy.satellites.generate_satellite import (
    generate_satellites_from_two_line_elements_with_pyorbital_model,
)


class ConfigurationManager:
    def load_simulation(self) -> SimulationManager:
        pass


def generate_default_simulation_name():
    return "simulation_{date}".format(date=datetime.now().strftime("%Y%m%d-%H_%M_%S"))


class YamlConfigurationManager(ConfigurationManager):
    """
    This class manage the creation of a simulation with a Yaml configuration in input.
    Todo: Extract the Yaml reading part and implementing it elsewhere, In the adapter package maybe.
    """

    plain_configuration: dict
    two_line_element_configuration: TwoLineElementFile

    def __init__(self, configuration_path):
        self.configuration_path = configuration_path

    def load_configuration(self):
        with open(self.configuration_path, "r") as file:
            self.plain_configuration = yaml.safe_load(file)

    def load_simulation_configuration(self) -> Simulation:
        """
        Load configuration related to the simualtion
        :return:
        """

        simulation_name = self.plain_configuration.get(
            "simulation_name", generate_default_simulation_name()
        )
        simulation = Simulation()
        simulation.simulation_name = simulation_name

        distance_model = self.plain_configuration.get("distance_model", None)
        if distance_model is not None:
            if distance_model == "geopy":
                geopy_distance_model = GeopyDistanceModel()
                simulation.set_distance_model(geopy_distance_model)

        return simulation

    def load_satellite_configuration(self, simulation_manager: SimulationManager):
        """
        Load the simulation related to the satellites
        :param simulation_manager:
        :return:
        """
        constellation_file = self.plain_configuration.get("constellation_file")

        plain_start_date = self.plain_configuration.get("start_date")

        movement_model = self.plain_configuration.get("movement_model", None)

        start_date = datetime.strptime(plain_start_date, "%d/%m/%Y %H:%M:%S")

        if constellation_file is not None:
            self.two_line_element_configuration = parse_two_line_element_to_instance(
                constellation_file
            )

        if movement_model is not None and movement_model == "pyorbital":
            satellites = (
                generate_satellites_from_two_line_elements_with_pyorbital_model(
                    self.two_line_element_configuration.parsed_tles, start_date
                )
            )
        else:
            satellites = generate_satellites_from_two_line_element(
                self.two_line_element_configuration.parsed_tles
            )

        simulation_manager.add_all_satellites(satellites)

    def load_ground_station_configuration(self, simulation_manager: SimulationManager):
        """
        Load the simulation related to the ground stations
        :param simulation_manager: Simulation Manager
        :return:
        """
        ground_station_file = self.plain_configuration.get("ground_station_file")

        if ground_station_file is not None:
            ground_stations = generate_ground_stations_from_file(ground_station_file)
            simulation_manager.add_all_ground_stations(ground_stations)

    def load_user_terminal_configuration(self, simulation: Simulation):
        """
        Load the configuration related to the terminal users
        Not implemented yet
        :param simulation:
        :return:
        """
        raise NotImplementedError("Loading User hasn't been implemented yet")

    def load_inter_satellite_configuration(self, simulation_manager: SimulationManager):
        """
        Load Inter Satellite Links configuration. It will generate inter satellite links based on the
        satellite configuration previously loaded.
        :param simulation_manager:
        :return:
        """
        create_inter_satellite_link_from_two_line_element(
            simulation_manager, self.two_line_element_configuration
        )

    def load_ground_station_link_configuration(self, simulation: SimulationManager):
        """
        Load ground station links configuration. It will generate ground station link based on their position and the
        in range satellites.
        Todo: Add connection limit.
        :param simulation:
        :return:
        """
        ground_station_link_range = self.plain_configuration.get(
            "ground_station_link_range", 1000000
        )
        generate_ground_station_link_with_position(
            simulation, ground_station_link_range
        )

    def load_user_terminal_link_configuration(self, simulation: SimulationManager):
        raise NotImplementedError(
            "Loading User terminal links hasn't been implemented yet"
        )

    def load_simulation(self) -> SimulationManager:
        """
        This method load the simulation. It should be used to load simulation.
        :return: A simulation manager
        """
        self.load_configuration()

        simulation = self.load_simulation_configuration()

        simulation_manager = SimulationManager(simulation)

        self.load_satellite_configuration(simulation_manager)

        self.load_ground_station_configuration(simulation_manager)

        self.load_inter_satellite_configuration(simulation_manager)

        disable_ground_station_link_preload = self.plain_configuration.get(
            "disable_ground_station_link_preload", False
        )

        simulation.update()

        if not disable_ground_station_link_preload:
            self.load_ground_station_link_configuration(simulation_manager)

        return simulation_manager


class EmptyConfigurationManager(ConfigurationManager):
    """
    This class can be used to generate an empty simulation.
    """

    simulation_name: str

    def __init__(self, simulation_name: str = "EmptySimulation"):
        self.simulation_name = simulation_name

    def load_simulation(self) -> SimulationManager:
        simulation = Simulation()
        simulation.simulation_name = self.simulation_name
        simulation_manager = SimulationManager(simulation)
        return simulation_manager
