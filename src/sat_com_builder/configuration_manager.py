from datetime import datetime

from src.sat_com_builder.isl.isl_generator import (
    create_inter_satellite_link_from_two_line_element,
)
from src.sat_com_builder.tle.two_line_element_file import (
    parse_two_line_element_to_instance,
    TwoLineElementFile,
)
from src.sat_com_model.model import Simulation
import yaml

from src.sat_com_trajectopy.satellites.generate_satellite import (
    generate_satellites_from_two_line_elements_with_pyorbital_model,
)


class ConfigurationManager:
    def load_simulation(self) -> Simulation:
        pass


def generate_default_simulation_name():
    return "simulation_{date}".format(date=datetime.now().strftime("%Y%m%d-%H_%M_%S"))


class YamlConfigurationManager(ConfigurationManager):
    plain_configuration: dict
    two_line_element_configuration: TwoLineElementFile

    def __init__(self, configuration_path):
        self.configuration_path = configuration_path

    def load_configuration(self):
        with open(self.configuration_path, "r") as file:
            self.plain_configuration = yaml.safe_load(file)

    def load_simulation(self) -> Simulation:
        self.load_configuration()

        simulation_name = self.plain_configuration.get(
            "simulation_name", generate_default_simulation_name()
        )
        constellation_file = self.plain_configuration.get("constellation_file")

        ground_station_file = self.plain_configuration.get("ground_station_file")

        start_date = self.plain_configuration.get("start_date")

        simulation = Simulation()
        simulation.simulation_name = simulation_name

        self.two_line_element_configuration = parse_two_line_element_to_instance(
            constellation_file
        )

        simulation.topology_objects.extend(
            generate_satellites_from_two_line_elements_with_pyorbital_model(
                self.two_line_element_configuration.parsed_tles, simulation, start_date
            )
        )

        create_inter_satellite_link_from_two_line_element(
            simulation, self.two_line_element_configuration
        )

        return simulation
