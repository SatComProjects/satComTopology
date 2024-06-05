import datetime

from sat_com_model.models import Link
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
    def compute_traffic(self, link: Link, current_time: datetime.time) -> int:
        position = link.source.get_coordinates()
        random_amount_of_population = get_random_user_amount_based_on_population_model(
            position.longitude, position.latitude, 100, current_time
        )
        return random_amount_of_population
