from enum import Enum

from .exception import (
    InterSatelliteConnectionError,
    GroundStationConnectionError,
    UserTerminalConnectionError,
    ConnectionBetweenSameSatelliteForbiddenError,
    TopologyObjectNotFoundError,
    TopologyIdentifierNotDefinedError,
    OrbitalObjectMovementModelUndefinedError,
)

IslDirection = Enum("IslDirection", ["TOP", "BACK", "ADJACENT", "UNDEFINED"])


class SpatialPoint:
    """
    This is the lower element of the stack. Every element in the topology has a position
    """

    longitude: float
    latitude: float
    altitude: float

    simulation_context: "Simulation"

    def __str__(self):
        longitude, latitude, altitude = self.get_coordinates()
        coordinate = f"Coordinate : Longitude: {longitude}, Latitude: {latitude} Altitude: {altitude}"
        return coordinate

    def get_coordinates(self) -> (float, float, float):
        return self.longitude, self.latitude, self.altitude

    def set_position(self, **kwargs):
        """
        Set the position of the spatial point
        :param kwargs: latitude, longitude, altitude. If one of them is empty, value will remain the same
        :return:
        """
        self.latitude = kwargs.get("latitude", self.latitude)
        self.longitude = kwargs.get("longitude", self.longitude)
        self.altitude = kwargs.get("altitude", self.altitude)


class TopologyObject(SpatialPoint):
    """
    Any Object in the topology
    """

    """Identifier provided by the simulator (uniq for avery topology object)"""
    topology_uniq_id: int = None

    """Identifier given by the data provider (ex: satellite identifier, uniq for every satellite)"""
    object_id: int = None

    """This is the object type as string, used for debugging and export purposes"""
    type = "TypologyObject"

    def get_type(self) -> str:
        return self.type

    def __str__(self):
        topology_object_info = "id: {id}, type: {type}".format(
            id=self.topology_uniq_id, type=self.type
        )
        return super().__str__() + topology_object_info

    def get_topology_uniq_id(self) -> int:
        if self.topology_uniq_id is not None:
            return self.topology_uniq_id
        else:
            raise TopologyIdentifierNotDefinedError()

    def update(self):
        """
        Update everything who need to be updated on the topology. Ex: coordinates
        :return:
        """
        pass


class MovementModel:
    """
    This is the movement model class. This abstract class should be implemented using a orbit trajectory
    library.
    """

    def is_ascending(self) -> bool:
        """
        Return True if the Orbital object is in its ascending phase.
        :return:
        """
        pass

    def get_longitude_latitude(self) -> (float, float, float):
        """
        Return the longitude, latitude  and elevation on ground of the orbital object
        :param date: Specify the date at which time you want the position
        :return:
        """
        pass

    def get_position_earth_general_inertial(self) -> (float, float, float):
        """
        This method returns the position of the orbital object in the referential of EGI.
        It can be used in the is_ascending method.
        :return:
        """
        pass


class OrbitalObject(TopologyObject):
    """
    Any object in orbit
    """

    movement_model: MovementModel = None

    def __str__(self):
        return super().__str__()

    def set_movement_model(self, movement_model: MovementModel):
        """
        Movement model is an abstract class. You have to implement your movement model class depending on
        what library you want to use. For example : pyorbital. The objective is to define a class that will
        give the MovementModel methods

        :param movement_model: Your implementation of MovementModel
        :return:
        """
        self.movement_model = movement_model
        self.update()

    def get_movement_model(self) -> MovementModel:
        if self.movement_model is None:
            raise OrbitalObjectMovementModelUndefinedError(
                "You can't use movement features because you didn't specify a movement model"
            )
        return self.movement_model

    def is_ascending(self) -> bool:
        return self.get_movement_model().is_ascending()

    def get_coordinates(self) -> (float, float, float):
        return self.get_movement_model().get_longitude_latitude()

    def update(self):
        self.longitude, self.latitude, self.altitude = self.get_coordinates()


class Satellite(OrbitalObject):
    satellite_name: str
    type = "Satellite"

    def __str__(self):
        return (
            super().__str__()
            + "Satellite name: {satellite_name} satellite_id: {satellite_id} ".format(
                satellite_name=self.satellite_name, satellite_id=self.object_id
            )
        )


class GroundObject(TopologyObject):
    pass


class GroundStation(GroundObject):
    city: str

    type = "GroundStation"

    def __init__(self, city_name: str = "unknown"):
        self.city = city_name
        self.longitude = 0
        self.latitude = 0
        self.altitude = 0

    def __str__(self):
        return (
            super().__str__()
            + "Ground station id: {ground_station_id} city: {city} ".format(
                ground_station_id=self.object_id, city=self.city
            )
        )


class UserTerminal(GroundObject):
    user_name: str

    type = "UserTerminal"


class Link:
    """
    This is the communication Link
    Todo: maybe we should directly connect interface here
    """

    type: str
    source: TopologyObject = None
    destination: TopologyObject = None

    def connect(self, source: TopologyObject, destination: TopologyObject):
        if source == destination:
            raise ConnectionBetweenSameSatelliteForbiddenError(
                "You cannot connect with same source and destination"
            )
        self.source = source
        self.destination = destination


class InterSatelliteLink(Link):
    type = "InterSatelliteLink"

    def connect(self, source: TopologyObject, destination: TopologyObject):
        object_are_both_satellites = isinstance(source, Satellite) and isinstance(
            destination, Satellite
        )
        if not object_are_both_satellites:
            raise InterSatelliteConnectionError(
                "You cannot use InterSatellite connection between these two object : {source} - {destination} ".format(
                    source=source.__class__, destination=destination.__class__
                )
            )

        super().connect(source, destination)


