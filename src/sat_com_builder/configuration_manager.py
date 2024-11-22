from abc import ABC, abstractmethod

import yaml

from sat_com_application.simulation_manager import SimulationManager
from sat_com_application.time_managers import SimulationTimeManager
from sat_com_builder.ground_objects.generate_ground_stations import (
    generate_ground_stations_from_file,
)
from sat_com_builder.ground_objects.generate_user_terminals import (
    generate_user_terminal_from_file,
)
from sat_com_builder.links.inter_satellite_link_generator import (
    create_inter_satellite_links_for_walker_constellation,
)
from sat_com_builder.models import SimulationProperty, WalkerShellProperty
from sat_com_builder.utils import parse_date
from sat_com_constellation.models import (
    WalkerStarConstellation,
    WalkerDeltaConstellation,
)
from sat_com_model.exceptions import (
    DistanceModelUndefinedError,
    InvalidGroundObjectTypeError,
)
from sat_com_model.models import (
    Simulation,
    GroundObjectDomain,
    WalkerShell,
)
from sat_com_trajectopy.distance_models import (
    GeopyDistanceModel,
    SkLearningDistanceModel,
)
from sat_com_trajectopy.satellites.generate_satellite import (
    generate_satellites_from_walker_constellation,
)


class ConfigurationManager(ABC):

    @abstractmethod
    def load_simulation(self) -> SimulationManager:
        pass


