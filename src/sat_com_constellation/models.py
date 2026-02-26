from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from sat_com_constellation.utils import (
    generate_two_line_elements,
    TwoLineElement,
    generate_sso_dawn_dusk,
)


class ConstellationProperty(BaseModel):
    identifier: str


class Constellation:
    identifier: str

    generated_two_line_elements: Optional[list[TwoLineElement]] = None

    def __init__(self, constellation_property: ConstellationProperty):
        self.identifier = constellation_property.identifier


class DawnDuskSunSynchronousOrbitConstellationProperty(ConstellationProperty):
    altitude_in_km: float
    amount_of_satellite: int
    epoch: Optional[datetime] = Field(default=None)


class DawnDuskSunSynchronousOrbitConstellation(Constellation):

    def __init__(
        self,
        sun_synchronous_orbit_constellation_property: DawnDuskSunSynchronousOrbitConstellationProperty,
    ):
        super().__init__(sun_synchronous_orbit_constellation_property)

        self.altitude_in_km = (
            sun_synchronous_orbit_constellation_property.altitude_in_km
        )
        self.amount_of_satellite = (
            sun_synchronous_orbit_constellation_property.amount_of_satellite
        )

        self.epoch = sun_synchronous_orbit_constellation_property.epoch

        self.__init_constellation()

    def __init_constellation(self):
        self.generated_two_line_elements = generate_sso_dawn_dusk(
            constellation_name=self.identifier,
            number_of_satellites=self.amount_of_satellite,
            epoch=self.epoch,
            altitude_km=self.altitude_in_km,
        )

    def __get_configuration(self) -> "DawnDuskSunSynchronousOrbitConstellationData":
        return DawnDuskSunSynchronousOrbitConstellationData(
            constellation_property=DawnDuskSunSynchronousOrbitConstellationProperty(
                identifier=self.identifier,
                amount_of_satellite=self.amount_of_satellite,
                epoch=self.epoch,
                altitude_in_km=self.altitude_in_km,
            ),
            constellation_two_line_elements=self.generated_two_line_elements,
        )

    def update_constellation(self, epoch: datetime = None):
        """
            Update the constellation's epoch and LTAN hours, and regenerate the two-line elements accordingly.
        :param epoch: New epoch for the constellation. If None, the epoch will not be updated.
        :return:
        """
        if epoch is not None:
            self.epoch = epoch

        self.__init_constellation()


class WalkerConstellationProperty(ConstellationProperty):
    identifier: str
    amount_of_orbit_plane: int
    amount_of_satellite_per_orbit_plane: int
    inclination: float
    phase_difference_between_satellites: bool
    mean_revolution_per_day: float


class DawnDuskSunSynchronousOrbitConstellationData(BaseModel):
    constellation_property: DawnDuskSunSynchronousOrbitConstellationProperty
    constellation_two_line_elements: list[TwoLineElement]


class WalkerConstellationData(BaseModel):
    constellation_property: WalkerConstellationProperty
    constellation_two_line_elements: list[TwoLineElement]


class WalkerConstellation(Constellation):
    amount_of_orbit_plane: int
    amount_of_satellite_per_orbit_plane: int
    inclination: float

    ORBIT_SPREADING_DEGREE = 360

    def __init__(self, walker_constellation_property: WalkerConstellationProperty):
        super().__init__(walker_constellation_property)
        self.amount_of_orbit_plane = walker_constellation_property.amount_of_orbit_plane
        self.amount_of_satellite_per_orbit_plane = (
            walker_constellation_property.amount_of_satellite_per_orbit_plane
        )
        self.inclination = walker_constellation_property.inclination
        self.phase_difference_between_satellites = (
            walker_constellation_property.phase_difference_between_satellites
        )
        self.mean_revolution_per_day = (
            walker_constellation_property.mean_revolution_per_day
        )
        self.argument_of_perigee_degree = 0.0
        self.eccentricity = 0.0001

        self.__init_constellation()

    def __init_constellation(self):
        self.generated_two_line_elements = generate_two_line_elements(
            constellation_name=self.identifier,
            number_of_orbits=self.amount_of_orbit_plane,
            number_of_satellites_per_plane=self.amount_of_satellite_per_orbit_plane,
            phase_difference=self.phase_difference_between_satellites,
            mean_motion_revolution_per_day=self.mean_revolution_per_day,
            eccentricity=self.eccentricity,
            inclination_degree=self.inclination,
            argument_of_perigee_degree=self.argument_of_perigee_degree,
            orbit_spreading_degree=self.ORBIT_SPREADING_DEGREE,
        )

    def __get_configuration(self) -> WalkerConstellationData:
        return WalkerConstellationData(
            constellation_property=WalkerConstellationProperty(
                identifier=self.identifier,
                amount_of_orbit_plane=self.amount_of_orbit_plane,
                amount_of_satellite_per_orbit_plane=self.amount_of_satellite_per_orbit_plane,
                inclination=self.inclination,
                phase_difference_between_satellites=self.phase_difference_between_satellites,
                mean_revolution_per_day=self.mean_revolution_per_day,
            ),
            constellation_two_line_elements=self.generated_two_line_elements,
        )


class WalkerStarConstellation(WalkerConstellation):
    ORBIT_SPREADING_DEGREE = 180


class WalkerDeltaConstellation(WalkerConstellation):
    ORBIT_SPREADING_DEGREE = 360
