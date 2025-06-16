from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from typing import List, Optional, Tuple

from sat_com_constellation.models import WalkerConstellationProperty


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
    shell_white_lists: List[str] = Field(default_factory=list)
    maximum_connected_satellites: Optional[int] = None

    ground_to_space_connections_strategy: str = Field(
        default="best-angle-until-disconnection"
    )


class OrbitalConnectivityProperty(BaseModel):
    maximum_inter_satellite_count: int = Field(default=4)
    adjacent_inter_satellite_shifting: int = Field(default=0)
    maximum_inter_satellite_range_distance: Optional[float] = None
    maximum_ground_station_range: Optional[float] = None
    maximum_user_terminal_range: Optional[float] = None
    maximum_connected_ground_object: Optional[int] = None
    maximum_connected_user_terminal: Optional[int] = None
    maximum_connected_ground_station: Optional[int] = None


class GroundObjectProperty(BaseModel):
    """
    Class that regroup properties for a set of ground objects.
    A ground object types:
    - user_terminal
    - ground_station

    Usually, a ground_station is also called "Gateway". But in the Starlink ecosystem,
    a ground station can be a point of presence and not necessarily a gateway.

    `data_file`: path of file with ground station data.

    `identifier`: should be a unique string, e.g., "Starlink Default Users",
    "Starlink Maritime Users", "Star Link PoP".
    """

    identifier: str
    data_file: str
    type: str
    connectivity_properties: GroundConnectivityProperty


class WalkerShellProperty(BaseModel):
    """
    Class that groups properties of a shell.
    A shell can take in parameter a list of ground object sets that will be allowed
    to communicate. If empty, the shell will not have any ground restriction.
    """

    type: str
    constellation_property: WalkerConstellationProperty
    orbital_connectivity_property: OrbitalConnectivityProperty
    ground_object_white_list: List[str] = Field(default_factory=list)


class GroundConnectivity(BaseModel):
    """
    Represents connectivity between GroundObjects.
    """

    type: str = Field(default="ground-to-ground")

    links: List[Tuple[Tuple[str, int], Tuple[str, int]]] = Field(default_factory=list)


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

    ground_objects_properties: List[GroundObjectProperty] = Field(default_factory=list)
    walker_shells: List[WalkerShellProperty] = Field(default_factory=list)

    disable_ground_station_link_preload: bool = Field(default=False)
    static_ground_station_link_mode: bool = Field(default=False)

    ground_connectivity_properties: List[GroundConnectivity] = Field(
        default_factory=list
    )
