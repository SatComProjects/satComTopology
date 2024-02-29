from datetime import datetime

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
from sat_com_model.model import Simulation
import yaml

from sat_com_trajectopy.satellites.generate_satellite import (
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

        ground_station_link_range = self.plain_configuration.get(
            "ground_station_link_range"
        )

        plain_start_date = self.plain_configuration.get("start_date")

        movement_model = self.plain_configuration.get("movement_model", None)

        start_date = datetime.strptime(plain_start_date, "%d/%m/%Y %H:%M:%S")

        simulation = Simulation()
        simulation.simulation_name = simulation_name

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

        simulation.add_all_satellites(satellites)

        ground_stations = generate_ground_stations_from_file(ground_station_file)
        simulation.add_all_ground_stations(ground_stations)

        create_inter_satellite_link_from_two_line_element(
            simulation, self.two_line_element_configuration
        )

        create_inter_satellite_link_from_two_line_element(
            simulation, self.two_line_element_configuration
        )

        generate_ground_station_link_with_position(
            simulation, ground_station_link_range
        )

        return simulation
