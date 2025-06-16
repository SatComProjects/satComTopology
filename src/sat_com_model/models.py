import abc
from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, List, Tuple, Dict
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict, computed_field

from .exceptions import (
    InterSatelliteConnectionError,
    GroundStationConnectionError,
    UserTerminalConnectionError,
    ConnectionBetweenSameSatelliteForbiddenError,
    TopologyIdentifierNotDefinedError,
    OrbitalObjectMovementModelUndefinedError,
    DistanceModelUndefinedError,
    GroundObjectLinkConnectionError,
    ConnectionBetweenSameTopologyForbiddenError,
)


class InterSatelliteLinkDirection(Enum):
    ORBITAL = 1
    ADJACENT = 2
    UNDEFINED = 3


class SpatialPosition(BaseModel):
    longitude: float = Field(default=None)
    latitude: float = Field(default=None)
    altitude: float = Field(default=None)

    def to_longitude_latitude(self) -> (float, float):
        return self.longitude, self.latitude

    def to_latitude_longitude(self) -> (float, float):
        return self.latitude, self.longitude

    def to_longitude_latitude_altitude(self) -> (float, float, float):
        return self.longitude, self.latitude, self.altitude

    def to_latitude_longitude_altitude(self) -> (float, float, float):
        return self.latitude, self.longitude, self.altitude

    def __str__(self):
        return f"Longitude: {self.longitude}, Latitude: {self.latitude}, Altitude: {self.altitude}"


class SpatialPoint(BaseModel):
    """
    This is the lower element of the stack. Every element in the topology has a position
    """

    spatial_position_info: SpatialPosition = Field(default_factory=SpatialPosition)

    @property
    def spatial_position(self):
        return self.spatial_position_info

    @spatial_position.setter
    def spatial_position(self, value):
        self.spatial_position_info = value

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
    topology_uniq_id: int = Field(default=None)

    """"""
    domain: str = Field(default="public")

    """Identifier given by the data provider (ex: satellite identifier, uniq for every satellite)"""
    object_id: int = Field(default=None)

    """This is the object type as string, used for debugging and export purposes"""
    type: str = Field(default="TypologyObject", frozen=True)

    """These are the links that this object has with other objects in the topology"""
    links: List["Link"] = Field(default_factory=list, exclude=True, repr=False)

    @computed_field
    @property
    def current_number_of_link(self) -> int:
        return len(self.links)

    @property
    def domain_id(self) -> str:
        return (
            "{affiliation_business}-{object_id}".format(
                affiliation_business=self.domain, object_id=self.object_id
            )
            .lower()
            .replace(" ", "-")
        )

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

    def __eq__(self, other):
        if not isinstance(other, TopologyObject):
            return False
        return self.topology_uniq_id == other.topology_uniq_id

    def update(self):
        """
        Update everything who need to be updated on the topology. Ex: coordinates
        :return:
        """
        pass


class MovementModel(ABC):
    """
    This is the movement model class. This abstract class should be implemented using an orbit trajectory
    library.
    """

    @abstractmethod
    def is_ascending(self) -> bool:
        """
        Return True if the Orbital object is in its ascending phase.
        :return:
        """
        pass

    @abstractmethod
    def get_longitude_latitude(self) -> SpatialPosition:
        """
        Return the longitude, latitude  and elevation on ground of the orbital object
        :return:
        """
        pass

    @abstractmethod
    def get_position_earth_general_inertial(self) -> (float, float, float):
        """
        This method returns the position of the orbital object in the referential of EGI.
        It can be used in the is_ascending method.
        :return:
        """
        pass


class WalkerShell(BaseModel):
    identifier: str
    type: str
    amount_of_orbit_plane: int
    amount_of_satellite_per_orbit_plane: int

    adjacent_inter_satellite_shifting: int = Field(default=0)
    maximum_inter_satellite_range_distance: Optional[float] = None
    maximum_ground_station_range: Optional[float] = None
    maximum_user_terminal_range: Optional[float] = None
    maximum_connected_ground_object: Optional[int] = None
    maximum_connected_user_terminal: Optional[int] = None
    maximum_connected_ground_station: Optional[int] = None

    ground_object_white_list: List[str] = Field(default_factory=list)


class GroundObjectDomain(BaseModel):

    identifier: str
    type: str

    elevation_above_horizon: float = Field(default=20)
    maximum_satellite_range_distance: float = Field(default=1000)
    maximum_satellite_connected_count: Optional[int] = None
    shell_white_lists: List[str] = Field(default_factory=list)
    maximum_connected_satellites: Optional[int] = None
    ground_to_space_connections_strategy: str = Field(default="")


