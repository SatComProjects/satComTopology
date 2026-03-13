import datetime

from pyorbital.orbital import Orbital
from typing_extensions import deprecated

from sat_com_application.time_managers import TimeManager
from sat_com_model.models import MovementModel, SpatialPosition


class PyOrbitalModel(MovementModel):
    """
    Orbital movement model using Two-Line Element (TLE) sets propagated via the
    pyorbital SGP4 implementation.

    Two independent caches are maintained to avoid cross-invalidation:
    - lonlatalt cache: geographic coordinates (longitude, latitude, altitude)
    - ECI cache: Earth-Centered Inertial position and velocity vectors

    Both caches are only populated for current-time queries (delta_t=0).
    Future-time queries (delta_t>0) always propagate directly.
    """

    orbital_object: Orbital
    clock: TimeManager

    _last_spatial_position: SpatialPosition = None
    _last_time_longitude_latitude_altitude_calculated: datetime.datetime = None

    _last_position_eci: tuple[float, float, float] = None
    _last_velocity_eci: tuple[float, float, float] = None
    _last_time_eci_calculated: datetime.datetime = None

    def __init__(self, tle: dict, time_manager: TimeManager):
        super().__init__()
        self.satellite_name = tle.get("satellite_name")
        self.line1 = tle.get("line1")
        self.line2 = tle.get("line2")
        self.orbital_object = Orbital(
            self.satellite_name, line1=self.line1, line2=self.line2
        )
        self.clock = time_manager

    def get_datetime(self) -> datetime.datetime:
        return self.clock.get_current_time()

    def is_ascending(self) -> bool:
        """
        Returns True if the satellite is currently in the ascending part of its orbit
        (i.e. moving toward higher latitudes), determined by the sign of the ECI z-velocity.
        """
        _, velocity = self.orbital_object.get_position(
            self.clock.get_current_time(), normalize=False
        )
        return velocity[2] > 0

    def get_longitude_latitude_altitude(self, delta_t: float = 0.0) -> SpatialPosition:
        """
        Return the geographic position of the satellite as a SpatialPosition.
        Altitude is converted from km (pyorbital) to metres.

        Current-time results (delta_t=0) are cached to avoid redundant SGP4 calls.
        Future-time queries (delta_t>0) always propagate directly.

        Parameters
        ----------
        delta_t : float
            Time offset in seconds from the current clock time.
        """
        t = self.clock.get_current_time() + datetime.timedelta(seconds=delta_t)

        if (
            delta_t == 0.0
            and t == self._last_time_longitude_latitude_altitude_calculated
            and self._last_spatial_position is not None
        ):
            return self._last_spatial_position

        longitude, latitude, altitude = self.orbital_object.get_lonlatalt(t)

        position = SpatialPosition(
            longitude=longitude,
            latitude=latitude,
            altitude=altitude * 1000,  # km → m
        )

        if delta_t == 0.0:
            self._last_spatial_position = position
            self._last_time_longitude_latitude_altitude_calculated = t

        return position

    @deprecated(
        "Use get_longitude_latitude_altitude instead for more complete position information."
    )
    def get_longitude_latitude(self) -> SpatialPosition:
        return self.get_longitude_latitude_altitude()

    def get_position_earth_general_inertial(
        self, delta_t: float = 0.0
    ) -> tuple[float, float, float]:
        """
        Return the ECI position vector (km) at now + delta_t seconds.
        Current-time results (delta_t=0) are cached and shared with
        get_velocity_earth_general_inertial to avoid a redundant SGP4 call.

        Parameters
        ----------
        delta_t : float
            Time offset in seconds from the current clock time.

        Returns
        -------
        tuple[float, float, float]
            ECI position vector in km.
        """
        t = self.clock.get_current_time() + datetime.timedelta(seconds=delta_t)

        if (
            delta_t == 0.0
            and t == self._last_time_eci_calculated
            and self._last_position_eci is not None
        ):
            return self._last_position_eci

        position, velocity = self.orbital_object.get_position(t, normalize=False)

        if delta_t == 0.0:
            self._last_position_eci = position
            self._last_velocity_eci = velocity
            self._last_time_eci_calculated = t

        return position

    def get_velocity_earth_general_inertial(
        self, delta_t: float = 0.0
    ) -> tuple[float, float, float]:
        """
        Return the ECI velocity vector (km/s) at now + delta_t seconds.
        If get_position_earth_general_inertial was already called at the same
        current time, the cached velocity is returned at no extra SGP4 cost.

        Parameters
        ----------
        delta_t : float
            Time offset in seconds from the current clock time.

        Returns
        -------
        tuple[float, float, float]
            ECI velocity vector in km/s.
        """
        t = self.clock.get_current_time() + datetime.timedelta(seconds=delta_t)

        if (
            delta_t == 0.0
            and t == self._last_time_eci_calculated
            and self._last_velocity_eci is not None
        ):
            return self._last_velocity_eci

        position, velocity = self.orbital_object.get_position(t, normalize=False)

        if delta_t == 0.0:
            self._last_position_eci = position
            self._last_velocity_eci = velocity
            self._last_time_eci_calculated = t

        return velocity
