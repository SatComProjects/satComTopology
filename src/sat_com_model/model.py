from .exception import (
    InterSatelliteConnectionError,
    GroundStationConnectionError,
    UserTerminalConnectionError,
    SimulationContextError,
    ConnectionBetweenSameSatelliteForbiddenError,
)


class SpatialPoint:
    """
    This is the lower element of the stack. Every element in the topology has a position
    """

    longitude: float
    latitude: float
    altitude: float

    def get_position(self) -> (float, float, float):
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

    object_name: str
    id: int
    type = "TypologyObject"

    def get_type(self) -> str:
        return self.type

    def __eq__(self, __value):
        if isinstance(__value, self.__class__) and self.id == __value.id:
            return True
        return False


class OrbitalObject(TopologyObject):
    """
    Any object in orbit
    """

    tle: str
    orbital_object_id: int


class Satellite(OrbitalObject):
    satellite_name: str
    satellite_id: int
    type = "Satellite"


class GroundObject(TopologyObject):
    pass


class GroundStation(GroundObject):
    ground_station_id: int
    city: str

    type = "GroundStation"


class UserTerminal(GroundObject):
    user_id: int
    user_name: str

    type = "UserTerminal"


class Link:
    """
    This is the communication Link
    Todo: maybe we should directly connect interface here
    """

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
    def connect(self, source: TopologyObject, destination: TopologyObject):
        object_are_both_satellites = isinstance(source, Satellite) and isinstance(
            destination, Satellite
        )
        if not object_are_both_satellites:
            raise InterSatelliteConnectionError(
                "You cannot use InterSatellite connection between these two object : {source} - {destination} ".format(
                    source=source.get_type(), destination=destination.get_type()
                )
            )

        super().connect(source, destination)


class GroundStationLink(Link):
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


class Simulation:
    available_id_index: int = 0

    topology_objects: list[TopologyObject]

    connection_links: list[Link]

    def __init__(self):
        self.topology_objects = []
        self.connection_links = []

    def request_an_id(self):
        attributed_id = self.available_id_index
        self.available_id_index += 1

        return attributed_id

    def get_object_from_type(self, object_type):
        return filter(
            lambda t_object: isinstance(t_object, object_type),
            self.topology_objects,
        )

    def get_satellites(self, satellite_id: int) -> Satellite:
        return filter(
            lambda t_object: t_object.satellite_id == satellite_id,
            self.get_object_from_type(Satellite),
        )

    def create_bi_directional_connection(self, satellite_a, satellite_b):
        isl = InterSatelliteLink()
        isl.connect(satellite_a, satellite_b)
        isl.connect(satellite_b, satellite_a)

        self.connection_links.append(isl)
        return isl


def create_satellite(
    simulation_context: Simulation, satellite_name, satellite_id
) -> Satellite:
    """
    Create a satellite with parameters
    todo: check what we have to put inside a satellite object
    :param simulation_context: REQUIRED SIMULATION, very important to identify our future satellite.
    :param satellite_name: Name of the satellite
    :param satellite_id: Identifier of the satellite
    :return:
    """
    if simulation_context is None:
        raise SimulationContextError()

    created_satellite = Satellite()

    created_satellite.satellite_id = satellite_id
    created_satellite.satellite_name = satellite_name
    created_satellite.id = simulation_context.request_an_id()

    return created_satellite


def create_ground_station(
    simulation_context: Simulation, ground_station_id: int, city: str
) -> GroundStation:
    """
    Create a ground station
    :param simulation_context: REQUIRED SIMULATION, very important to identify our future satellite.
    :param ground_station_id: identifier of the ground station
    :param city: position of the ground station (closest city)
    :return:
    """
    if simulation_context is None:
        raise SimulationContextError()

    created_ground_station = GroundStation()
    created_ground_station.id = simulation_context.request_an_id()
    created_ground_station.city = city
    created_ground_station.ground_station_id = ground_station_id

    return created_ground_station


def create_user_terminal(
    simulation_context: Simulation, user_id, username
) -> UserTerminal:
    """
    Create a user terminal
    :param username: username
    :param simulation_context: REQUIRED SIMULATION, very important to identify our future satellite.
    :param user_id: identifier of the user
    :return:
    """
    if simulation_context is None:
        raise SimulationContextError()

    created_user = UserTerminal()
    created_user.id = simulation_context.request_an_id()
    created_user.user_name = username
    created_user.user_id = user_id

    return created_user
