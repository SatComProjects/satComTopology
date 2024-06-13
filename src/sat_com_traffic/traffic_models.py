import datetime
import random

from pytz import timezone, utc
from timezonefinder import TimezoneFinder

from sat_com_application.simulation_manager import SimulationManager
from sat_com_model.models import Link, Satellite
from sat_com_traffic.earth_internet_user_generator.earth_internet_user_generator import (
    get_random_user_amount_based_on_population_model,
)


class TrafficModel:
    def compute_traffic(self, link: Link, current_time: datetime.time):
        pass


daily_multiplier = {
    1: 0.10,
    2: 0.05,
    3: 0.50,
    4: 0.75,
    5: 0.95,
    6: 0.30,
}


class GeographicalBasedTrafficModel(TrafficModel):
    simulation_manager: SimulationManager

    satellite_and_users: set

    def get_amount_of_users_per_satellite(self) -> [(Satellite, int)]:
        self.satellite_and_users = set()
        for satellite in self.simulation_manager.get_satellites():
            satellite_coordinate = satellite.get_coordinates()

            tf = TimezoneFinder()
            time_zone_str = tf.timezone_at(
                lng=satellite_coordinate.longitude, lat=satellite_coordinate.latitude
            )
            local_tz = timezone(time_zone_str)
            local_date = utc.localize(
                self.simulation_manager.time_manager.current_time
            ).astimezone(local_tz)

            satellite_local_date = local_date

            random_amount_of_population = (
                get_random_user_amount_based_on_population_model(
                    satellite_coordinate.longitude,
                    satellite_coordinate.latitude,
                    100,
                    satellite_local_date.time(),
                )
            )
            self.satellite_and_users.add((satellite, random_amount_of_population))

    def get_k_random_satellite_based_on_users_probability(
        self, k: int
    ) -> [(Satellite, int)]:
        satellites = [item[0] for item in self.satellite_and_users]
        weights = [item[1] for item in self.satellite_and_users]

        draws = random.choices(satellites, weights=weights, k=k)

        return draws

    def get_set_of_random_k_pairs_of_satellite(self, k: int):
        self.get_amount_of_users_per_satellite()
        sources = self.get_k_random_satellite_based_on_users_probability(k)
        destinations = self.get_k_random_satellite_based_on_users_probability(k)

        return list(zip(sources, destinations))
