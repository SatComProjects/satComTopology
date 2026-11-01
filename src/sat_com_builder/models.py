import warnings
from datetime import datetime, timedelta
from enum import Enum

from pydantic import BaseModel, Field, model_validator
from typing import ClassVar, Optional

from sat_com_constellation.models import (
    WalkerConstellationProperty,
    DawnDuskSunSynchronousOrbitConstellationProperty,
)
from sat_com_model.models import OpticalInterSatelliteLinkModel


def _drop_unused_parameters(data, parameters: tuple[str, ...], section: str):
    """
    Remove parameters that are no longer part of the configuration, with a warning,
    so an old configuration file still loads.
    """
    if not isinstance(data, dict):
        return data
    unused = [parameter for parameter in parameters if parameter in data]
    for parameter in unused:
        warnings.warn(
            f"Parameter `{parameter}` ({section}) was never used and will be removed. It is ignored.",
            FutureWarning,
            stacklevel=2,
        )
    return {key: value for key, value in data.items() if key not in unused}


class InterSatelliteLinkOrientationProperty(str, Enum):
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
                if member.value.lower() == value:
                    return member
        return None


class OpticalTerminalProperty(BaseModel):
    maximum_angular_velocity_degree_per_second: float = Field(default=1)
    maximum_range_distance_km: float = Field(default=7800)
    minimum_contact_duration_seconds: float = Field(default=30)

    max_azimuth_degrees: float = Field(
        default=180
    )  # ±180° azimuth -> This is an overkill default terminal
    min_elevation_degrees: float = Field(default=-25)  # +5°/-25° elev
    max_elevation_degrees: float = Field(default=5)

    los_central_angle_max_degrees: float = Field(default=80)


class OpticalTerminalInstallationProperty(BaseModel):
    azimuth_angle_configuration: float = Field(
        default=0
    )  # 0 ° (X along track), 90°, -90°, -180°
    elevation_angle_configuration: float = Field(default=-90)  # Nadir anti nadir is -90

    descriptor: InterSatelliteLinkOrientationProperty = Field(
        default=InterSatelliteLinkOrientationProperty.INTRA_PLANE_FORWARD
    )  # az=0° and nadir=-180° is InterSatelliteLinkOrientation.INTRA_PLANE_FORWARD

    orientation_possibilities: list[InterSatelliteLinkOrientationProperty] = Field(
        default=[InterSatelliteLinkOrientationProperty.INTRA_PLANE_FORWARD]
    )

    optical_terminal_property: OpticalTerminalProperty = Field(
        default_factory=OpticalTerminalProperty
    )  # Configured as CONDOR gen 1


class SatelliteProperty(BaseModel):
    optical_inter_satellite_link_installations: list[
        OpticalTerminalInstallationProperty
    ] = [
        OpticalTerminalInstallationProperty(
            azimuth_angle_configuration=0.0,
            elevation_angle_configuration=-90,
            descriptor=InterSatelliteLinkOrientationProperty.INTRA_PLANE_FORWARD,
            orientation_possibilities=[
                InterSatelliteLinkOrientationProperty.INTRA_PLANE_FORWARD,
            ],
        ),
        OpticalTerminalInstallationProperty(
            azimuth_angle_configuration=90.0,
            elevation_angle_configuration=-90,
            descriptor=InterSatelliteLinkOrientationProperty.INTER_PLANE_LEFT,
            orientation_possibilities=[
                InterSatelliteLinkOrientationProperty.INTER_PLANE_LEFT,
            ],
        ),
        OpticalTerminalInstallationProperty(
            azimuth_angle_configuration=-90.0,
            elevation_angle_configuration=-90,
            descriptor=InterSatelliteLinkOrientationProperty.INTER_PLANE_RIGHT,
            orientation_possibilities=[
                InterSatelliteLinkOrientationProperty.INTER_PLANE_RIGHT,
            ],
        ),
        OpticalTerminalInstallationProperty(
            azimuth_angle_configuration=-180.0,
            elevation_angle_configuration=-90,
            descriptor=InterSatelliteLinkOrientationProperty.INTRA_PLANE_BACKWARD,
            orientation_possibilities=[
                InterSatelliteLinkOrientationProperty.INTRA_PLANE_BACKWARD,
            ],
        ),
    ]  # default has 4 ISL anti-nadir INTER and INTRA Planes


