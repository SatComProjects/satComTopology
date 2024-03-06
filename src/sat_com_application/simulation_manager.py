from sat_com_model.exceptions import TopologyObjectNotFoundError
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
        satellite.topology_uniq_id = self.simulation.request_an_id()
        self.simulation.satellites.append(satellite)

    def add_ground_station(self, ground_station: GroundStation):
        ground_station.topology_uniq_id = self.simulation.request_an_id()
        self.simulation.ground_stations.append(ground_station)

    def add_user_terminals(self, user_terminal: UserTerminal):
        user_terminal.topology_uniq_id = self.simulation.request_an_id()
        self.simulation.user_terminals.append(user_terminal)

    def get_all_topology_objects(self) -> list[TopologyObject]:
        return self.simulation.get_all_topology_objects()

    def get_all_links(self) -> list[Link]:
        all_links = []
        all_links.extend(self.simulation.inter_satellite_links)
        all_links.extend(self.simulation.ground_station_links)
        all_links.extend(self.simulation.user_terminal_links)

        return all_links

    def get_satellite_by_object_id(self, object_id: int) -> Satellite:
        return get_object_by_object_id(object_id, self.simulation.satellites)

    def get_ground_station_by_object_id(self, object_id: int) -> GroundStation:
        return get_object_by_object_id(object_id, self.simulation.ground_stations)

    def get_user_terminal_by_object_id(self, object_id: int) -> UserTerminal:
        return get_object_by_object_id(object_id, self.simulation.user_terminals)

    def get_topology_object_from_uniq_id(self, uniq_id: int) -> TopologyObject:
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
        inter_satellite_link = InterSatelliteLink()
        inter_satellite_link.connect(satellite_a, satellite_b)

        self.simulation.inter_satellite_links.append(inter_satellite_link)
        return inter_satellite_link

    def create_ground_station_link_connection(
        self, satellite: Satellite, ground_station: GroundStation
    ) -> GroundStationLink:
        ground_station_link = GroundStationLink()
        ground_station_link.connect(satellite, ground_station)

        self.simulation.ground_station_links.append(ground_station_link)
        return ground_station_link

    def create_user_terminal_link_connection(
        self, satellite: Satellite, user_terminal: UserTerminal
    ) -> UserTerminalLink:
        user_terminal_link = UserTerminalLink()
        user_terminal_link.connect(satellite, user_terminal)

        self.simulation.user_terminal_links.append(user_terminal_link)
        return user_terminal_link

    def add_all_satellites(self, satellites: list[Satellite]):
        for satellite in satellites:
            self.add_satellite(satellite)

    def add_all_ground_stations(self, ground_stations: list[GroundStation]):
        for ground_station in ground_stations:
            self.add_ground_station(ground_station)

    def get_ascending_satellites(self):
        return list(
            filter(
                lambda satellite: satellite.is_ascending(),
                self.simulation.satellites,
            )
        )

    def get_descending_satellites(self):
        return list(
            filter(
                lambda satellite: not satellite.is_ascending(),
                self.simulation.satellites,
            )
        )

    def get_distance_between_two_topology_object_km(
        self, object_1: TopologyObject, object_2: TopologyObject
    ) -> float:
        return self.simulation.get_distance_model().get_distance_km(
            object_1.get_coordinates(), object_2.get_coordinates()
        )

    def get_closest_satellite(
        self,
        ground_station: GroundStation,
        orbit_direction: str = None,
    ) -> Satellite:
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

    def get_ground_station_link_connected_to_a_ground_station(
        self, ground_station_id: int
    ) -> [GroundStationLink]:
        return list(
            filter(
                lambda ground_station_link: ground_station_link_is_connected_to_ground_station(
                    ground_station_link, ground_station_id
                ),
                self.simulation.ground_station_links,
            )
        )