class GroundStationLink(Link):
    type = "GroundStationLink"

    def connect(self, source: TopologyObject, destination: TopologyObject):
        object_source_is_a_gsl_and_destination_a_satellite = isinstance(
            source, GroundStation
        ) and isinstance(destination, Satellite)

        object_source_is_a_satellite_and_destination_a_gsl = isinstance(
            source, Satellite
        ) and isinstance(destination, GroundStation)

        cant_connect = (
            not object_source_is_a_gsl_and_destination_a_satellite
            and not object_source_is_a_satellite_and_destination_a_gsl
        )

        if cant_connect:
            raise GroundStationConnectionError()

        super().connect(source, destination)


class UserTerminalLink(Link):
    link = "UserTerminalLink"

    def connect(self, source: TopologyObject, destination: TopologyObject):
        object_source_is_a_user_and_destination_a_satellite = isinstance(
            source, UserTerminal
        ) and isinstance(destination, Satellite)

        object_source_is_a_satellite_and_destination_a_user = isinstance(
            source, Satellite
        ) and isinstance(destination, UserTerminal)

        cant_connect = (
            not object_source_is_a_user_and_destination_a_satellite
            and not object_source_is_a_satellite_and_destination_a_user
        )

        if cant_connect:
            raise UserTerminalConnectionError()

        super().connect(source, destination)


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


class Simulation:
    object_uuid_index: int

    satellites: list[Satellite]
    inter_satellite_links: list[InterSatelliteLink]

    ground_stations: list[GroundStation]
    ground_station_links: list[GroundStationLink]

    user_terminals: list[UserTerminal]
    user_terminal_links: list[UserTerminalLink]

    def __init__(self):
        self.object_uuid_index = 0
        self.satellites = []
        self.inter_satellite_links = []
        self.ground_stations = []
        self.ground_station_links = []
        self.user_terminals = []
        self.user_terminal_links = []

    def request_an_id(self):
        attributed_id = self.object_uuid_index
        self.object_uuid_index += 1

        return attributed_id

    def add_satellite(self, satellite: Satellite):
        satellite.topology_uniq_id = self.request_an_id()
        self.satellites.append(satellite)

    def add_ground_station(self, ground_station: GroundStation):
        ground_station.topology_uniq_id = self.request_an_id()
        self.ground_stations.append(ground_station)

    def add_user_terminals(self, user_terminal: UserTerminal):
        user_terminal.topology_uniq_id = self.request_an_id()
        self.user_terminals.append(user_terminal)

    def get_all_topology_objects(self) -> list[TopologyObject]:
        topology_objects = []
        topology_objects.extend(self.satellites)
        topology_objects.extend(self.ground_stations)
        topology_objects.extend(self.user_terminals)

        return topology_objects

    def get_all_links(self) -> list[Link]:
        all_links = []
        all_links.extend(self.user_terminal_links)
        all_links.extend(self.ground_station_links)
        all_links.extend(self.user_terminal_links)

        return all_links

    def get_satellite_by_object_id(self, object_id: int) -> Satellite:
        return get_object_by_object_id(object_id, self.satellites)

    def get_ground_station_by_object_id(self, object_id: int) -> GroundStation:
        return get_object_by_object_id(object_id, self.ground_stations)

    def get_user_terminal_by_object_id(self, object_id: int) -> UserTerminal:
        return get_object_by_object_id(object_id, self.user_terminals)

    def get_topology_object_from_uniq_id(self, uniq_id: int) -> TopologyObject:
        matching_objects_iterator = filter(
            lambda x: x.topology_uniq_id == uniq_id, self.get_all_topology_objects()
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

        self.inter_satellite_links.append(inter_satellite_link)
        return inter_satellite_link

    def create_ground_station_link_connection(
        self, satellite: Satellite, ground_station: GroundStation
    ) -> GroundStationLink:
        ground_station_link = GroundStationLink()
        ground_station_link.connect(satellite, ground_station)

        self.ground_station_links.append(ground_station_link)
        return ground_station_link

    def create_user_terminal_link_connection(
        self, satellite: Satellite, user_terminal: UserTerminal
    ) -> UserTerminalLink:
        user_terminal_link = UserTerminalLink()
        user_terminal_link.connect(satellite, user_terminal)

        self.user_terminal_links.append(user_terminal_link)
        return user_terminal_link

    def add_all_satellites(self, satellites: list[Satellite]):
        for satellite in satellites:
            self.add_satellite(satellite)

    def add_all_ground_stations(self, ground_stations: list[GroundStation]):
        for ground_station in ground_stations:
            self.add_ground_station(ground_station)


def create_satellite(satellite_name, satellite_id) -> Satellite:
    """
    Create a satellite with parameters
    todo: check what we have to put inside a satellite object
    :param satellite_name: Name of the satellite
    :param satellite_id: Identifier of the satellite
    :return:
    """
    created_satellite = Satellite()

    created_satellite.object_id = satellite_id
    created_satellite.satellite_name = satellite_name

    return created_satellite


def create_ground_station(ground_station_id: int) -> GroundStation:
    """
    Create a ground station
    :param ground_station_id: identifier of the ground station
    :return:
    """
    created_ground_station = GroundStation()
    created_ground_station.object_id = ground_station_id

    return created_ground_station


def create_user_terminal(user_id, username) -> UserTerminal:
    """
    Create a user terminal
    :param username: username
    :param user_id: identifier of the user
    :return:
    """

    created_user = UserTerminal()
    created_user.user_name = username
    created_user.object_id = user_id

    return created_user
