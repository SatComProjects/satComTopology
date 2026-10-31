from __future__ import annotations

import datetime
import uuid
import warnings
from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, Generic, TypeVar, Any, cast
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict, computed_field, field_serializer
from typing_extensions import deprecated

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


class OpticalInterSatelliteLinkModel(str, Enum):
    """
    How optical inter-satellite links (OISL) are computed.

    - BASIC (default): links follow the addressing plan. Terminals are only
      connection slots: their pointing configuration is ignored, no optical
      metrics (elevation, azimuth, angular velocity...) are computed and links
      are never dropped for geometry. Only the distance is computed.
    - ADVANCED: every link is checked against its terminals configuration and
      carries its optical constraints.

    A strategy that needs the metrics (e.g. inter-shell assignment) computes them
    for the links it manages, whatever the simulation model.
    """

    BASIC = "basic"
    ADVANCED = "advanced"


class InterSatelliteLinkDirection(str, Enum):
    ORBITAL = "orbital"
    ADJACENT = "adjacent"
    UNDEFINED = "undefined"
    INTER_SHELL = "inter_shell"

    @classmethod
    def _missing_(cls, value):
        """
        Enables case-insensitive and flexible parsing.
        Called automatically by Enum when value is not found.
        """
        if isinstance(value, str):
            normalized = value.strip().lower()
            for member in cls:
                if member.value == normalized:
                    return member
        return None

    @classmethod
    def from_str(cls, value: str) -> "InterSatelliteLinkDirection":
        """
        Explicit constructor with clear error message.
        """
        try:
            return cls(value)
        except ValueError:
            valid = ", ".join([m.value for m in cls])
            raise ValueError(f"Invalid direction '{value}'. Valid values: {valid}")

    def __str__(self) -> str:
        """
        Clean string representation.
        """
        return self.value

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}.{self.name}"

    def is_defined(self) -> bool:
        return self is not self.UNDEFINED

    def is_orbital(self) -> bool:
        return self is self.ORBITAL

    def is_adjacent(self) -> bool:
        return self is self.ADJACENT

    def is_inter_shell(self) -> bool:
        return self is self.INTER_SHELL

    @classmethod
    def values(cls) -> list[str]:
        """
        Returns all possible string values.
        """
        return [member.value for member in cls]

    @classmethod
    def names(cls) -> list[str]:
        """
        Returns all enum names.
        """
        return [member.name for member in cls]


