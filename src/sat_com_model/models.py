from enum import Enum

from .exceptions import (
    InterSatelliteConnectionError,
    GroundStationConnectionError,
    UserTerminalConnectionError,
    ConnectionBetweenSameSatelliteForbiddenError,
    TopologyIdentifierNotDefinedError,
    OrbitalObjectMovementModelUndefinedError,
    DistanceModelUndefinedError,
)


class InterSatelliteLinkDirection(Enum):
    ORBITAL = 1
    ADJACENT = 2
    UNDEFINED = 3


class SpatialPosition:
    longitude: float
    latitude: float
    altitude: float

    def __init__(
        self, longitude: float = None, latitude: float = None, altitude: float = None
    ):
        self.longitude = longitude
        self.latitude = latitude
        self.altitude = altitude

    def __str__(self):
        return f"Longitude: {self.longitude}, Latitude: {self.latitude}, Altitude: {self.altitude}"


class SpatialPoint:
    """
    This is the lower element of the stack. Every element in the topology has a position
    """

    spatial_position: SpatialPosition

    simulation_context: "Simulation"

    def __init__(self):
        self.spatial_position = SpatialPosition()

    def __str__(self):
        return self.spatial_position.__str__()

    def get_coordinates(self) -> SpatialPosition:
        """
        Get the object coordinates. The default format is longitude, latitude and elevation.
        :return:
        """
        return self.spatial_position

    def set_position(self, **kwargs):
        """
        Set the position of the spatial point
        :param kwargs: latitude, longitude, altitude. If one of them is empty, value will remain the same
        :return:
        """
        self.spatial_position.latitude = kwargs.get(
            "latitude", self.spatial_position.latitude
        )
        self.spatial_position.longitude = kwargs.get(
            "longitude", self.spatial_position.longitude
        )
        self.spatial_position.altitude = kwargs.get(
            "altitude", self.spatial_position.altitude
        )


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

    def get_longitude_latitude(self) -> SpatialPosition:
        """
        Return the longitude, latitude  and elevation on ground of the orbital object
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
        """
        Return the movement mode. Mandatory if you want to calculate position of an orbital object
        :return:
        """
        if self.movement_model is None:
            raise OrbitalObjectMovementModelUndefinedError(
                "You can't use movement features because you didn't specify a movement model"
            )
        return self.movement_model

    def is_ascending(self) -> bool:
        """
        Return if the orbital object is in ascending phase or descending phase
        :return:
        """
        return self.get_movement_model().is_ascending()

    def get_coordinates(self) -> SpatialPosition:
        """
        Get the object coordinates. The default format is longitude, latitude and elevation.
        :return:
        """

        return self.get_movement_model().get_longitude_latitude()

    def update(self):
        self.spatial_position = self.get_coordinates()


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
        super().__init__()
        self.city = city_name
        self.spatial_position.longitude = 0
        self.spatial_position.latitude = 0
        self.spatial_position.altitude = 0

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

    inter_satellite_direction: InterSatelliteLinkDirection

    def connect(
        self,
        source: TopologyObject,
        destination: TopologyObject,
        inter_satellite_direction: InterSatelliteLinkDirection = InterSatelliteLinkDirection.UNDEFINED,
    ):
        object_are_both_satellites = isinstance(source, Satellite) and isinstance(
            destination, Satellite
        )
        if not object_are_both_satellites:
            raise InterSatelliteConnectionError(
                "You cannot use InterSatellite connection between these two object : {source} - {destination} ".format(
                    source=source.__class__, destination=destination.__class__
                )
            )
        self.inter_satellite_direction = inter_satellite_direction

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


class DistanceModel:
    def get_distance_meters(
        self, spatial_position_1: SpatialPosition, spatial_position_2: SpatialPosition
    ) -> float:
        pass

    def get_distance_km(
        self, spatial_position_1: SpatialPosition, spatial_position_2: SpatialPosition
    ) -> float:
        pass


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


class Simulation:
    object_uuid_index: int

    simulation_name: str

    satellites: list[Satellite]
    inter_satellite_links: list[InterSatelliteLink]

    ground_stations: list[GroundStation]
    ground_station_links: list[GroundStationLink]

    user_terminals: list[UserTerminal]
    user_terminal_links: list[UserTerminalLink]

    distance_model: DistanceModel = None

    def __init__(self):
        self.simulation_name = "Unknown"
        self.object_uuid_index = 0
        self.satellites = []
        self.inter_satellite_links = []
        self.ground_stations = []
        self.ground_station_links = []
        self.user_terminals = []
        self.user_terminal_links = []

    def get_distance_model(self) -> DistanceModel:
        if self.distance_model is None:
            raise DistanceModelUndefinedError()
        return self.distance_model

    def set_distance_model(self, distance_model: DistanceModel):
        self.distance_model = distance_model

    def request_an_id(self):
        attributed_id = self.object_uuid_index
        self.object_uuid_index += 1

        return attributed_id

    def get_all_topology_objects(self) -> list[TopologyObject]:
        topology_objects = []
        topology_objects.extend(self.satellites)
        topology_objects.extend(self.ground_stations)
        topology_objects.extend(self.user_terminals)

        return topology_objects

    def update(self):
        for topology_object in self.get_all_topology_objects():
            topology_object.update()


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