class OrbitalObject(TopologyObject):
    """
    Any object in orbit
    """

    movement_model: MovementModel = Field(default=None, exclude=True)

    model_config = ConfigDict(arbitrary_types_allowed=True)

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

    @computed_field
    @property
    def orbital_phase(self) -> str:
        """
        Return the orbital phase of the object. It can be ascending or descending.
        :return:
        """
        if self.is_ascending():
            return "ascending"
        else:
            return "descending"

    def get_coordinates(self) -> SpatialPosition:
        """
        Get the object coordinates. The default format is longitude, latitude and elevation.
        :return:
        """

        return self.spatial_position

    @property
    def spatial_position(self):
        computed_spatial_position = self.get_movement_model().get_longitude_latitude()
        self.spatial_position_info = computed_spatial_position
        return computed_spatial_position

    def update(self):
        self.get_coordinates()


class Satellite(OrbitalObject):
    satellite_name: str
    type: str = Field(default="Satellite", frozen=True)

    walker_shell: Optional[WalkerShell] = None

    def __str__(self):
        return (
            super().__str__()
            + "Satellite name: {satellite_name} satellite_id: {satellite_id} ".format(
                satellite_name=self.satellite_name, satellite_id=self.object_id
            )
        )


class GroundObject(TopologyObject):
    ground_object_domain: Optional[GroundObjectDomain] = None

    label: str = Field(default="unknown")


class GroundStation(GroundObject):
    type: str = Field(default="GroundStation", frozen=True)

    def __post_init__(self):
        self.spatial_position.longitude = 0
        self.spatial_position.latitude = 0
        self.spatial_position.altitude = 0

    def __str__(self):
        return (
            super().__str__()
            + "Ground station id: {ground_station_id} label: {label} ".format(
                ground_station_id=self.object_id, label=self.label
            )
        )


class UserTerminal(GroundObject):
    """
    User terminal is a special type of ground station. It receives and emit data to the constellation
    """

    type: str = Field(default="UserTerminal", frozen=True)


class PointOfPresence(GroundObject):
    """
    Point of presence is a special type of ground station.
    It is used to connect an infrastructure to the internet backbone.
    """

    type: str = Field(default="PointOfPresence", frozen=True)

    def __str__(self):
        return (
            super().__str__()
            + "Point of presence id: {point_of_presence_id} label: {label} ".format(
                point_of_presence_id=self.object_id, label=self.label
            )
        )


class Flow(BaseModel):
    id: UUID = Field(default=None)

    source: int = Field(default=None)
    destination: int = Field(default=None)

    previous_hop: int = Field(default=None)
    next_hop: int = Field(default=None)

    size: int = Field(default=1)


class Link(BaseModel):
    """
    This is the communication Link. The link connects two Topological object.
    Links are considered as bidirectional for this first version.
    """

    type: str = Field(default="Link", frozen=True)

    source: TopologyObject = Field(default=None)
    destination: TopologyObject = Field(default=None)

    flows: list[Flow] = Field(default_factory=list)

    link_maximum_capacity: int = Field(default=1000)

    disabled: bool = Field(default=False)

    def get_used_capacity_between_hops_unidirectional(
        self, previous_hop: TopologyObject, next_hop: TopologyObject
    ) -> float:
        concerned_flows = list(
            filter(
                lambda concerned_flow: concerned_flow.previous_hop == previous_hop
                and concerned_flow.next_hop == next_hop,
                self.flows,
            )
        )
        total_used_capacity = 0
        for flow in concerned_flows:
            total_used_capacity += flow.size

        return total_used_capacity

    def total_capacity_between_hops_bidirectional(self) -> float:
        total_used_capacity = 0
        for flow in self.flows:
            total_used_capacity += flow.size
        return total_used_capacity

    def connect(self, source: TopologyObject, destination: TopologyObject):

        if source.topology_uniq_id is None or destination.topology_uniq_id is None:
            raise TopologyIdentifierNotDefinedError(
                "You cannot connect two objects without topology identifier"
            )

        if source == destination:
            raise ConnectionBetweenSameSatelliteForbiddenError(
                "You cannot connect with same source and destination"
            )
        self.source = source
        self.destination = destination


class InterSatelliteLink(Link):
    type: str = Field(default="InterSatelliteLink", frozen=True)

    inter_satellite_direction: InterSatelliteLinkDirection = Field(
        default=InterSatelliteLinkDirection.UNDEFINED
    )

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

    class ConfigDict:
        use_enum_values = True


class GroundToSpaceLink(Link):
    elevation_above_horizon_angle: float = Field(default=None)


class GroundStationLink(GroundToSpaceLink):
    type: str = Field(default="GroundStationLink", frozen=True)

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
            raise GroundStationConnectionError(
                "Incompatible types: "
                + source.__class__.__name__
                + " and "
                + destination.__class__.__name__
            )

        super().connect(source, destination)


class UserTerminalLink(GroundToSpaceLink):
    type: str = Field(default="UserTerminalLink", frozen=True)

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