class SpatialPosition(BaseModel):
    longitude: float = Field(default=None)
    latitude: float = Field(default=None)
    altitude: float = Field(default=None)

    def to_longitude_latitude(self) -> tuple[float | None, float | None]:
        return self.longitude, self.latitude

    def to_latitude_longitude(self) -> tuple[float | None, float | None]:
        return self.latitude, self.longitude

    def to_longitude_latitude_altitude(
        self,
    ) -> tuple[float | None, float | None, float | None]:
        return self.longitude, self.latitude, self.altitude

    def to_latitude_longitude_altitude(
        self,
    ) -> tuple[float | None, float | None, float | None]:
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
    links: list[Link] = Field(default_factory=list, exclude=True, repr=False)

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
    def get_datetime(self) -> datetime.datetime:
        """
        Return the current time of the movement model.
        :return:
        """
        pass

    @abstractmethod
    def is_ascending(self) -> bool:
        """
        Return True if the Orbital object is in its ascending phase.
        :return:
        """
        pass

    @abstractmethod
    def get_longitude_latitude(self):
        warnings.warn(
            "get_longitude_latitude() is deprecated and will be removed in a future version. "
            "Use get_longitude_latitude_altitude() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.get_longitude_latitude_altitude()

    @abstractmethod
    def get_longitude_latitude_altitude(self, delta_t: float = 0.0) -> SpatialPosition:
        """
        Return the longitude, latitude  and elevation on ground of the orbital object
        :return:
        """
        pass

    @abstractmethod
    def get_position_earth_general_inertial(
        self, delta: float = 0.0
    ) -> tuple[float, float, float]:
        """
        This method returns the position of the orbital object in the referential of EGI.
        It can be used in the is_ascending method.
        :return:
        """
        pass

    @abstractmethod
    def get_velocity_earth_general_inertial(
        self, delta: float = 0.0
    ) -> tuple[float, float, float]:
        """
        This method returns the velocity of the orbital object in the referential of EGI.
        It can be used in the is_ascending method.
        :return:
        """
        pass


class InterSatelliteLinkOrientation(str, Enum):
    INTRA_PLANE_FORWARD = "INTRA_PLANE_FORWARD"
    INTRA_PLANE_BACKWARD = "INTRA_PLANE_BACKWARD"
    INTER_PLANE_RIGHT = "INTER_PLANE_RIGHT"
    INTER_PLANE_LEFT = "INTER_PLANE_LEFT"

    CROSS_PLANE_FORWARD = "CROSS_PLANE_FORWARD"
    CROSS_PLANE_BACKWARD = "CROSS_PLANE_BACKWARD"
    CROSS_PLANE_LEFT = "CROSS_PLANE_LEFT"
    CROSS_PLANE_RIGHT = "CROSS_PLANE_RIGHT"

    INTER_SHELL_FORWARD = "INTER_SHELL_FORWARD"
    INTER_SHELL_BACKWARD = "INTER_SHELL_BACKWARD"
    INTER_SHELL_LEFT = "INTER_SHELL_LEFT"
    INTER_SHELL_RIGHT = "INTER_SHELL_RIGHT"

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            value = value.lower()
            for member in cls:
                if member.value == value:
                    return member
        return None


class OpticalTerminalConfiguration(BaseModel):
    maximum_angular_velocity_degree_per_second: float = Field(default=1)
    maximum_range_distance_km: float = Field(default=7800)
    minimum_contact_duration_seconds: float = Field(default=30)

    max_azimuth_degrees: float = Field(default=175)  # ±175° azimuth
    min_elevation_degrees: float = Field(default=-25)  # +5°/-25° elev
    max_elevation_degrees: float = Field(default=5)

    los_central_angle_max_degrees: float = Field(
        default=80
    )  # Unused I don't remember what is it


class OpticalTerminalInstallationConfiguration(BaseModel):
    azimuth_angle_configuration: float = Field(
        default=0
    )  # 0 ° (X along track), 90°, -90°, -180°
    elevation_angle_configuration: float = Field(
        default=-180
    )  # Nadir anti nadir is 180

    descriptor: InterSatelliteLinkOrientation = Field(
        default=InterSatelliteLinkOrientation.INTRA_PLANE_FORWARD
    )  # az=0° and nadir=-180° is InterSatelliteLinkOrientation.INTRA_PLANE_FORWARD

    orientation_possibilities: list[InterSatelliteLinkOrientation] = Field(
        default=[InterSatelliteLinkOrientation.INTRA_PLANE_FORWARD]
    )

    optical_terminal_property: OpticalTerminalConfiguration = Field(
        default_factory=OpticalTerminalConfiguration
    )  # Configured as CONDOR gen 1


class SatelliteConfiguration(BaseModel):
    optical_inter_satellite_link_installations: list[
        OpticalTerminalInstallationConfiguration
    ] = [
        OpticalTerminalInstallationConfiguration(
            azimuth_angle_configuration=0.0,
            elevation_angle_configuration=-180,
            descriptor=InterSatelliteLinkOrientation.INTRA_PLANE_FORWARD,
            orientation_possibilities=[
                InterSatelliteLinkOrientation.INTRA_PLANE_FORWARD
            ],
        ),
        OpticalTerminalInstallationConfiguration(
            azimuth_angle_configuration=90.0,
            elevation_angle_configuration=-180,
            descriptor=InterSatelliteLinkOrientation.INTER_PLANE_LEFT,
            orientation_possibilities=[
                InterSatelliteLinkOrientation.INTER_PLANE_LEFT,
                InterSatelliteLinkOrientation.INTER_SHELL_LEFT,
            ],
        ),
        OpticalTerminalInstallationConfiguration(
            azimuth_angle_configuration=-90.0,
            elevation_angle_configuration=-180,
            descriptor=InterSatelliteLinkOrientation.INTER_PLANE_RIGHT,
            orientation_possibilities=[
                InterSatelliteLinkOrientation.INTER_PLANE_RIGHT,
                InterSatelliteLinkOrientation.INTER_SHELL_RIGHT,
            ],
        ),
        OpticalTerminalInstallationConfiguration(
            azimuth_angle_configuration=-180.0,
            elevation_angle_configuration=-180,
            descriptor=InterSatelliteLinkOrientation.INTRA_PLANE_BACKWARD,
            orientation_possibilities=[
                InterSatelliteLinkOrientation.INTRA_PLANE_FORWARD
            ],
        ),
    ]  # default has 4 ISL anti-nadir INTER and INTRA Planes


class Shell(BaseModel):

    model_config = ConfigDict(frozen=True)

    shell_id: UUID = Field(default_factory=uuid.uuid4, frozen=True)

    @field_serializer("shell_id", mode="plain", when_used="always")
    def serialize_uuid_as_str(self, val: UUID) -> str:
        return str(val)

    identifier: str
    type: str
    satellite_configuration: Optional[SatelliteConfiguration] = Field(default=None)

    static_addressing_plan: str = Field(default="")

    def __hash__(self) -> int:
        return hash(self.shell_id)

    def __eq__(self, other):
        if not isinstance(other, Shell):
            return False
        return self.shell_id == other.shell_id


class WalkerShell(Shell):
    type: str = Field(default="WalkerShell", frozen=True)
    amount_of_orbit_plane: int
    amount_of_satellite_per_orbit_plane: int
    inclination: float = Field(default=98.7)
    mean_revolution_per_day: float = Field(default=14.25)

    adjacent_inter_satellite_shifting: int = Field(default=0)
    maximum_inter_satellite_range_distance: Optional[float] = None
    maximum_ground_station_range: Optional[float] = None
    maximum_user_terminal_range: Optional[float] = None
    maximum_connected_ground_object: Optional[int] = None
    maximum_connected_user_terminal: Optional[int] = None
    maximum_connected_ground_station: Optional[int] = None

    ground_object_white_list: list[str] = Field(default_factory=list)


class DawnDuskSSOShell(Shell):
    epoch: datetime.datetime
    altitude_in_km: float

    amount_of_satellite: int

    type: str = Field(default="SSOShell", frozen=True)


class GroundObjectDomain(BaseModel):

    identifier: str
    type: str

    elevation_above_horizon: float = Field(default=20)
    maximum_satellite_range_distance: float = Field(default=1000)
    maximum_satellite_connected_count: Optional[int] = None
    shells_whitelist: list[str] = Field(default_factory=list)
    maximum_connected_satellites: Optional[int] = None
    ground_to_space_connections_strategy: str = Field(
        default="best-angle-until-disconnection"
    )


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
        computed_spatial_position = (
            self.get_movement_model().get_longitude_latitude_altitude()
        )
        self.spatial_position_info = computed_spatial_position
        return computed_spatial_position

    def update(self):
        self.get_coordinates()


class OpticalLinkTerminal(BaseModel):
    terminal_id: uuid.UUID = Field(default_factory=uuid.uuid4, frozen=True)

    @field_serializer("terminal_id", mode="plain", when_used="always")
    def serialize_uuid_as_str(self, val: UUID) -> str:
        return str(val)

    link: Optional[InterSatelliteLink] = Field(default=None, exclude=True)
    target_optical_link_terminal: Optional["OpticalLinkTerminal"] = Field(
        default=None, exclude=True
    )
    host_satellite: Satellite = Field(exclude=True, frozen=True)

    azimuth_angle_configuration: float = Field(
        default=0
    )  # 0 ° (X along track), 90°, -90°, -180°
    elevation_angle_configuration: float = Field(
        default=-180
    )  # Nadir anti nadir is 180

    descriptor: InterSatelliteLinkOrientation = Field(
        default=InterSatelliteLinkOrientation.INTRA_PLANE_FORWARD
    )  # az

    orientation_possibilities: list[InterSatelliteLinkOrientation] = Field(
        default=[InterSatelliteLinkOrientation.INTRA_PLANE_FORWARD]
    )

    terminal_configuration: OpticalTerminalConfiguration = Field(
        default_factory=OpticalTerminalConfiguration
    )  # Global terminal config

    def __hash__(self):
        return hash(self.terminal_id)

    def __eq__(self, other):
        if not isinstance(other, OpticalLinkTerminal):
            return False
        return self.terminal_id == other.terminal_id


T_Shell = TypeVar("T_Shell", bound=Shell)


class Satellite(Generic[T_Shell], OrbitalObject):
    satellite_name: str
    shell: Optional[T_Shell] = None

    type: str = Field(default="Satellite", frozen=True)

    optical_link_terminals: list[OpticalLinkTerminal] = Field(default_factory=list)

    def __init__(self, /, **data: Any):
        super().__init__(**data)

        if self.shell is None or self.shell.satellite_configuration is None:
            satellite_configuration = SatelliteConfiguration()
        else:
            satellite_configuration = self.shell.satellite_configuration
        self.__configure_satellite(satellite_configuration=satellite_configuration)

    def __configure_satellite(self, satellite_configuration: SatelliteConfiguration):
        for (
            optical_installation
        ) in satellite_configuration.optical_inter_satellite_link_installations:
            optical_terminal = OpticalLinkTerminal(
                descriptor=optical_installation.descriptor,
                azimuth_angle_configuration=optical_installation.azimuth_angle_configuration,
                elevation_angle_configuration=optical_installation.elevation_angle_configuration,
                orientation_possibilities=optical_installation.orientation_possibilities,
                terminal_configuration=optical_installation.optical_terminal_property,
                host_satellite=self,
            )

            self.optical_link_terminals.append(optical_terminal)

    def reconfigure_satellite(self, satellite_configuration: SatelliteConfiguration):
        """
        Re configure the satellite with a new configuration. This will update the optical link terminals of the satellite.
        Warning: it might diverge from the Shell default configuration.
        :param satellite_configuration:
        :return:
        """
        self.__configure_satellite(satellite_configuration)

    def __str__(self):
        return f"Satellite name: {self.satellite_name} satellite_id: {self.object_id} shell type: {self.shell.type}"

    def __repr__(self):
        return "Satellite(name={name}, topology_object_id={topology_object_id}, shell={shell})".format(
            name=self.satellite_name,
            topology_object_id=self.topology_uniq_id,
            shell=self.shell.shell_id if self.shell else "(no shell)",
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

    @field_serializer("id", mode="plain", when_used="always")
    def serialize_uuid_as_str(self, val: UUID) -> str:
        return str(val)

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

    link_id: uuid.UUID = Field(default_factory=uuid.uuid4)

    @field_serializer("link_id", mode="plain", when_used="always")
    def serialize_uuid_as_str(self, val: UUID) -> str:
        return str(val)

    type: str = Field(default="Link", frozen=True)

    source: TopologyObject = Field(default=None)
    destination: TopologyObject = Field(default=None)

    flows: list[Flow] = Field(default_factory=list)

    link_maximum_capacity: int = Field(default=1000)

    disabled: bool = Field(default=False)

    distance_km: Optional[float] = Field(default=None)

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

    def __hash__(self) -> int:
        return hash(self.link_id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Link):
            return False
        return self.link_id == other.link_id


class OpticalConstraint(BaseModel):
    azimuth_angle_degree: float = Field(default=None)
    relative_azimuth_angle_degree: float = Field(default=None)
    elevation_angle_degree: float = Field(default=None)
    range_distance_km: float = Field(default=None)
    angular_velocity_rate_degree_per_second: float = Field(default=None)
    los_min_altitude_km: float = Field(default=None)
    estimated_duration: float | None = Field(default=None)
    range_rate: float | None = Field(default=None)


class InterSatelliteLink(Link):
    type: str = Field(default="InterSatelliteLink", frozen=True)

    inter_satellite_direction: InterSatelliteLinkDirection = Field(
        default=InterSatelliteLinkDirection.UNDEFINED
    )
    source_constraint: OpticalConstraint | None = Field(default=None)
    destination_constraint: OpticalConstraint | None = Field(default=None)

    source_optical_terminal: Optional[OpticalLinkTerminal] = Field(
        default=None, exclude=True
    )
    destination_optical_terminal: Optional[OpticalLinkTerminal] = Field(
        default=None, exclude=True
    )

    temporary_unavailable: bool = Field(default=False)

    recovery_time: datetime.datetime | None = Field(default=None)

    estimated_duration: float = Field(default=None)

    """
    Model the link was computed with. BASIC: source_constraint and
    destination_constraint are None by design. ADVANCED: they are always set.
    """
    optical_link_model: OpticalInterSatelliteLinkModel = Field(
        default=OpticalInterSatelliteLinkModel.BASIC
    )

    @property
    def has_optical_metrics(self) -> bool:
        """True when the constraints were computed (advanced model)."""
        return self.optical_link_model == OpticalInterSatelliteLinkModel.ADVANCED

    def connect(
        self,
        source: TopologyObject,
        destination: TopologyObject,
        source_optical_terminal: OpticalLinkTerminal = None,
        destination_optical_terminal: OpticalLinkTerminal = None,
        source_constraint: OpticalConstraint = None,
        destination_constraint: OpticalConstraint = None,
        inter_satellite_direction: InterSatelliteLinkDirection = InterSatelliteLinkDirection.UNDEFINED,
    ):
        object_are_both_satellites = isinstance(source, Satellite) and isinstance(
            destination, Satellite
        )

        if not object_are_both_satellites:
            raise InterSatelliteConnectionError(
                f"You cannot use InterSatellite connection between these two objects: "
                f"{source.__class__} - {destination.__class__}"
            )

        source__destination_optical_terminal_are_the_same = (
            source_optical_terminal is not None
            and destination_optical_terminal is not None
            and source_optical_terminal == destination_optical_terminal
        )

        if source__destination_optical_terminal_are_the_same:
            raise InterSatelliteConnectionError("Terminals cannot be the same")

        # Logic Related to the ISL
        self.inter_satellite_direction = inter_satellite_direction

        # Logic Related To Every Links
        super().connect(source, destination)

        if source_optical_terminal and destination_optical_terminal:
            self.bind_terminals(
                source_terminal=source_optical_terminal,
                destination_terminal=destination_optical_terminal,
                source_constraint=source_constraint,
                destination_constraint=destination_constraint,
            )

    def bind_terminals(
        self,
        source_terminal: OpticalLinkTerminal,
        destination_terminal: OpticalLinkTerminal,
        source_constraint: OpticalConstraint,
        destination_constraint: OpticalConstraint,
    ):
        """
        Bind optical terminals to this link and wire all back-references:
          - link.source_optical_terminal / destination_optical_terminal
          - terminal.link on both sides
          - terminal.target_optical_link_terminal on both sides (peer reference)

        Must be called after connect().
        """

        if source_terminal.link is not None and source_terminal.link is not self:
            raise ValueError(
                f"Terminal {source_terminal.terminal_id} is already bound to "
                f"{source_terminal.link!r}. Call unbind_terminals() on the old "
                f"link before rebinding."
            )
        if (
            destination_terminal.link is not None
            and destination_terminal.link is not self
        ):
            raise ValueError(
                f"Terminal {destination_terminal.terminal_id} is already bound to "
                f"{destination_terminal.link!r}. Call unbind_terminals() on the old "
                f"link before rebinding."
            )

        self.source_optical_terminal = source_terminal
        self.destination_optical_terminal = destination_terminal

        self.source_constraint = source_constraint
        self.destination_constraint = destination_constraint

        source_terminal.link = self
        destination_terminal.link = self

        source_terminal.target_optical_link_terminal = destination_terminal
        destination_terminal.target_optical_link_terminal = source_terminal

    def unbind_terminals(self):
        """
        Clear all terminal bindings on both sides — call before removing the link
        so terminals are released back to the unassigned pool.
        """
        if self.source_optical_terminal is not None:
            self.source_optical_terminal.link = None
            self.source_optical_terminal.target_optical_link_terminal = None

        if self.destination_optical_terminal is not None:
            self.destination_optical_terminal.link = None
            self.destination_optical_terminal.target_optical_link_terminal = None

        self.source_optical_terminal = None
        self.destination_optical_terminal = None

        self.source_constraint = None
        self.destination_constraint = None

    def get_satellite_source(self) -> "Satellite":
        return cast(Satellite, self.source)

    def get_satellite_destination(self) -> "Satellite":
        return cast(Satellite, self.destination)

    def get_peer_satellite(self, satellite: "Satellite") -> "Satellite":
        """Return the satellite on the other end of this link."""
        if self.source == satellite:
            return cast(Satellite, self.destination)
        elif self.destination == satellite:
            return cast(Satellite, self.source)
        raise ValueError(
            f"Satellite {satellite.satellite_name} is not an endpoint of this link."
        )

    def get_terminal_for_satellite(
        self, satellite: "Satellite"
    ) -> Optional[OpticalLinkTerminal]:
        """Return the optical terminal assigned to the given satellite's side."""
        if self.source == satellite:
            return self.source_optical_terminal
        elif self.destination == satellite:
            return self.destination_optical_terminal
        raise ValueError(
            f"Satellite {satellite.satellite_name} is not an endpoint of this link."
        )

    def get_peer_terminal(
        self, terminal: OpticalLinkTerminal
    ) -> Optional[OpticalLinkTerminal]:
        """Return the terminal on the other side of this link."""
        if terminal == self.source_optical_terminal:
            return self.destination_optical_terminal
        elif terminal == self.destination_optical_terminal:
            return self.source_optical_terminal
        raise ValueError("Terminal is not bound to this link.")

    class ConfigDict:
        use_enum_values = True

    def __repr__(self):
        src_id = self.source.topology_uniq_id if self.source else None
        dst_id = self.destination.topology_uniq_id if self.destination else None
        return f"InterSatelliteLink(source={src_id}, destination={dst_id})"


class GroundToSpaceLink(Link):
    elevation_above_horizon_angle: float = Field(default=None)

    """Seconds until the disconnection at the last update (-1 when unknown)."""
    estimated_link_duration: float = Field(default=None)

    """
    Predicted time the satellite drops below the minimum elevation, set when the
    link is created. Absolute, so it never gets stale between updates.
    """
    estimated_disconnection_time: datetime.datetime | None = Field(default=None)

    def get_ground_object(self) -> GroundObject:
        return (
            self.source if isinstance(self.source, GroundObject) else self.destination
        )

    def get_space_object(self) -> OrbitalObject:
        return (
            self.source if isinstance(self.source, OrbitalObject) else self.destination
        )


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

    def get_satellite(self):
        return self.source if isinstance(self.source, Satellite) else self.destination

    def get_ground_station(self):
        return (
            self.source if isinstance(self.source, GroundStation) else self.destination
        )


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

    def get_satellite(self):
        return self.source if isinstance(self.source, Satellite) else self.destination

    def get_user_terminal(self):
        return (
            self.source if isinstance(self.source, UserTerminal) else self.destination
        )


class GroundObjectLink(Link):
    """
    This is the link between a ground object and another ground object
    """

    type: str = Field(default="GroundObjectLink", frozen=True)

    sub_type: str = Field(default="ground-object-to-ground-object")

    source: GroundObject = Field(default=None)
    destination: GroundObject = Field(default=None)

    recorded_latency: float | None = Field(default=None)

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

    def get_3d_distance_meters(
        self, spatial_position_1: SpatialPosition, spatial_position_2: SpatialPosition
    ):
        pass

    def get_ground_distance_meters(
        self, spatial_position_1: SpatialPosition, spatial_position_2: SpatialPosition
    ) -> float:
        pass

    def get_ground_distance_km(
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

    def spatial_position_on_ground_in_range(
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

    satellites: list[Satellite]

    inter_satellite_links: list[InterSatelliteLink]

    ground_object_links: list[GroundObjectLink]

    ground_stations: list[GroundStation]
    ground_station_links: list[GroundStationLink]

    user_terminals: list[UserTerminal]
    user_terminal_links: list[UserTerminalLink]

    point_of_presences: list[PointOfPresence]

    walker_shells: list[WalkerShell]

    down_dusk_sso_shells: list[DawnDuskSSOShell]

    ground_object_domains: list[GroundObjectDomain]

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
        self.down_dusk_sso_shells = list()
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


@deprecated(
    "This factory will be removed in the factories.py. Please use the one in factories.py"
)
def create_satellite(
    satellite_name: str,
    object_id: int,
    shell: T_Shell,
    domain: str = "public",
) -> Satellite[T_Shell]:
    """
    This function creates a Satellite object.
    :param shell:
    :param satellite_name: The name of the satellite
    :param object_id: The business id of the satellite
    :param domain: The constellation identifier of the satellite.
    :return:
    """
    created_satellite = Satellite(
        satellite_name=satellite_name, object_id=object_id, domain=domain, shell=shell
    )

    created_satellite.object_id = object_id
    created_satellite.satellite_name = satellite_name
    created_satellite.domain = domain

    return created_satellite


@deprecated(
    "This factory will be removed in the factories.py. Please use the one in factories.py"
)
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


@deprecated(
    "This factory will be removed in the factories.py. Please use the one in factories.py"
)
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


@deprecated(
    "This factory will be removed in the factories.py. Please use the one in factories.py"
)
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
