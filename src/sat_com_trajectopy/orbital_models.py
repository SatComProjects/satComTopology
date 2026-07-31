import datetime

from pyorbital.orbital import Orbital
from typing_extensions import deprecated

from sat_com_application.time_managers import TimeManager
from sat_com_model.models import MovementModel, SpatialPosition


class PyOrbitalModel(MovementModel):
    """
    Orbital movement model using TLEs propagated via pyorbital SGP4.

    Two independent caches (lon/lat/alt and ECI) store results keyed by absolute
    datetime.  When the simulation clock advances, any cached times that are
    strictly before the new current time are discarded.
    """

    orbital_object: Orbital
    clock: TimeManager

    _lonlatalt_cache: dict[datetime.datetime, SpatialPosition]
    _eci_cache: dict[
        datetime.datetime, tuple[tuple[float, float, float], tuple[float, float, float]]
    ]

    def __init__(self, tle: dict, time_manager: TimeManager):
        super().__init__()
        self.satellite_name = tle.get("satellite_name")
        self.line1 = tle.get("line1")
        self.line2 = tle.get("line2")
        self.orbital_object = Orbital(
            self.satellite_name, line1=self.line1, line2=self.line2
        )
        self.clock = time_manager

        self._lonlatalt_cache = {}
        self._eci_cache = {}

    def get_datetime(self) -> datetime.datetime:
        return self.clock.get_current_time()

    def _purge_old_entries(self) -> None:
        """Drop every cached time that is already in the past."""
        now = self.clock.get_current_time()
        for cache in (self._lonlatalt_cache, self._eci_cache):
            for t in list(cache):
                if t < now:
                    del cache[t]

    def _absolute_time(self, delta_t: float) -> datetime.datetime:
        return self.clock.get_current_time() + datetime.timedelta(seconds=delta_t)

    def is_ascending(self) -> bool:
        """True when the satellite is currently ascending (ECI vz > 0)."""
        _, velocity = self.get_position_and_velocity_earth_general_inertial(0.0)
        return velocity[2] > 0

    def get_longitude_latitude_altitude(self, delta_t: float = 0.0) -> SpatialPosition:
        """
        Geographic position (lon, lat, alt-in-metres).
        Results for any delta_t are cached; past entries are purged
        automatically when the clock advances.
        """
        self._purge_old_entries()
        t = self._absolute_time(delta_t)

        if t in self._lonlatalt_cache:
            return self._lonlatalt_cache[t]

        longitude, latitude, altitude = self.orbital_object.get_lonlatalt(t)
        position = SpatialPosition(
            longitude=longitude,
            latitude=latitude,
            altitude=altitude * 1000.0,  # km → m
        )
        self._lonlatalt_cache[t] = position
        return position

    @deprecated(
        "Use get_longitude_latitude_altitude instead for more complete "
        "position information."
    )
    def get_longitude_latitude(self) -> SpatialPosition:
        return self.get_longitude_latitude_altitude()

    def get_position_and_velocity_earth_general_inertial(
        self, delta_t: float = 0.0
    ) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
        """
        Single SGP4 call that returns both ECI position (km) and velocity (km/s).
        Preferred entry point when both vectors are needed.
        """
        self._purge_old_entries()
        t = self._absolute_time(delta_t)

        if t in self._eci_cache:
            return self._eci_cache[t]

        position, velocity = self.orbital_object.get_position(t, normalize=False)
        self._eci_cache[t] = (position, velocity)
        return position, velocity

    def get_position_earth_general_inertial(
        self, delta_t: float = 0.0
    ) -> tuple[float, float, float]:
        """ECI position vector (km) at now + delta_t."""
        position, _ = self.get_position_and_velocity_earth_general_inertial(delta_t)
        return position

    def get_velocity_earth_general_inertial(
        self, delta_t: float = 0.0
    ) -> tuple[float, float, float]:
        """ECI velocity vector (km/s) at now + delta_t."""
        _, velocity = self.get_position_and_velocity_earth_general_inertial(delta_t)
        return velocity

    def clear_caches(self) -> None:
        """Force-clear both caches (rarely needed)."""
        self._lonlatalt_cache.clear()
        self._eci_cache.clear()

    def cache_stats(self) -> dict:
        """Return current cache sizes (useful for profiling)."""
        return {
            "lonlatalt": len(self._lonlatalt_cache),
            "eci": len(self._eci_cache),
        }
