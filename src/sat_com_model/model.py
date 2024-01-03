from enum import Enum

from .exception import (
    InterSatelliteConnectionError,
    GroundStationConnectionError,
    UserTerminalConnectionError,
    SimulationContextError,
    ConnectionBetweenSameSatelliteForbiddenError,
    TopologyObjectNotFoundError,
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
        coordinate = f"Coordinate : Longitude: {self.longitude}, Latitude: {self.latitude} Altitude: {self.altitude}"
        return coordinate

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

    id: int
    type = "TypologyObject"

    def get_type(self) -> str:
        return self.type

    def __str__(self):
        topology_object_info = "id: {id}, type: {type}".format(
            id=self.id, type=self.type
        )
        return super().__str__().join(topology_object_info)


class MovementModel:
    """
    This is the movement model class. This abstract class should be implemented using a orbit trajectory
    library. You have to respect 2 things: Giving TLE in entry, and implementing methods.
    """

    tle: str

    def __init__(self, tle: str) -> None:
        self.tle = tle

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

    tle: str

    movement_model: MovementModel

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

    def get_movement_model(self) -> MovementModel:
        if self.movement_model is None:
            raise ValueError(
                "You can't use movement features because you didn't specify a movement model"
            )
        return self.movement_model

    def is_ascending(self) -> bool:
        return self.get_movement_model().is_ascending()

    def get_position(self) -> (float, float, float):
        return self.get_movement_model().get_longitude_latitude()


class Satellite(OrbitalObject):
    satellite_name: str
    satellite_id: int
    type = "Satellite"

    def __str__(self):
        return (
            super().__str__()
            + "Satellite name: {satellite_name} satellite_id: {satellite_id} ".format(
                satellite_name=self.satellite_name, satellite_id=self.satellite_id
            )
        )


class GroundObject(TopologyObject):
    pass


class GroundStation(GroundObject):
    ground_station_id: int
    city: str

    type = "GroundStation"

    def __str__(self):
        return (
            super().__str__()
            + "Ground station id: {ground_station_id} city: {city} ".format(
                ground_station_id=self.ground_station_id, city=self.city
            )
        )


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
                    source=source.__class__, destination=destination.__class__
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

    def get_objects_from_type(self, object_type) -> list:
        return list(
            filter(
                lambda t_object: isinstance(t_object, object_type),
                self.topology_objects,
            )
        )

    def get_satellite(self, satellite_id) -> Satellite:
        matched_satellite = list(
            filter(
                lambda t_object: t_object.satellite_id == satellite_id,
                self.get_objects_from_type(Satellite),
            )
        )

        if len(matched_satellite) < 1:
            raise TopologyObjectNotFoundError()

        return matched_satellite[0]

    def create_bi_directional_isl_connection(
        self, satellite_a: Satellite, satellite_b: Satellite
    ):
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
