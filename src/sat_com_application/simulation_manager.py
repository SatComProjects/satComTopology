from sat_com_model.exceptions import TopologyObjectNotFoundError, LinkNotFoundError
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
)


def get_object_by_object_id(
    object_id: int, topology_objects: list
) -> Satellite | GroundStation | UserTerminal:
    """
    Return the topology object matching its object_id
    :param object_id: the object identifier (satellite.object_id, ground_station.object_id, etc.)
    :param topology_objects: The list of objects from its type /!\\ SHOULDN'T BE A LIST OF TOPOLOGY_OBJECT
    :return:
    """
    matching_objects_iterator = filter(
        lambda x: x.object_id == object_id, topology_objects
    )
    matched_object = list(matching_objects_iterator)

    if len(matched_object) == 1:
        return matched_object[0]

    if len(matched_object) > 1:
        raise Exception()

    if len(matched_object) == 0:
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

    simulation: Simulation

    def __init__(self, simulation: Simulation):
        self.simulation = simulation

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
        Add ground station to the simulation. Automatically attribute a uniq topology id.
        :param ground_station: Ground station instance to add
        :return:
        """
        ground_station.topology_uniq_id = self.simulation.request_an_id()
        self.simulation.ground_stations.append(ground_station)

    def add_user_terminals(self, user_terminal: UserTerminal):
        """
        Add user terminals to the simulation. Automatically attribute a uniq topology id
        :param user_terminal: User terminal instance to add
        :return:
        """
        user_terminal.topology_uniq_id = self.simulation.request_an_id()
        self.simulation.user_terminals.append(user_terminal)

    def get_all_topology_objects(self) -> list[TopologyObject]:
        """
        Get all topology objects from the simulation.
        :return: List of topology objects
        """
        return self.simulation.get_all_topology_objects()

    def get_all_links(self) -> list[Link]:
        """
        Get all links of the simulation.
        :return: List of links
        """
        all_links = []
        all_links.extend(self.simulation.inter_satellite_links)
        all_links.extend(self.simulation.ground_station_links)
        all_links.extend(self.simulation.user_terminal_links)

        return all_links

    def get_satellite_by_object_id(self, object_id: int) -> Satellite:
        """
        Get satellite by its object id. (Satellite identifier)
        :param object_id:  Satellite identifier
        :return: Satellite instance
        """
        return get_object_by_object_id(object_id, self.simulation.satellites)

    def get_ground_station_by_object_id(self, object_id: int) -> GroundStation:
        """
        Get ground station by its object id. (Ground station identifier)
        :param object_id:  Ground station identifier
        :return: Ground station instance
        """
        return get_object_by_object_id(object_id, self.simulation.ground_stations)

    def get_user_terminal_by_object_id(self, object_id: int) -> UserTerminal:
        """
        Get user terminal by its object id. (User terminal identifier)
        :param object_id: User terminal identifier
        :return: User terminal instance
        """
        return get_object_by_object_id(object_id, self.simulation.user_terminals)

    def get_topology_object_from_uniq_id(self, uniq_id: int) -> TopologyObject:
        """
        Get any topology object from its uniq id. (Topology identifier)
        :param uniq_id: Unique identifier
        :return: Topology instance
        """
        matching_objects_iterator = filter(
            lambda x: x.topology_uniq_id == uniq_id,
            self.get_all_topology_objects(),
        )
        matched_object = list(matching_objects_iterator)

        if len(matched_object) == 1:
            return matched_object[0]

        if len(matched_object) > 1:
            raise Exception()

        if len(matched_object) == 0:
            raise TopologyObjectNotFoundError()

    def create_inter_satellite_link_connection(
        self, satellite_a: Satellite, satellite_b: Satellite
    ) -> InterSatelliteLink:
        """
        Create inter satellite link between two satellites
        :param satellite_a: Satellite instance A
        :param satellite_b: Satellite instance B
        :return: InterSatelliteLink instance
        """
        inter_satellite_link = InterSatelliteLink()
        inter_satellite_link.connect(satellite_a, satellite_b)

        self.simulation.inter_satellite_links.append(inter_satellite_link)
        return inter_satellite_link

    def create_ground_station_link_connection(
        self, satellite: Satellite, ground_station: GroundStation
    ) -> GroundStationLink:
        """
        Create ground station link between a satellite and a ground station
        :param satellite: Satellite instance
        :param ground_station: GroundStation instance
        :return: GroundStationLink instance
        """
        ground_station_link = GroundStationLink()
        ground_station_link.connect(satellite, ground_station)

        self.simulation.ground_station_links.append(ground_station_link)
        return ground_station_link

    def create_user_terminal_link_connection(
        self, satellite: Satellite, user_terminal: UserTerminal
    ) -> UserTerminalLink:
        """
        Create user terminal link between a satellite and a user terminal
        :param satellite: Satellite instance
        :param user_terminal: User terminal instance
        :return: UserTerminalLink instance
        """
        user_terminal_link = UserTerminalLink()
        user_terminal_link.connect(satellite, user_terminal)

        self.simulation.user_terminal_links.append(user_terminal_link)
        return user_terminal_link

    def add_all_satellites(self, satellites: list[Satellite]):
        """
        Add all satellites to the simulation from a list in argument
        :param satellites: List of satellites to add
        :return: List of satellite
        """
        for satellite in satellites:
            self.add_satellite(satellite)

    def add_all_ground_stations(self, ground_stations: list[GroundStation]):
        """
        Add all ground to the simulation from a list in argument
        :param ground_stations: List of ground stations to add
        :return: List of ground station
        """
        for ground_station in ground_stations:
            self.add_ground_station(ground_station)

    def get_ascending_satellites(self) -> list[Satellite]:
        """
        Return all satellites in ascending phase
        :return: List of satellites
        """
        return list(
            filter(
                lambda satellite: satellite.is_ascending(),
                self.simulation.satellites,
            )
        )

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

    def get_descending_satellites(self) -> list[Satellite]:
        """
        Get all simulation descending satellites
        :return: List of descending satellites
        """
        return list(
            filter(
                lambda satellite: not satellite.is_ascending(),
                self.simulation.satellites,
            )
        )

    def get_distance_between_two_topology_object_km(
        self, object_1: TopologyObject, object_2: TopologyObject
    ) -> float:
        """
        Get distance between two topology object in km.
        :param object_1: Topology object A
        :param object_2: Topology object  B
        :return: float: Distance between two topology objects
        """
        return self.simulation.get_distance_model().get_distance_km(
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

        closest_satellite = None
        best_distance = None

        for satellite in satellites_to_filter:
            distance_in_km = self.get_distance_between_two_topology_object_km(
                ground_station, satellite
            )

            if best_distance is None:
                best_distance = distance_in_km
                closest_satellite = satellite
            else:
                if best_distance > distance_in_km:
                    best_distance = distance_in_km
                    closest_satellite = satellite

        return closest_satellite

    def get_ground_station_links_connected_to_a_ground_station(
        self, ground_station_id: int
    ) -> [GroundStationLink]:
        """
        Return all ground station links connected to a ground station
        :param ground_station_id:
        :return:
        """
        return list(
            filter(
                lambda ground_station_link: ground_station_link_is_connected_to_ground_station(
                    ground_station_link, ground_station_id
                ),
                self.simulation.ground_station_links,
            )
        )

    def remove_ground_station_link(self, ground_station_link: GroundStationLink):
        """
        Remove a Ground Station link
        :param ground_station_link: Ground Station Link to remove
        :return:
        """
        self.simulation.ground_station_links.remove(ground_station_link)

    def remove_all_ground_station_links(
        self, ground_station_links: [GroundStationLink]
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
        :param topology_object_a: Topology object source
        :param topology_object_b: Topology object destination
        :return: Link connecting two topology objects, raise LinkNotFoundError if not found
        """
        for link in self.get_all_links():
            if (
                link.source.topology_uniq_id == topology_object_a.topology_uniq_id
                and link.destination.topology_uniq_id
                == topology_object_b.topology_uniq_id
            ) or (
                link.source.topology_uniq_id == topology_object_b.topology_uniq_id
                and link.destination.topology_uniq_id
                == topology_object_a.topology_uniq_id
            ):
                return link

        raise LinkNotFoundError()

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
