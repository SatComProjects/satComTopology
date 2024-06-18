import datetime
import random

from pytz import timezone, utc
from timezonefinder import TimezoneFinder

from sat_com_application.simulation_manager import SimulationManager
from sat_com_model.models import Link, Satellite
from sat_com_traffic.earth_internet_user_generator.earth_internet_user_generator import (
    get_urban_areas_around_positions,
    get_average_potential_user_for_group_of_area,
    get_random_amount_of_user_between_bounds,
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
    # Todo: Use property for satellite and user

    satellite_and_users: set

    center_urban_minimum_population: int = 100000

    def __init__(self):
        self.tf = TimezoneFinder()

    def get_satellite_and_users(self):
        if self.satellite_and_users is None:
            self.calculate_amount_of_potential_user_per_satellite()

        return self.satellite_and_users

    def calculate_amount_of_potential_user_per_satellite(self) -> [(Satellite, int)]:
        self.satellite_and_users = set()
        satellites = self.simulation_manager.get_satellites()

        satellite_positions = [
            (
                satellite.get_coordinates().latitude,
                satellite.get_coordinates().longitude,
            )
            for satellite in satellites
        ]

        satellites_urbans_areas = get_urban_areas_around_positions(
            satellite_positions, 100, self.center_urban_minimum_population
        )

        for satellite, urbans_areas in zip(satellites, satellites_urbans_areas):
            satellite_position = satellite.get_coordinates()

            time_zone_str = self.tf.timezone_at(
                lng=satellite_position.longitude, lat=satellite_position.latitude
            )
            local_tz = timezone(time_zone_str)
            local_date = utc.localize(
                self.simulation_manager.time_manager.current_time
            ).astimezone(local_tz)

            min_user, max_user = get_average_potential_user_for_group_of_area(
                urbans_areas, local_date.time()
            )
            amount_of_user = get_random_amount_of_user_between_bounds(
                min_user, max_user
            )
            self.satellite_and_users.add((satellite, amount_of_user))

    def get_k_random_satellite_based_on_users_probability(
        self, k: int
    ) -> [(Satellite, int)]:
        satellites = [item[0] for item in self.satellite_and_users]
        weights = [item[1] for item in self.satellite_and_users]

        draws = random.choices(satellites, weights=weights, k=k)

        return draws

    def get_set_of_random_k_pairs_of_satellite(self, k: int):
        sources = self.get_k_random_satellite_based_on_users_probability(k)
        destinations = self.get_k_random_satellite_based_on_users_probability(k)

        return list(zip(sources, destinations))
