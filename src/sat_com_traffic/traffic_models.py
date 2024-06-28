import copy
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
from sat_com_trajectopy.distance_models import (
    calculate_topology_objects_in_range_of_topology_objects,
)


class TrafficModel:
    def compute_traffic(self, link: Link, current_time: datetime.time):
        pass


class GeographicalBasedTrafficModel(TrafficModel):
    simulation_manager: SimulationManager
    # Todo: Use property for satellite and user

    satellite_and_users: set

    center_urban_minimum_population: int = 100000

    amount_of_satellite_per_latitude: dict

    def satellites_around_satellite_with_a_given_range(self, range_in_km: int) -> dict:
        self.satellites_and_they_neighboring_but_not_linked_satellite = (
            calculate_topology_objects_in_range_of_topology_objects(
                self.simulation_manager.get_satellites(),
                self.simulation_manager.get_satellites(),
                range_in_km,
            )
        )
        return self.satellites_and_they_neighboring_but_not_linked_satellite

    def calculate_satellite_density_per_latitude(self):
        latitude_max = 90
        latitude_min = -90
        step = 10

        numbers = list(range(latitude_min, latitude_max + step, step))

        latitudes_pairs = [
            (numbers[i], numbers[i + 1]) for i in range(len(numbers) - 1)
        ]

        satellite_to_check = copy.deepcopy(self.simulation_manager.get_satellites())

        satellite_per_latitudes = dict()

        for pair in latitudes_pairs:
            born_latitude_min, born_latitude_max = pair
            satellite_per_latitudes[(born_latitude_min, born_latitude_max)] = 0
            for satellite in satellite_to_check:
                if (
                    born_latitude_min
                    <= satellite.get_coordinates().latitude
                    <= born_latitude_max
                ):
                    satellite_per_latitudes[pair] += satellite

        self.amount_of_satellite_per_latitude = satellite_per_latitudes
        return self.amount_of_satellite_per_latitude

    def __init__(self, simulation_manager: SimulationManager = None):
        self.satellites_and_they_neighboring_but_not_linked_satellite = dict()

        self.tf = TimezoneFinder()
        self.simulation_manager = simulation_manager
        self.satellite_and_users = set()
        self.amount_of_satellite_per_latitude = dict()

    def get_satellite_and_users(self):
        if self.satellite_and_users is None:
            self.calculate_amount_of_potential_user_per_satellite()

        return self.satellite_and_users

    def calculate_amount_of_potential_user_per_satellite(
        self, satellite_range_in_km: int = 100
    ) -> [(Satellite, int)]:
        self.satellite_and_users = set()
        self.satellites_around_satellite_with_a_given_range(satellite_range_in_km)
        satellites = self.simulation_manager.get_satellites()

        satellite_positions = [
            (
                satellite.get_coordinates().latitude,
                satellite.get_coordinates().longitude,
            )
            for satellite in satellites
        ]

        satellites_urbans_areas = get_urban_areas_around_positions(
            satellite_positions,
            satellite_range_in_km,
            self.center_urban_minimum_population,
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

            amount_of_satellite = len(
                self.satellites_and_they_neighboring_but_not_linked_satellite.get(
                    satellite
                )
            )

            amount_of_user_per_satellite = amount_of_user / amount_of_satellite
            self.satellite_and_users.add((satellite, amount_of_user_per_satellite))

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
