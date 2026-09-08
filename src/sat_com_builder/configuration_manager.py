from abc import ABC, abstractmethod

import yaml

from sat_com_application.simulation_manager import (
    SimulationManager,
    get_object_by_object_id,
)
from sat_com_application.time_managers import SimulationTimeManager
from sat_com_builder import (
    GROUND_STATION_TYPES_STR,
    POINT_OF_PRESENCE_TYPES_STR,
    USER_TERMINAL_TYPES_STR,
)
from sat_com_builder.ground_objects.generate_ground_stations import (
    generate_ground_stations_from_file,
)
from sat_com_builder.ground_objects.generate_point_of_presences import (
    generate_point_of_presences,
)
from sat_com_builder.ground_objects.generate_user_terminals import (
    generate_user_terminal_from_file,
)
from sat_com_builder.links.inter_satellite_link_generator import (
    create_inter_satellite_links_for_walker_constellation,
)
from sat_com_builder.models import SimulationProperty
from sat_com_builder.utils import parse_date
from sat_com_connectivity.ground_object_to_space_connectivity.ground_connection_strategy_registry import (
    GROUND_TO_SPACE_CONNECTION_STRATEGY_REGISTRY,
)
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

    def __save_property_inside_simulation_manager(
        self, simulation_manager: SimulationManager
    ):
        simulation_manager.configuration.update(
            properties=self.simulation_property.model_dump(
                mode="json", exclude_none=True
            )
        )

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

    def __load_static_ground_to_ground_link_configuration(
        self, simulation_manager: SimulationManager
    ):
        """
        Load ground to ground links configuration. It will generate ground to ground links based on the
        ground object configuration previously loaded.
        :param simulation_manager:
        :return:
        """

        for (
            ground_connectivity
        ) in self.simulation_property.ground_connectivity_properties:
            for link in ground_connectivity.links:
                source_domain, source_object_id = link[0][0], link[0][1]
                destination_domain, destination_object_id = link[1][0], link[1][1]

                object_source = get_object_by_object_id(
                    object_id=source_object_id,
                    topology_objects=simulation_manager.get_all_ground_objects(),
                    domain=source_domain,
                )

                object_destination = get_object_by_object_id(
                    object_id=destination_object_id,
                    topology_objects=simulation_manager.get_all_ground_objects(),
                    domain=destination_domain,
                )

                simulation_manager.create_and_add_ground_object_link_connection(
                    object_source, object_destination
                )

    def __load_satellite_to_ground_link_configuration(
        self, simulation_manager: SimulationManager
    ):
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
                ground_to_space_connections_strategy=ground_object.connectivity_properties.ground_to_space_connections_strategy,
            )

            ground_connection_strategy = (
                ground_object_domain.ground_to_space_connections_strategy
            )

            GROUND_TO_SPACE_CONNECTION_STRATEGY_REGISTRY.get(
                ground_connection_strategy, None
            )

            simulation_manager.add_ground_object_domain(
                ground_object_domain=ground_object_domain
            )

            if ground_object.type in GROUND_STATION_TYPES_STR:
                ground_stations = generate_ground_stations_from_file(
                    ground_station_file_path=ground_object.data_file,
                    ground_object_domain=ground_object_domain,
                )

                simulation_manager.add_all_ground_stations(ground_stations)

            elif ground_object.type in USER_TERMINAL_TYPES_STR:

                user_terminals = generate_user_terminal_from_file(
                    user_terminal_file_path=ground_object.data_file,
                    ground_object_domain=ground_object_domain,
                )
                simulation_manager.add_all_user_terminals(user_terminals)

            elif ground_object.type in POINT_OF_PRESENCE_TYPES_STR:
                point_of_presences = generate_point_of_presences(
                    point_of_presence_file_path=ground_object.data_file,
                    ground_object_domain=ground_object_domain,
                )
                simulation_manager.add_all_point_of_presences(point_of_presences)

            else:
                raise InvalidGroundObjectTypeError(
                    "Invalid ground object type: " + str(ground_object.type)
                )

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
                shell_constellation = WalkerStarConstellation(
                    walker_constellation_property=shell.constellation_property
                )
            elif shell.type == "delta":
                shell_constellation = WalkerDeltaConstellation(
                    walker_constellation_property=shell.constellation_property
                )
            else:
                raise ValueError("Walker constellation type not found: " + shell.type)

            walker_shell = WalkerShell(
                **shell.constellation_property.model_dump(), **shell.model_dump()
            )

            simulation_manager.add_walker_shell(walker_shell)

            if movement_model == "pyorbital":
                satellites = generate_satellites_from_walker_constellation(
                    walker_constellation=shell_constellation,
                    timer_manager=simulation_manager.time_manager,
                )
            else:
                raise ValueError("Invalid movement model: " + str(movement_model))

            for satellite in satellites:
                satellite.walker_shell = walker_shell

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

        self.__save_property_inside_simulation_manager(simulation_manager)

        self.__load_time_manager(simulation_manager=simulation_manager)

        self.__load_satellite_configuration(simulation_manager=simulation_manager)

        self.__load_ground_object_configuration(simulation_manager=simulation_manager)

        self.__load_inter_satellite_configuration(simulation_manager=simulation_manager)

        self.__load_satellite_to_ground_link_configuration(
            simulation_manager=simulation_manager
        )

        self.__load_static_ground_to_ground_link_configuration(
            simulation_manager=simulation_manager
        )

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
            super().__init__(SimulationProperty(**plain_configuration))
            file.close()
