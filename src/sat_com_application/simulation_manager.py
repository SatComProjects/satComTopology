import uuid
from typing import Callable

from sat_com_application.time_managers import SimulationTimeManager
from sat_com_connectivity.ground_object_to_space_connectivity.ground_connection_strategy_registry import (
    GROUND_TO_SPACE_CONNECTION_STRATEGY_REGISTRY,
)
from sat_com_model.exceptions import (
    TopologyObjectNotFoundError,
    LinkNotFoundError,
    WalkerShellNotFoundError,
    GroundObjectDomainNotFoundError,
)
from sat_com_model.models import (
    Simulation,
    Satellite,
    GroundStation,
    UserTerminal,
    TopologyObject,
    Link,
    InterSatelliteLink,
    GroundStationLink,
    UserTerminalLink,
    Flow,
    WalkerShell,
    GroundObjectDomain,
    GroundObject,
    GroundObjectLink,
    PointOfPresence,
)
from sat_com_model.specifications import (
    SourceDestinationMatchWithLinkSpecification,
)


def get_object_by_object_id(
    object_id: int, topology_objects: list, domain: str = "public"
) -> Satellite | GroundStation | UserTerminal | PointOfPresence | None:
    """
    Return the topology object matching its object_id
    :param domain: Domain where the object belong. If missing public domain will be provided
    :param object_id: the object identifier (satellite.object_id, ground_station.object_id, etc.)
    :param topology_objects: The list of objects from its type /!\\ SHOULDN'T BE A LIST OF TOPOLOGY_OBJECT
    :return:
    """

    matched_objects = [
        topology_object
        for topology_object in topology_objects
        if topology_object.object_id == object_id and topology_object.domain == domain
    ]

    if len(matched_objects) == 1:
        return matched_objects[0]

    if len(matched_objects) > 1:
        raise Exception()

    if len(matched_objects) == 0:
        raise TopologyObjectNotFoundError()


def ground_station_link_is_connected_to_ground_station(
    ground_station_link: GroundStationLink, ground_station_object_id: int
) -> bool:
    """
    Check if the ground station link is connected to a ground station with the given id
    :param ground_station_link: Ground station link instance
    :param ground_station_object_id: Ground station object id
    :return:
    """
    source = ground_station_link.source
    destination = ground_station_link.destination

    if isinstance(source, GroundStation):
        return source.object_id == ground_station_object_id
    elif isinstance(destination, GroundStation):
        return destination.object_id == ground_station_object_id
    else:
        raise ValueError("This ground station link is corrupted")