class BaseConfigurationManager(ConfigurationManager):

    def __init__(self, simulation_property: SimulationProperty):
        self.simulation_property = simulation_property

    def __load_inter_satellite_configuration(
        self, simulation_manager: SimulationManager
    ):
        """
        Load Inter Satellite Links configuration. It will generate inter satellite links based on the
        satellite configuration previously loaded.
        :param simulation_manager:
        :return:
        """

        for shell in self.simulation_property.walker_shells:
            create_inter_satellite_links_for_walker_constellation(
                simulation_manager=simulation_manager, walker_shell_properties=shell
            )

    def __load_ground_link_configuration(self, simulation_manager: SimulationManager):
        """
        Load ground station links configuration. It will generate ground station link based on their position and the
        in range satellites.
        :param simulation_manager:
        :return:
        """

        simulation_manager.static_ground_station_link_mode = (
            self.simulation_property.static_ground_station_link_mode
        )

        if not self.simulation_property.disable_ground_station_link_preload:
            simulation_manager.update_ground_station_links()
            simulation_manager.update_user_terminal_links()

    def __load_ground_object_configuration(self, simulation_manager: SimulationManager):
        """
        Load the simulation related to the ground stations
        :param simulation_manager: Simulation Manager
        :return:
        """

        for ground_object in self.simulation_property.ground_objects_properties:

            ground_object_domain = GroundObjectDomain(
                identifier=ground_object.identifier,
                type=ground_object.type,
                elevation_above_horizon=ground_object.connectivity_properties.elevation_above_horizon,
                maximum_satellite_range_distance=ground_object.connectivity_properties.maximum_satellite_range_distance,
                maximum_satellite_connected_count=ground_object.connectivity_properties.maximum_satellite_connected_count,
                shell_white_lists=ground_object.connectivity_properties.shell_white_lists,
                maximum_connected_satellites=ground_object.connectivity_properties.maximum_connected_satellites,
            )

            simulation_manager.add_ground_object_domain(
                ground_object_domain=ground_object_domain
            )

            if ground_object.type == "ground_station":
                ground_stations = generate_ground_stations_from_file(
                    ground_station_file_path=ground_object.data_file
                )
                simulation_manager.add_all_ground_stations(ground_stations)

            elif ground_object.type == "user_terminal":

                user_terminals = generate_user_terminal_from_file(
                    user_terminal_file_path=ground_object.data_file
                )
                simulation_manager.add_all_user_terminals(user_terminals)
            else:
                raise InvalidGroundObjectTypeError()

    def __load_satellite_configuration(self, simulation_manager: SimulationManager):
        """
        Load the simulation related to the satellites
        :param simulation_manager:
        :return:
        """
        movement_model = self.simulation_property.movement_model

        if len(self.simulation_property.walker_shells) == 0:
            print("No shell detected")
            return

        for shell in self.simulation_property.walker_shells:
            if shell.type == "star":
                shell_constellation = (
                    WalkerStarConstellation.create_from_constellation_property(
                        walker_constellation_property=shell.constellation_property
                    )
                )
            elif shell.type == "delta":
                shell_constellation = (
                    WalkerDeltaConstellation.create_from_constellation_property(
                        walker_constellation_property=shell.constellation_property
                    )
                )
            else:
                raise ValueError("Walker constellation type not found: " + shell.type)

            simulation_manager.add_walker_shell(
                WalkerShell(
                    **shell.constellation_property.model_dump(), **shell.model_dump()
                )
            )

            if movement_model == "pyorbital":
                satellites = generate_satellites_from_walker_constellation(
                    walker_constellation=shell_constellation,
                    timer_manager=simulation_manager.time_manager,
                )
            else:
                raise ValueError("Invalid movement model: " + str(movement_model))

            simulation_manager.add_all_satellites(satellites)

    def __load_time_manager(self, simulation_manager: SimulationManager):

        plain_start_date = self.simulation_property.start_date

        plain_end_date = self.simulation_property.end_date

        start_date = parse_date(plain_start_date)
        end_date = parse_date(plain_end_date)

        time_manager = SimulationTimeManager(start_date=start_date, end_date=end_date)

        simulation_manager.set_time_manager(time_manager=time_manager)

    def __create_and_load_simulation(self) -> Simulation:
        """
        Construct the Simulation object.
        Setup Distance Models
        :return:
        """
        simulation = Simulation()
        simulation.simulation_name = self.simulation_property.simulation_name

        distance_model = self.simulation_property.distance_model
        if distance_model is not None:
            if distance_model == "geopy":
                geopy_distance_model = GeopyDistanceModel()
                simulation.set_distance_model(distance_model=geopy_distance_model)

            elif distance_model == "sklearn":
                sklearn_distance_model = SkLearningDistanceModel()
                simulation.set_distance_model(distance_model=sklearn_distance_model)

            else:
                raise DistanceModelUndefinedError()

        return simulation

    def load_simulation(self) -> SimulationManager:
        simulation = self.__create_and_load_simulation()

        simulation_manager = SimulationManager(simulation=simulation)

        self.__load_time_manager(simulation_manager=simulation_manager)

        self.__load_satellite_configuration(simulation_manager=simulation_manager)

        self.__load_ground_object_configuration(simulation_manager=simulation_manager)

        self.__load_inter_satellite_configuration(simulation_manager=simulation_manager)

        self.__load_ground_link_configuration(simulation_manager=simulation_manager)

        return simulation_manager


class EmptyConfigurationManager(BaseConfigurationManager):
    """
    This class can be used to generate an empty simulation.
    """

    simulation_name: str

    def __init__(
        self,
        simulation_property: SimulationProperty = None,
        simulation_name: str = "EmptySimulation",
    ):
        super().__init__(simulation_property)
        self.simulation_name = simulation_name
        if simulation_property is None:
            self.simulation_property = SimulationProperty()

    def load_simulation(self) -> SimulationManager:
        simulation = Simulation()
        simulation.simulation_name = self.simulation_name
        simulation_manager = SimulationManager(simulation=simulation)
        return simulation_manager


class YamlConfigurationManager(BaseConfigurationManager):
    """
    This class create a simulation from a Yaml configuration
    """

    configuration_path: str

    def __init__(self, configuration_path: str):
        with open(configuration_path, "r") as file:
            plain_configuration = yaml.safe_load(file)
            self.configuration_path = configuration_path
            super().__init__(plain_configuration)
            file.close()