class GroundObjectData(BaseModel):
    id: int
    label: str
    longitude: float
    latitude: float
    altitude: float


class GroundConnectivityProperty(BaseModel):
    elevation_above_horizon: float = Field(default=20)
    maximum_satellite_range_distance: float = Field(default=1000)
    maximum_satellite_connected_count: Optional[int] = None

    # Deprecated
    shell_white_lists: list[str] = Field(default_factory=list)

    shells_whitelist: list[str] = Field(default_factory=list)

    maximum_connected_satellites: Optional[int] = None

    ground_to_space_connections_strategy: str = Field(
        default="best-angle-until-disconnection"
    )

    @model_validator(mode="before")
    @classmethod
    def handle_deprecated_shell_whitelist(cls, data):
        if not isinstance(data, dict):
            return data

        old = data.get("shell_white_lists")
        new = data.get("shells_whitelist")

        if (not new) and old:
            data["shells_whitelist"] = old

        return data


class OrbitalConnectivityProperty(BaseModel):
    # Parameters that were never used: accepted in a configuration, but ignored with a warning.
    UNUSED_PARAMETERS: ClassVar[tuple[str, ...]] = (
        "maximum_inter_satellite_count",
        "maximum_inter_satellite_range_distance",
        "maximum_ground_station_range",
        "maximum_user_terminal_range",
    )

    adjacent_inter_satellite_shifting: int = Field(default=0)

    # Can be kept for now
    maximum_connected_ground_object: Optional[int] = None
    maximum_connected_user_terminal: Optional[int] = None
    maximum_connected_ground_station: Optional[int] = None

    @model_validator(mode="before")
    @classmethod
    def drop_unused_parameters(cls, data):
        return _drop_unused_parameters(
            data, cls.UNUSED_PARAMETERS, "orbital_connectivity_property"
        )


class GroundObjectProperty(BaseModel):
    """
    Class that regroup properties for a set of ground objects.
    A ground object types:
    - user_terminal
    - ground_station

    Usually, a ground_station is also called "Gateway". But in the Starlink ecosystem,
    a ground station can be a point of presence and not necessarily a gateway.

    `data_file`: path of file with ground object data (id,label,latitude,longitude,altitude per line).

    `ground_objects`: ground objects written directly in the configuration.

    At least one of `data_file` and `ground_objects` must be set. When both are set,
    the ground objects of the file are loaded first, then the inline ones.

    `identifier`: should be a unique string, e.g., "Starlink Default Users",
    "Starlink Maritime Users", "Star Link PoP".
    """

    identifier: str
    data_file: Optional[str] = None
    type: str
    connectivity_properties: GroundConnectivityProperty

    ground_objects: Optional[list[GroundObjectData]] = None

    @model_validator(mode="after")
    def check_ground_object_source(self):
        if self.data_file is None and self.ground_objects is None:
            raise ValueError(
                f"Ground objects '{self.identifier}': set `data_file`, `ground_objects`, or both."
            )
        return self


class AddressingPlanType(str, Enum):
    CHECKERBOARD_WALKER_DELTA = "CHECKERBOARD_WALKER_DELTA"
    CHECKERBOARD_WALKER_STAR = "CHECKERBOARD_WALKER_STAR"
    FULL_MESH_WALKER_DELTA = "FULL_MESH_WALKER_DELTA"
    FULL_MESH_WALKER_STAR = "FULL_MESH_WALKER_STAR"
    LINKED_SSO = "LINKED_SSO"

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            value = value.lower()
            for member in cls:
                if member.value.lower() == value:
                    return member
        return None