class GroundObjectLink(Link):
    """
    This is the link between a ground object and another ground object
    """

    type: str = Field(default="GroundObjectLink", frozen=True)

    sub_type: str = Field(default="ground-object-to-ground-object")

    source: GroundObject = Field(default=None)
    destination: GroundObject = Field(default=None)

    def connect(self, source: GroundObject, destination: GroundObject):
        if source == destination:
            raise ConnectionBetweenSameTopologyForbiddenError(
                "You cannot connect with same source and destination"
            )

        if isinstance(source, GroundObject) and isinstance(destination, GroundObject):
            self.source = source
            self.destination = destination
        else:
            raise GroundObjectLinkConnectionError(
                "Incompatible types: "
                + source.__class__.__name__
                + " and "
                + destination.__class__.__name__
            )


class DistanceModel:
    def get_distance_meters(
        self, spatial_position_1: SpatialPosition, spatial_position_2: SpatialPosition
    ) -> float:
        pass

    def get_distance_km(
        self, spatial_position_1: SpatialPosition, spatial_position_2: SpatialPosition
    ) -> float:
        pass

    def k_closest(
        self,
        reference_point: SpatialPoint,
        target_points: list[SpatialPoint],
        k: int = 1,
    ) -> list[SpatialPoint]:
        pass

    def spatial_position_in_range(
        self,
        reference_point: SpatialPoint,
        target_points: list[SpatialPoint],
        range_in_km: int = 1000,
    ) -> list[SpatialPoint]:
        pass


def ground_station_link_is_connected_to_topology_object(
    ground_station_link: GroundStationLink, topology_object_id: str
) -> bool:
    source = ground_station_link.source
    destination = ground_station_link.destination

    if isinstance(source, GroundStation):
        return source.topology_uniq_id == topology_object_id
    elif isinstance(destination, GroundStation):
        return destination.topology_uniq_id == topology_object_id
    else:
        raise ValueError("This ground station link is corrupted")


class Simulation:
    object_uuid_index: int

    simulation_name: str

    satellites: List[Satellite]
    inter_satellite_links: List[InterSatelliteLink]

    ground_object_links: List[GroundObjectLink]

    ground_stations: List[GroundStation]
    ground_station_links: List[GroundStationLink]

    user_terminals: List[UserTerminal]
    user_terminal_links: List[UserTerminalLink]

    point_of_presences: List[PointOfPresence]

    walker_shells: List[WalkerShell]
    ground_object_domains: List[GroundObjectDomain]

    distance_model: DistanceModel = None

    def __init__(self):
        self.simulation_name = "Unknown"
        self.object_uuid_index = 0
        self.satellites = list()
        self.inter_satellite_links = list()
        self.ground_stations = list()
        self.ground_station_links = list()
        self.user_terminals = list()
        self.user_terminal_links = list()
        self.walker_shells = list()
        self.ground_object_domains = list()
        self.ground_object_links = list()
        self.point_of_presences = list()

        self.ground_object_domains.append(
            GroundObjectDomain(identifier="public", type="ground_object")
        )

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
        topology_objects.extend(self.point_of_presences)

        return topology_objects

    def get_all_ground_objects(self):
        ground_objects = []
        ground_objects.extend(self.ground_stations)
        ground_objects.extend(self.user_terminals)
        ground_objects.extend(self.point_of_presences)
        return ground_objects


def create_satellite(
    satellite_name: str,
    object_id: int,
    domain: str = "public",
) -> Satellite:
    """
    This function creates a Satellite object.
    :param satellite_name: The name of the satellite
    :param object_id: The business id of the satellite
    :param domain: The constellation identifier of the satellite.
    :return:
    """
    created_satellite = Satellite(
        satellite_name=satellite_name, object_id=object_id, domain=domain
    )

    created_satellite.object_id = object_id
    created_satellite.satellite_name = satellite_name
    created_satellite.domain = domain

    return created_satellite


def create_ground_station(object_id: int, domain: str = "public") -> GroundStation:
    """
    Create a ground station.
    :param domain: Owner of the ground station
    :param object_id: identifier of the ground station.
    :return:
    """
    created_ground_station = GroundStation()
    created_ground_station.object_id = object_id
    created_ground_station.domain = domain

    return created_ground_station


def create_user_terminal(object_id: int, domain: str = "public") -> UserTerminal:
    """
    Create a user terminal.
    :param domain: Owner domain of the company
    :param object_id: Object identifier
    :return:
    """

    created_user = UserTerminal()
    created_user.object_id = object_id
    created_user.domain = domain

    return created_user


def create_point_of_presence(object_id: int, domain: str = "public") -> PointOfPresence:
    """
    Create a point of presence.
    :param domain: Owner domain of the company
    :param object_id: Object identifier
    :return:
    """

    created_point_of_presence = PointOfPresence()
    created_point_of_presence.object_id = object_id
    created_point_of_presence.domain = domain

    return created_point_of_presence