class SimulationManager:
    """
    This class regroup every method to manage simulation.
    Every function which can manage Simulation should be here.
    We shouldn't put logic into the models.
    """

    configuration: dict

    simulation: Simulation

    time_manager: SimulationTimeManager

    static_ground_station_link_mode: bool

    ground_to_space_connection_strategies: dict = dict()

    def __init__(self, simulation: Simulation):
        self.simulation = simulation
        self.configuration = dict()
        self.enabled_update_functions = None
        self.static_ground_station_link_mode = False

        self.ground_to_space_connection_strategies = {}
        for name, cls in GROUND_TO_SPACE_CONNECTION_STRATEGY_REGISTRY.items():
            kwargs = {"distance_model": self.simulation.distance_model}

            self.ground_to_space_connection_strategies[name] = cls(**kwargs)

    def set_time_manager(self, time_manager: SimulationTimeManager):
        self.time_manager = time_manager
        self.time_manager.register_action(self.__update)

    enabled_update_functions: list[Callable] | None

    @property
    def update_protocol(self) -> list[Callable]:
        if self.enabled_update_functions is None:
            return self.get_default_update_protocol()
        else:
            return self.enabled_update_functions

    def __update(self):
        for update_function in self.update_protocol:
            update_function()

    def append_flows(self, list_of_flows: list[list]) -> set[Link]:
        """
        Append to the Links a Flow object for every flow generated
        :param list_of_flows: List of flows, a flow is a list of topology_uniq_id
        :return: The links that contains the added flow
        """
        links = set()
        for topology_paths in list_of_flows:
            links.update(self.reconstruct_path_to_and_add_flow(topology_paths))
        return links

    def add_satellite(self, satellite: Satellite):
        """
        Add satellite to the simulation. Automatically attribute a uniq topology id.
        :param satellite: Satellite instance to add
        :return:
        """
        satellite.topology_uniq_id = self.simulation.request_an_id()
        self.simulation.satellites.append(satellite)

    def add_ground_station(self, ground_station: GroundStation):
        """
        Add ground station to the simulation. Automatically attribute an uniq topology id.
        :param ground_station: Ground station instance to add
        :return:
        """
        ground_station.topology_uniq_id = self.simulation.request_an_id()
        self.simulation.ground_stations.append(ground_station)

    def add_user_terminals(self, user_terminal: UserTerminal):
        """
        Add user terminals to the simulation. Automatically attribute an uniq topology id
        :param user_terminal: User terminal instance to add
        :return:
        """
        user_terminal.topology_uniq_id = self.simulation.request_an_id()
        self.simulation.user_terminals.append(user_terminal)

    def add_point_of_presence(self, point_of_presence: PointOfPresence):
        """
        Add point of presence to the simulation. Automatically attribute an uniq topology id
        :param point_of_presence: Point of presence instance to add
        :return:
        """
        point_of_presence.topology_uniq_id = self.simulation.request_an_id()
        self.simulation.point_of_presences.append(point_of_presence)

    def get_all_topology_objects(self) -> list[TopologyObject]:
        """
        Get all topology objects from the simulation.
        :return: List of topology objects
        """
        return self.simulation.get_all_topology_objects()

    def get_all_ground_objects(self) -> list[GroundObject]:
        """
        Get all ground objects from the simulation.
        :return: List of ground objects
        """
        return self.simulation.get_all_ground_objects()

    def get_all_links(self) -> list[Link]:
        """
        Get all links of the simulation.
        :return: List of links
        """
        all_links = []
        all_links.extend(self.simulation.inter_satellite_links)
        all_links.extend(self.simulation.ground_station_links)
        all_links.extend(self.simulation.user_terminal_links)
        all_links.extend(self.simulation.ground_object_links)

        return all_links

    def get_satellite_by_object_id(
        self, object_id: int, domain: str = "public"
    ) -> Satellite:
        """
        Get satellite by its object id. (Satellite identifier)
        :param domain: The domain to check whereas identifier belongs. If not provided "public" domain will be provided
        :param object_id:  Satellite identifier
        :return: Satellite instance
        """
        return get_object_by_object_id(
            object_id=object_id,
            domain=domain,
            topology_objects=self.simulation.satellites,
        )

    def get_ground_station_by_object_id(
        self, object_id: int, domain: str = "public"
    ) -> GroundStation:
        """
        Get ground station by its object id. (Ground station identifier)
        :param domain: The domain to check whereas identifier belongs. If not provided "public" domain will be provided
        :param object_id:  Ground station identifier
        :return: Ground station instance
        """
        return get_object_by_object_id(
            object_id=object_id,
            domain=domain,
            topology_objects=self.simulation.ground_stations,
        )

    def get_user_terminal_by_object_id(
        self, object_id: int, domain: str = "public"
    ) -> UserTerminal:
        """
        Get user terminal by its object id. (User terminal identifier)
        :param domain: The domain to check whereas identifier belongs. If domain missing, public domain will be provided
        :param object_id: User terminal identifier
        :return: User terminal instance
        """
        return get_object_by_object_id(
            object_id=object_id,
            domain=domain,
            topology_objects=self.simulation.user_terminals,
        )

    def get_topology_object_from_uniq_id(self, uniq_id: int) -> TopologyObject:
        """
        Get any topology object from its uniq id. (Topology identifier)
        :param uniq_id: Unique identifier
        :return: Topology instance
        """
        for obj in self.get_all_topology_objects():
            if obj.topology_uniq_id == uniq_id:
                return obj

        raise TopologyObjectNotFoundError()

    def create_and_add_inter_satellite_link_connection(
        self, satellite_a: Satellite, satellite_b: Satellite
    ) -> InterSatelliteLink:
        """
        Create inter-satellite link between two satellites
        :param satellite_a: Satellite instance A
        :param satellite_b: Satellite instance B
        :return: InterSatelliteLink instance
        """
        inter_satellite_link = InterSatelliteLink()
        inter_satellite_link.connect(satellite_a, satellite_b)

        satellite_a.links.append(inter_satellite_link)
        satellite_b.links.append(inter_satellite_link)

        self.simulation.inter_satellite_links.append(inter_satellite_link)
        return inter_satellite_link

    def create_and_add_ground_station_link_connection(
        self,
        satellite: Satellite,
        ground_station: GroundStation,
        elevation_above_horizon_angle: float = 0,
    ) -> GroundStationLink:
        """
        Create a ground station link between a satellite and a ground station and append it to the simulation.
        :param satellite: Satellite instance
        :param ground_station: GroundStation instance
        :param elevation_above_horizon_angle:
        :return: GroundStationLink instance

        """
        ground_station_link = GroundStationLink()
        ground_station_link.connect(satellite, ground_station)
        ground_station_link.elevation_above_horizon_angle = (
            elevation_above_horizon_angle
        )

        satellite.links.append(ground_station_link)
        ground_station.links.append(ground_station_link)

        self.simulation.ground_station_links.append(ground_station_link)
        return ground_station_link

    def create_and_add_user_terminal_link_connection(
        self,
        satellite: Satellite,
        user_terminal: UserTerminal,
        elevation_above_horizon_angle: float = 0,
    ) -> UserTerminalLink:
        """
        Create a user terminal link between a satellite and a user terminal
        :param elevation_above_horizon_angle:
        :param satellite: Satellite instance
        :param user_terminal: User terminal instance
        :return: UserTerminalLink instance
        """
        user_terminal_link = UserTerminalLink()
        user_terminal_link.connect(satellite, user_terminal)
        user_terminal_link.elevation_above_horizon_angle = elevation_above_horizon_angle

        satellite.links.append(user_terminal_link)
        user_terminal.links.append(user_terminal_link)

        self.simulation.user_terminal_links.append(user_terminal_link)
        return user_terminal_link

    def create_and_add_ground_object_link_connection(
        self, ground_object_1: GroundObject, ground_object_2: GroundObject
    ) -> GroundObjectLink:
        ground_object_link = GroundObjectLink()
        ground_object_link.connect(ground_object_1, ground_object_2)

        self.simulation.ground_object_links.append(ground_object_link)

        return ground_object_link

    def add_all_satellites(self, satellites: list[Satellite]):
        """
        Add all satellites to the simulation from a list in argument
        :param satellites: List of satellites to add
        :return:
        """
        for satellite in satellites:
            self.add_satellite(satellite)

    def add_all_ground_stations(self, ground_stations: list[GroundStation]):
        """
        Add all ground to the simulation from a list in argument
        :param ground_stations: List of ground stations to add
        :return:
        """
        for ground_station in ground_stations:
            self.add_ground_station(ground_station)

    def add_all_user_terminals(self, user_terminals: list[UserTerminal]):
        """
        Add all user terminals to the simulation from a list in argument
        :param user_terminals: List of user terminals to add
        :return:
        """
        for user_terminal in user_terminals:
            self.add_user_terminals(user_terminal)

    def add_all_point_of_presences(self, point_of_presences: list[PointOfPresence]):
        for point_of_presence in point_of_presences:
            self.add_point_of_presence(point_of_presence)

    def get_ascending_satellites(self) -> list[Satellite]:
        """
        Return all satellites in ascending phase
        :return: List of satellites
        """
        return [sat for sat in self.simulation.satellites if sat.is_ascending()]

    def get_satellites(self) -> list[Satellite]:
        """
        Get all simulation satellites
        :return: List of satellites
        """
        return self.simulation.satellites

    def get_ground_stations(self) -> list[GroundStation]:
        """
        Get all simulation ground stations
        :return: List of ground stations
        """
        return self.simulation.ground_stations

    def get_user_terminals(self) -> list[UserTerminal]:
        """
        Get all simulation user terminals
        :return: List of user terminals
        """
        return self.simulation.user_terminals

    def get_user_terminal_links(self) -> list[UserTerminalLink]:
        """
        Get all simulation user terminal links
        :return: List of user terminal links
        """
        return self.simulation.user_terminal_links

    def get_inter_satellites_links(self) -> list[InterSatelliteLink]:
        """
        Get all simulation inter satellite links
        :return: List of inter satellite links
        """
        return self.simulation.inter_satellite_links

    def get_ground_stations_links(self) -> list[GroundStationLink]:
        """
        Get all simulation ground stations links
        :return: List of ground stations links
        """
        return self.simulation.ground_station_links

    def get_static_ground_object_links(self):
        """
        Get all simulation static ground object links
        :return: List of static ground object links
        """
        return self.simulation.ground_object_links

    def get_descending_satellites(self) -> list[Satellite]:
        """
        Get all simulation descending satellites
        :return: List of descending satellites
        """
        return [sat for sat in self.simulation.satellites if not sat.is_ascending()]

    def get_distance_between_two_topology_object_km(
        self, object_1: TopologyObject, object_2: TopologyObject
    ) -> float:
        """
        Get distance between two topology object in km.
        :param object_1: Topology object A
        :param object_2: Topology object  B
        :return: float: Distance between two topology objects
        """
        return self.simulation.get_distance_model().get_ground_distance_km(
            object_1.get_coordinates(), object_2.get_coordinates()
        )

    def get_closest_satellite_to_a_ground_station(
        self,
        ground_station: GroundStation,
        orbit_direction: str = None,
    ) -> Satellite:
        """
        Get the closest satellite from a ground station.
        :param ground_station: Ground station
        :param orbit_direction: Direction of the orbit, either 'ascending' or 'descending'. Other values will be ignored
        :return: Satellite instance
        """
        if orbit_direction == "ascending":
            satellites_to_filter = self.get_ascending_satellites()
        elif orbit_direction == "descending":
            satellites_to_filter = self.get_descending_satellites()
        else:
            satellites_to_filter = self.simulation.satellites

        closest_satellite = self.simulation.get_distance_model().k_closest(
            ground_station, satellites_to_filter, 1
        )[0]
        if isinstance(closest_satellite, Satellite):
            return closest_satellite
        else:
            raise TopologyObjectNotFoundError("Satellite not found")

    def get_ground_station_links_connected_to_a_ground_station(
        self, ground_station_id: int
    ) -> list[GroundStationLink]:
        """
        Return all ground station links connected to a ground station
        :param ground_station_id:
        :return:
        """
        return [
            link
            for link in self.simulation.ground_station_links
            if ground_station_link_is_connected_to_ground_station(
                link, ground_station_id
            )
            and not link.disabled
        ]

    def remove_ground_station_link(self, ground_station_link: GroundStationLink):
        """
        Remove a Ground Station link
        :param ground_station_link: Ground Station Link to remove
        :return:
        """
        ground_station_link.source.links.remove(ground_station_link)
        ground_station_link.destination.links.remove(ground_station_link)

        self.simulation.ground_station_links.remove(ground_station_link)

    def remove_inter_satellite_link(self, inter_satellite_link: InterSatelliteLink):
        """
        Remove an Inter satellite  link
        :param inter_satellite_link: Inter satellite Link to remove
        :return:
        """
        inter_satellite_link.source.links.remove(inter_satellite_link)
        inter_satellite_link.destination.links.remove(inter_satellite_link)

        self.simulation.inter_satellite_links.remove(inter_satellite_link)

    def remove_user_terminal_link(self, user_terminal_link: UserTerminalLink):
        """
        Remove a user terminal link
        :param user_terminal_link: User terminal link to remove
        :return:
        """

        user_terminal_link.source.links.remove(user_terminal_link)
        user_terminal_link.destination.links.remove(user_terminal_link)

        self.simulation.user_terminal_links.remove(user_terminal_link)

    def remove_all_ground_station_links(
        self, ground_station_links: list[GroundStationLink]
    ):
        """
        Remove  a list of ground station links
        :param ground_station_links: List of ground station links to remove
        :return:
        """
        for ground_station_link in ground_station_links:
            self.remove_ground_station_link(ground_station_link)

    def disconnect_all_ground_station_links_from_ground_station(
        self, ground_station: GroundStation
    ):
        """
        Disconnect all ground station links from a specified station
        :param ground_station: Ground Station to remove link
        :return:
        """
        connected_ground_station_links = (
            self.get_ground_station_links_connected_to_a_ground_station(
                ground_station.object_id
            )
        )
        self.remove_all_ground_station_links(connected_ground_station_links)

    def disconnect_every_ground_stations(self):
        """
        Disconnect every ground station which mean remove every ground station link connected
        :return:
        """
        self.get_ground_stations_links().clear()

    def get_link_connecting_topology_objects(
        self, topology_object_a: TopologyObject, topology_object_b: TopologyObject
    ) -> Link:
        """
        Get the link connecting two topology objects.  It will return  the first link found. It shouldn't have
        2 links.
        Todo: Use specification specification
        :param topology_object_a: Topology object source
        :param topology_object_b: Topology object destination
        :return: Link connecting two topology objects, raise LinkNotFoundError if not found
        """
        for link in self.get_all_links():
            link_source_topology_id = link.source.topology_uniq_id
            link_destination_topology_id = link.destination.topology_uniq_id

            link_source_correspond_to_object_a = (
                link_source_topology_id == topology_object_a.topology_uniq_id
            )
            link_source_correspond_to_object_b = (
                link_destination_topology_id == topology_object_b.topology_uniq_id
            )

            link_is_connecting_object_a_to_object_b = (
                link_source_correspond_to_object_a
                and link_source_correspond_to_object_b
            )

            link_source_correspond_to_object_b = (
                link_source_topology_id == topology_object_b.topology_uniq_id
            )
            link_destination_correspond_to_object_a = (
                link_destination_topology_id == topology_object_a.topology_uniq_id
            )

            link_is_connecting_object_b_to_object_a = (
                link_source_correspond_to_object_b
                and link_destination_correspond_to_object_a
            )

            link_connect_objects = (
                link_is_connecting_object_a_to_object_b
                or link_is_connecting_object_b_to_object_a
            )

            if link_connect_objects:
                return link

        raise LinkNotFoundError()

    def reconstruct_path_to_and_add_flow(
        self, topology_object_id_list: list[int]
    ) -> list[Link]:
        """
        Retrieve every link connecting object in the list. Can be used to reconstruct a routing path
        :param topology_object_id_list: List of topology object ID
        :return: List of Link objects
        """

        flow_id = uuid.uuid4()

        topology_object_id_source = topology_object_id_list[0]
        topology_object_id_destination = topology_object_id_list[-1]

        topology_objects = [
            self.get_topology_object_from_uniq_id(object_id)
            for object_id in topology_object_id_list
        ]

        list_link_flow = []

        for i in range(len(topology_objects) - 1):
            input_source = topology_objects[i]
            output_destination = topology_objects[i + 1]

            connected_link = self.get_link_connecting_topology_objects(
                input_source, output_destination
            )
            flow = Flow()
            flow.id = flow_id
            flow.next_hop = output_destination.topology_uniq_id
            flow.previous_hop = input_source.topology_uniq_id
            flow.source = topology_object_id_source
            flow.destination = topology_object_id_destination

            connected_link.flows.append(flow)

            list_link_flow.append(connected_link)

        return list_link_flow

    def reconstruct_path(self, topology_object_id_list: list[int]) -> list[Link]:
        """
        Retrieve every link connecting object in the list. Can be used to reconstruct a routing path
        :param topology_object_id_list: List of topology object ID
        :return: List of Link objects
        """
        topology_objects = [
            self.get_topology_object_from_uniq_id(object_id)
            for object_id in topology_object_id_list
        ]

        list_link = []

        for i in range(len(topology_objects) - 1):
            source = topology_objects[i]
            destination = topology_objects[i + 1]

            connected_link = self.get_link_connecting_topology_objects(
                source, destination
            )

            list_link.append(connected_link)

        return list_link

    def connect_every_satellite_with_every_ground_stations(self):
        """
        This method will connect every satellite with every ground station, it will clear existing ground stations
        links
        :return:
        """
        self.simulation.ground_station_links.clear()

        for ground_station in self.get_ground_stations():
            for satellite in self.get_satellites():
                self.create_and_add_ground_station_link_connection(
                    satellite, ground_station
                )

    def connect_every_satellite_with_every_user_terminals_and_disable_un_connected(
        self,
    ):
        """
        This method will connect every satellite with every user terminal, it will clear existing user terminals
        links
        :return:
        """
        self.simulation.ground_station_links.clear()

        for user_terminal in self.get_user_terminals():
            simulation_domain = self.get_ground_object_domain(user_terminal.domain)
            satellites_in_range = self.simulation.get_distance_model().spatial_position_on_ground_in_range(
                user_terminal,
                self.get_satellites(),
                int(simulation_domain.maximum_satellite_range_distance),
            )
            for satellite in self.get_satellites():
                created_user_terminal_link = (
                    self.create_and_add_user_terminal_link_connection(
                        satellite, user_terminal
                    )
                )

                created_user_terminal_link.disabled = (
                    satellite not in satellites_in_range
                )

    def connect_every_satellite_with_every_ground_stations_and_disable_un_connected(
        self,
    ):
        """
        This method will connect every satellite with every ground station, it will clear existing ground stations
        links
        :return:
        """
        self.simulation.ground_station_links.clear()

        for ground_station in self.get_ground_stations():
            simulation_domain = self.get_ground_object_domain(ground_station.domain)
            satellites_in_range = self.simulation.get_distance_model().spatial_position_on_ground_in_range(
                ground_station,
                self.get_satellites(),
                int(simulation_domain.maximum_satellite_range_distance),
            )
            for satellite in self.get_satellites():
                created_ground_station_link = (
                    self.create_and_add_ground_station_link_connection(
                        satellite, ground_station
                    )
                )

                created_ground_station_link.disabled = (
                    satellite not in satellites_in_range
                )

    def get_ground_station_link(
        self, ground_station: GroundStation, satellite: Satellite
    ):
        satellite_ground_station_match = SourceDestinationMatchWithLinkSpecification(
            satellite, ground_station
        )
        ground_station_satellite_match = SourceDestinationMatchWithLinkSpecification(
            ground_station, satellite
        )

        link_connect_both_specification = (
            satellite_ground_station_match | ground_station_satellite_match
        )

        link_founds = list(
            filter(
                lambda ground_station_link: link_connect_both_specification(
                    ground_station_link
                ),
                self.get_ground_stations_links(),
            )
        )
        if len(link_founds) == 0:
            raise LinkNotFoundError()

        if len(link_founds) > 1:
            raise Exception("Too many links connect the same source destination")

        return link_founds[0]

    def enable_ground_station_links(self, ground_station, ground_station_range: float):
        satellites_in_range = (
            self.simulation.get_distance_model().spatial_position_on_ground_in_range(
                ground_station, self.get_satellites(), int(ground_station_range)
            )
        )

        for satellite in satellites_in_range:
            if isinstance(satellite, Satellite):
                ground_station_link = self.get_ground_station_link(
                    ground_station, satellite
                )
                ground_station_link.disabled = False

    def get_connected_satellites_to_ground_station(
        self, ground_station: GroundStation
    ) -> list[Satellite]:
        satellites_connected = set()

        for ground_station_link in self.get_ground_stations_links():
            if (
                ground_station_link.source is not None
                and ground_station_link.source == ground_station
            ):
                satellites_connected.add(ground_station_link.destination)
            if ground_station_link.destination == ground_station:
                satellites_connected.add(ground_station_link.source)

        return list(satellites_connected)

    def connect_user_terminal_to_satellites(
        self, user_terminal: UserTerminal, maximum_satellite_range_distance: float
    ):
        """
        This method will connect every satellite with every ground station
        :param user_terminal:
        :param maximum_satellite_range_distance:
        :return:
        """
        if len(self.get_satellites()) == 0:
            return

        satellites_in_range = (
            self.simulation.get_distance_model().spatial_position_on_ground_in_range(
                user_terminal,
                self.get_satellites(),
                int(maximum_satellite_range_distance),
            )
        )
        for satellite in satellites_in_range:
            if isinstance(satellite, Satellite):
                self.create_and_add_user_terminal_link_connection(
                    satellite, user_terminal
                )
            else:
                raise ValueError(
                    "An object of type " + type(satellite).__name__ + " wasn't expected"
                )

    def connect_ground_station_to_satellites(
        self,
        ground_station: GroundStation,
        ground_station_range_in_km: float,
    ):
        """
        Connect ground station to satellites.
        Implement a way to limit the count of satellite connected to ground stations.
        :param ground_station: Ground Station to connect to satellites
        :param ground_station_range_in_km: Range of satellites to connect to satellites
        :return:
        """

        if len(self.get_satellites()) == 0:
            return

        satellites_in_range = (
            self.simulation.get_distance_model().spatial_position_on_ground_in_range(
                ground_station, self.get_satellites(), int(ground_station_range_in_km)
            )
        )
        for satellite in satellites_in_range:
            if isinstance(satellite, Satellite):
                self.create_and_add_ground_station_link_connection(
                    satellite, ground_station
                )
            else:
                raise ValueError(
                    "An object of type " + type(satellite).__name__ + " wasn't expected"
                )

    def get_link_connected_to_topology_object(
        self, topology_object: TopologyObject
    ) -> set[Link]:
        connected_links = set()
        for link in self.get_all_links():
            if link.source == topology_object or link.destination == topology_object:
                connected_links.add(link)

        return connected_links

    def remove_link(self, link: Link) -> Link:
        """
        Remove a link from simulation whatever the type
        :param link:
        :return:
        """

        if isinstance(link, InterSatelliteLink):
            self.remove_inter_satellite_link(link)
        elif isinstance(link, GroundStationLink):
            self.remove_ground_station_link(link)
        elif isinstance(link, UserTerminalLink):
            self.remove_user_terminal_link(link)
        else:
            raise ValueError("Link type unknown: " + link.type)
        return link

    def __remove_topology_object(
        self, topology_object: TopologyObject
    ) -> TopologyObject:
        """
        WARNING SHOULD ONLY BE USED IN A CONTROLLED PLACE. EDGE EFFECT GUARANTEES
        :return: Deleted topology object
        """
        if isinstance(topology_object, Satellite):
            self.simulation.satellites.remove(topology_object)
        elif isinstance(topology_object, GroundStation):
            self.simulation.ground_stations.remove(topology_object)
        elif isinstance(topology_object, UserTerminal):
            self.simulation.user_terminals.remove(topology_object)
        else:
            raise ValueError("Topology object type unknown: " + topology_object.type)

        return topology_object

    def remove_cascade_topology_object(self, topology_object: TopologyObject):
        for link in topology_object.links:
            self.remove_link(link)

        topology_object.links.clear()
        if isinstance(topology_object, Satellite):
            self.simulation.satellites.remove(topology_object)
        elif isinstance(topology_object, GroundStation):
            self.simulation.ground_stations.remove(topology_object)
        elif isinstance(topology_object, UserTerminal):
            self.simulation.user_terminals.remove(topology_object)
        elif isinstance(topology_object, PointOfPresence):
            self.simulation.point_of_presences.remove(topology_object)
        else:
            raise ValueError("Topology object type unknown: " + topology_object.type)

    def remove_cascade_topology_object_by_id(
        self, topology_object_id: int
    ) -> list[TopologyObject]:
        """
        Remove from the simulation topology object and every related dependent objects (links)
        :param topology_object_id: Topology object identifier
        :return: List of every objects removed from this action
        """

        removed_objects = []

        topology_object = self.get_topology_object_from_uniq_id(topology_object_id)

        connected_links = self.get_link_connected_to_topology_object(topology_object)

        removed_objects.append(topology_object)
        removed_objects.extend(connected_links)

        for link in connected_links:
            self.remove_link(link)

        self.__remove_topology_object(topology_object)

        return removed_objects

    def remove_all_terminal_users(self):
        """
        Remove all user terminals from the simulation.
        :return:
        """
        for user_terminal in self.get_user_terminals():
            self.remove_cascade_topology_object(user_terminal)

    def remove_all_ground_stations(self):
        """
        Remove all ground stations from the simulation.
        :return:
        """
        for ground_station in self.get_ground_stations():
            self.remove_cascade_topology_object(ground_station)

    def remove_all_satellites(self):
        """
        Remove all satellites from the simulation.
        :return:
        """
        for satellite in self.get_satellites():
            self.remove_cascade_topology_object(satellite)

    def remove_all_point_of_presences(self):
        """
        Remove all points of presences from the simulation.
        :return:
        """
        for point_of_presence in self.simulation.point_of_presences:
            self.remove_cascade_topology_object(point_of_presence)

    def __update_user_terminal_links_in_static_mode(self):
        """
        This method will disable all ground station link that aren't connected
        :return:
        """
        self.simulation.user_terminal_links.clear()

        self.connect_every_satellite_with_every_ground_stations_and_disable_un_connected()

    def __update_ground_stations_in_static_mode(self):
        """
        This method will disable all ground station link that aren't connected
        :return:
        """
        self.simulation.ground_station_links.clear()

        self.connect_every_satellite_with_every_ground_stations_and_disable_un_connected()

    def __update_user_terminal_links_default(self):
        """
        This method will delete all user terminals links and will create new ones according to the current strategy
        :return:
        """
        for terminal in self.get_user_terminals():
            update_response = self.ground_to_space_connection_strategies.get(
                terminal.ground_object_domain.ground_to_space_connections_strategy
            ).compute_ground_object_connection_strategy(terminal, self.get_satellites())

            for link in update_response.obsolete_links:
                self.remove_link(link)

            for new_connection in update_response.new_ground_object_connections:
                self.create_and_add_user_terminal_link_connection(
                    satellite=new_connection.satellite,
                    user_terminal=terminal,
                    elevation_above_horizon_angle=new_connection.connection_info.get(
                        "elevation_above_horizon", -1
                    ),
                )

    def __update_ground_stations_default(self):
        """
        This method will delete all ground station links and will create new ones according to the current strategy
        :return:
        """
        for ground_station in self.get_ground_stations():
            update_response = self.ground_to_space_connection_strategies.get(
                ground_station.ground_object_domain.ground_to_space_connections_strategy
            ).compute_ground_object_connection_strategy(
                ground_station, self.get_satellites()
            )

            for link in update_response.obsolete_links:
                self.remove_link(link)

            for new_connection in update_response.new_ground_object_connections:
                self.create_and_add_ground_station_link_connection(
                    satellite=new_connection.satellite,
                    ground_station=ground_station,
                    elevation_above_horizon_angle=new_connection.connection_info.get(
                        "elevation_above_horizon", -1
                    ),
                )

    def update_ground_station_links(self):
        """
        Update the ground station links. This will connect ground station to satellites based on their position and their
        range.
        :return:
        """

        if self.static_ground_station_link_mode:
            if len(self.get_ground_stations_links()) == 0:
                self.connect_every_satellite_with_every_ground_stations()

            self.__update_ground_stations_in_static_mode()
        else:
            self.__update_ground_stations_default()

    def update_satellites(self):
        """
        Update the satellites. This will call the update method of each satellite object.
        :return:
        """
        for satellite in self.get_satellites():
            satellite.update()

    def update_ground_stations(self):
        """
        Update the ground stations. This will call the update method of each ground station object.
        :return:
        """
        for ground_station in self.get_ground_stations():
            ground_station.update()

    def update_user_terminal(self):
        """
        Update the user terminal object. This will call the update method of each user terminal object.
        :return:
        """
        for user_terminal in self.get_user_terminals():
            user_terminal.update()

    def update_user_terminal_links(self):
        if self.static_ground_station_link_mode:
            if len(self.get_user_terminal_links()) == 0:
                self.connect_every_satellite_with_every_ground_stations()

            self.__update_user_terminal_links_in_static_mode()
        else:
            self.__update_user_terminal_links_default()

    def add_to_update_protocol(self, callable_update: Callable):
        self.enabled_update_functions.append(callable_update)

    def remove_from_update_protocol(self, callable_remove: Callable):
        self.enabled_update_functions.remove(callable_remove)

    def set_callable_protocol(self, update_callables: list[Callable]):
        self.enabled_update_functions = update_callables

    def get_default_update_protocol(self) -> list[Callable]:
        """
        The default update protocol will update:
        - Satellites
        - GroundStations links
        :return:
        """
        return [
            self.update_satellites,
            self.update_ground_stations,
            self.update_user_terminal,
            self.update_ground_station_links,
            self.update_user_terminal_links,
        ]

    def add_walker_shell(self, walker_shell: WalkerShell):
        self.simulation.walker_shells.append(walker_shell)

    def add_ground_object_domain(self, ground_object_domain: GroundObjectDomain):
        self.simulation.ground_object_domains.append(ground_object_domain)

    def get_walker_shell(self, identifier: str) -> WalkerShell:
        walker_shells_found = [
            walker_shell
            for walker_shell in self.simulation.walker_shells
            if walker_shell.identifier == identifier
        ]
        if len(walker_shells_found) == 1:
            return walker_shells_found[0]

        elif len(walker_shells_found) == 0:
            raise WalkerShellNotFoundError("No walker shell found")
        else:
            raise ValueError("Multiple walker shells found with the same identifier")

    def get_ground_object_domain(self, identifier: str) -> GroundObjectDomain:
        ground_object_domains_found = [
            ground_object_domain
            for ground_object_domain in self.simulation.ground_object_domains
            if ground_object_domain.identifier == identifier
        ]
        if len(ground_object_domains_found) == 1:
            return ground_object_domains_found[0]

        elif len(ground_object_domains_found) == 0:
            raise GroundObjectDomainNotFoundError("No Ground Domain found")
        else:
            raise ValueError("Multiple found object found with the same identifier")

    def get_point_of_presences(self):
        return self.simulation.point_of_presences
