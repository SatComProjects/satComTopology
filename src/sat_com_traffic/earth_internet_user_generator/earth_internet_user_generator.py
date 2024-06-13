import datetime
import importlib.resources
import json
import os
import random

import numpy as np
from sklearn.neighbors import BallTree


with importlib.resources.open_text(
    "sat_com_traffic.earth_internet_user_generator.data",
    "world_data.json",
) as file:
    world_data_urban_area = json.load(file)

development_modifier = {1: 0.40, 2: 0.60, 3: 0.80}

daily_multiplier = {
    1: 0.10,
    2: 0.05,
    3: 0.50,
    4: 0.75,
    5: 0.95,
    6: 0.30,
}


def get_urban_area_around_position(position: (float, float), distance_max_km: int):
    center_of_urban_area = [
        (urban_area["GCPNT_LAT"], urban_area["GCPNT_LON"])
        for urban_area in world_data_urban_area
    ]

    center_of_urban_area = np.array(center_of_urban_area)

    position = np.array(position)

    position_rad = np.radians([position])

    distance_max = distance_max_km / 6371

    tree = BallTree(np.deg2rad(center_of_urban_area), metric="haversine")
    indices = tree.query_radius(position_rad, r=distance_max, return_distance=False)

    nearest_urban_area_positions = np.array(center_of_urban_area)[indices[0]]

    return list(
        filter(
            lambda urban_area: (urban_area["GCPNT_LAT"], urban_area["GCPNT_LON"])
            in nearest_urban_area_positions,
            world_data_urban_area,
        )
    )


def get_potential_user_min_and_max_for_urban_area(
    development_value: int, population: float, local_hour: datetime.time
) -> (float, float):
    percentage_of_mex_population_of_user = (
        development_modifier[development_value] * population
    )
    one_six_hour_period = local_hour.hour // 6 + 1
    hour_multiplier = daily_multiplier[one_six_hour_period]

    last_hour_multiplier = local_hour.hour // 6

    potential_user_max = percentage_of_mex_population_of_user * hour_multiplier
    potential_user_minimum = last_hour_multiplier * hour_multiplier

    return potential_user_minimum, potential_user_max


def get_average_potential_user_for_group_of_area(
    urban_areas: [], local_hour: datetime.time
):
    if len(urban_areas) == 0:
        return 0, 0
    total_potential_minimum_user = 0
    total_potential_maximum_user = 0
    for urban_area in urban_areas:
        development = urban_area["DEVELOPMENT"]
        population = urban_area["POPULATION"]
        (
            minimum_potential_user,
            maximum_potential_user,
        ) = get_potential_user_min_and_max_for_urban_area(
            development, population, local_hour
        )
        total_potential_minimum_user += maximum_potential_user
        total_potential_maximum_user += minimum_potential_user

    total_potential_user_minimum_mean = total_potential_minimum_user / len(urban_areas)
    total_potential_user_maximum_mean = total_potential_maximum_user / len(urban_areas)

    return total_potential_user_minimum_mean, total_potential_user_maximum_mean


def get_random_user_amount_based_on_population_model(
    longitude: float, latitude: float, range_in_km: int, local_hour: datetime.time
) -> int:
    urban_areas = get_urban_area_around_position((latitude, longitude), range_in_km)
    min_user, max_user = get_average_potential_user_for_group_of_area(
        urban_areas, local_hour
    )

    return random.randint(int(min_user), int(max_user))
