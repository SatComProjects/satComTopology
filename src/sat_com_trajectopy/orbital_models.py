import datetime

from pyorbital.orbital import Orbital

from sat_com_application.time_managers import TimeManager
from sat_com_model.models import MovementModel, SpatialPosition


class PyOrbitalModel(MovementModel):
    """
    This is an Orbital Model, which can be used to calculate orbital position of any orbital object using Two Line Orbit
    elements. This class uses the pyorbital library.
    """

    orbital_object: Orbital
    clock: TimeManager

    last_spatial_position: SpatialPosition = None

    last_time_position_calculated: datetime.datetime = None

    def __init__(self, tle: dict, time_manager: TimeManager):
        super().__init__()

        self.satellite_name = tle.get("satellite_name")
        self.line1 = tle.get("line1")
        self.line2 = tle.get("line2")
        orb = Orbital(self.satellite_name, line1=self.line1, line2=self.line2)
        self.orbital_object = orb
        self.clock = time_manager

    def is_ascending(self) -> bool:
        """
        Calculate whether the orbital object is ascending or descending.
        :return: True if the orbital object is ascending
        """
        position, velocity = self.orbital_object.get_position(
            self.clock.get_current_time()
        )
        # Check the sign of the z-coordinate to determine if in the ascending node
        return velocity[2] > 0

    def get_longitude_latitude_altitude(self) -> SpatialPosition:
        """
        Return the longitude and latitude AND the altitude of the orbital object as a spatial position.

        To minimize the computation, if the date didn't change since the last call, it will return the previously
        calculated position.

        Todo: This method should be renamed to include altitude in the name
        :return: SpatialPosition instance
        """

        time_did_not_change = (
            self.clock.get_current_time() == self.last_time_position_calculated
        )
        already_calculated_a_position_before = self.last_spatial_position is not None

        should_npt_calculate_new_position = (
            time_did_not_change and already_calculated_a_position_before
        )

        if should_npt_calculate_new_position:
            return self.last_spatial_position

        longitude, latitude, altitude = self.orbital_object.get_lonlatalt(
            self.clock.get_current_time()
        )

        new_position = SpatialPosition(
            longitude=longitude, latitude=latitude, altitude=altitude * 1000
        )
        self.last_spatial_position = new_position
        self.last_time_position_calculated = self.clock.get_current_time()

        return new_position

    def get_longitude_latitude(self):
        return self.get_longitude_latitude_altitude()

    def get_position_earth_general_inertial(self) -> tuple[float, float, float]:
        """
        Calculate the earth general inertial position. It is useful to know if object is
        ascending or descending for example.
        :return:
        """
        return self.orbital_object.get_position(self.clock.get_current_time())