class ShellProperty(BaseModel):
    satellite_property: SatelliteProperty = Field(default=SatelliteProperty())
    static_addressing_plan: AddressingPlanType = Field(default=None)


class DawnDuskSunSynchronousOrbitShellProperty(ShellProperty):
    """
    Class that groups properties of a shell with sun synchronous orbit constellation.
    A shell can take in parameter a list of ground object sets that will be allowed
    to communicate. If empty, the shell will not have any ground restriction.
    """

    constellation_property: DawnDuskSunSynchronousOrbitConstellationProperty
    orbital_connectivity_property: OrbitalConnectivityProperty
    ground_object_white_list: list[str] = Field(default_factory=list)
    constellation_white_list: list[str] = Field(default_factory=list)
    static_addressing_plan: AddressingPlanType = Field(
        default=AddressingPlanType.LINKED_SSO
    )


class WalkerShellType(str, Enum):
    DELTA = "delta"
    STAR = "star"

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            value = value.lower()
            for member in cls:
                if member.value.lower() == value:
                    return member
        return None


class WalkerShellProperty(ShellProperty):
    """
    Class that groups properties of a shell.
    A shell can take in parameter a list of ground object sets that will be allowed
    to communicate. If empty, the shell will not have any ground restriction.
    """

    type: WalkerShellType = Field(default=WalkerShellType.DELTA)

    static_addressing_plan: AddressingPlanType = Field(
        default=None,
    )

    constellation_property: WalkerConstellationProperty
    orbital_connectivity_property: OrbitalConnectivityProperty
    ground_object_white_list: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def set_default_addressing_plan(self):
        if self.static_addressing_plan is None:
            if self.type == WalkerShellType.DELTA:
                self.static_addressing_plan = AddressingPlanType.FULL_MESH_WALKER_DELTA
            else:
                self.static_addressing_plan = AddressingPlanType.FULL_MESH_WALKER_STAR
        return self


class GroundConnectivity(BaseModel):
    """
    Represents connectivity between GroundObjects.
    """

    type: str = Field(default="ground-to-ground")

    links: list[tuple[tuple[str, int], tuple[str, int]]] = Field(default_factory=list)


class SimulationProperty(BaseModel):
    """
    Simulation Properties
    """

    start_date: str = Field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
    )
    end_date: str = Field(
        default_factory=lambda: (datetime.now() + timedelta(days=7)).strftime(
            "%Y-%m-%d %H:%M:%S.%f"
        )
    )

    simulation_name: str = Field(
        default_factory=lambda: datetime.now().strftime("%Y%m%d-%H%M%S")
    )

    movement_model: str = Field(default="pyorbital")
    distance_model: str = Field(default="sklearn")

    ground_objects_properties: list[GroundObjectProperty] = Field(default_factory=list)
    walker_shells: list[WalkerShellProperty] = Field(default_factory=list)

    dawn_dusk_sso_shells: list[DawnDuskSunSynchronousOrbitShellProperty] = Field(
        default_factory=list
    )

    disable_ground_station_link_preload: bool = Field(default=False)

    ground_connectivity_properties: list[GroundConnectivity] = Field(
        default_factory=list
    )

    inter_satellite_link_connection_strategy: str = Field(
        default="intra-shell-static-connectivity"
    )

    """
    BASIC (default): optical ISLs follow the addressing plans without optical
    metrics. ADVANCED: every optical ISL is checked against its terminals.
    See sat_com_model.models.OpticalInterSatelliteLinkModel.
    """
    optical_inter_satellite_link_model: OpticalInterSatelliteLinkModel = Field(
        default=OpticalInterSatelliteLinkModel.BASIC
    )

    @model_validator(mode="before")
    @classmethod
    def drop_unused_parameters(cls, data):
        return _drop_unused_parameters(
            data, ("static_ground_station_link_mode",), "simulation properties"
        )
