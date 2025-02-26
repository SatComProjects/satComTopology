import datetime
import importlib.resources
import json
import random

import numpy as np
from sklearn.neighbors import BallTree

with importlib.resources.open_text(
    "sat_com_traffic.earth_internet_user_generator.data",
    "world_data.json",
) as file:
    world_data_urban_area = json.load(file)
    file.close()

development_modifier = {1: 0.01, 2: 0.05, 3: 0.80}

daily_multiplier = {
    1: 0.10,
    2: 0.05,
    3: 0.50,
    4: 0.75,
    5: 0.95,
    6: 0.30,
}


def map_ball_tree_result_with_urban_area(
    indices: [], center_points_of_urban_areas: [], urbans_area: []
):
    urban_area_positions_set = {
        (urban_area["GCPNT_LAT"], urban_area["GCPNT_LON"]): urban_area
        for urban_area in urbans_area
    }

    indices_with_its_urban_area_object = []

    center_points_of_urban_areas_np = np.array(center_points_of_urban_areas)

    for position_indices in indices:
        nearest_urban_area_positions = center_points_of_urban_areas_np[position_indices]

        nearest_urban_areas = [
            urban_area_positions_set[(lat, lon)]
            for lat, lon in nearest_urban_area_positions
            if (lat, lon) in urban_area_positions_set
        ]

        indices_with_its_urban_area_object.append(nearest_urban_areas)

    return indices_with_its_urban_area_object


def execute_balltree_query(
    center_points_of_urban_areas: [], input_to_query_positions: [], distance_max_km: int
) -> []:
    positions_rad = np.radians(input_to_query_positions)

    distance_max = distance_max_km / 6371

    tree = BallTree(np.deg2rad(center_points_of_urban_areas), metric="haversine")
    indices = tree.query_radius(positions_rad, r=distance_max, return_distance=False)

    return indices


def get_urban_areas_around_positions(
    positions: [(float, float)],
    distance_max_km: int,
    minimum_urban_area_population: int = 100000,
):
    filtered_urban_areas = [
        (urban_area["GCPNT_LAT"], urban_area["GCPNT_LON"], urban_area)
        for urban_area in world_data_urban_area
        if urban_area["POPULATION"] > minimum_urban_area_population
    ]

    center_points_of_urban_areas = np.array(
        [(urban_area[0], urban_area[1]) for urban_area in filtered_urban_areas]
    )

    positions = np.array(positions)

    indices = execute_balltree_query(
        center_points_of_urban_areas, positions, distance_max_km
    )

    results = map_ball_tree_result_with_urban_area(
        indices, center_points_of_urban_areas, filtered_urban_areas
    )

    return results


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

    total_potential_user_minimum_mean = total_potential_minimum_user
    total_potential_user_maximum_mean = total_potential_maximum_user

    return total_potential_user_minimum_mean, total_potential_user_maximum_mean


def get_random_amount_of_user_between_bounds(min_user: int, max_user: int) -> float:
    if max_user < min_user:
        return random.randint(int(max_user), int(min_user))

    return random.randint(int(min_user), int(max_user))
