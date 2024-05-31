from math import radians

import numpy as np
from geopy.distance import distance
from sklearn.metrics.pairwise import haversine_distances
from sklearn.neighbors import BallTree

from sat_com_model.models import DistanceModel, SpatialPosition, SpatialPoint


class GeopyDistanceModel(DistanceModel):
    """
    This is a Distance Model, a model used to calculate the distances. It uses the geopy library.
    """

    def get_distance_meters(
        self, spatial_position_1: SpatialPosition, spatial_position_2: SpatialPosition
    ) -> float:
        """
        Returns distance in meters between two spatial points
        :param spatial_position_1: The first spatial instance
        :param spatial_position_2: The second spatial instance
        :return: distance as float
        """
        return distance(
            (spatial_position_1.latitude, spatial_position_1.longitude),
            (spatial_position_2.latitude, spatial_position_2.longitude),
        ).meters

    def get_distance_km(
        self, spatial_position_1: SpatialPosition, spatial_position_2: SpatialPosition
    ) -> float:
        """
        Returns distance in km between two spatial points
        :param spatial_position_1: The first spatial instance
        :param spatial_position_2: The second spatial instance
        :return: distance as float
        """
        return distance(
            (spatial_position_1.latitude, spatial_position_1.longitude),
            (spatial_position_2.latitude, spatial_position_2.longitude),
        ).kilometers

    def k_closest(
        self,
        reference_point: SpatialPoint,
        target_points: [SpatialPoint],
        k: int = 1,
    ) -> [SpatialPoint]:
        spatial_point_with_distance_in_km = []
        for target_point in target_points:
            distance_between_satellite_and_ground_station = self.get_distance_km(
                reference_point.get_coordinates(), target_point.get_coordinates()
            )
            spatial_point_with_distance_in_km.append(
                (target_point, distance_between_satellite_and_ground_station)
            )

        spatial_points_with_distance_in_km_sorted = sorted(
            spatial_point_with_distance_in_km, key=lambda a: a[1], reverse=False
        )

        k_closest_points_with_distance_in_km = (
            spatial_points_with_distance_in_km_sorted[:k]
        )

        return [
            k_closest_point_with_distance_in_km[0]
            for k_closest_point_with_distance_in_km in k_closest_points_with_distance_in_km
        ]

    def spatial_position_in_range(
        self,
        reference_point: SpatialPoint,
        target_points: list[SpatialPoint],
        range_in_km: int = 1000,
    ) -> [SpatialPoint]:
        spatial_points_in_range = []
        for target_point in target_points:
            distance_between_satellite_and_ground_station = self.get_distance_km(
                reference_point.get_coordinates(), target_point.get_coordinates()
            )
            if distance_between_satellite_and_ground_station <= range_in_km:
                spatial_points_in_range.append(target_point)

        return spatial_points_in_range


def get_sklearn_haversine_distances(
    spatial_position_1: SpatialPosition, spatial_position_2: SpatialPosition
):
    """
    Returns distance in meters between two spatial points, using sklearn's haversine_distances function.
    :param spatial_position_1: The first spatial instance
    :param spatial_position_2: The second spatial instance
    :return:  distance as float at scale 1, should be multiplied by the miles/km/m, etc.
    """
    spatial_position_1_latitude_longitude = (
        spatial_position_1.latitude,
        spatial_position_1.longitude,
    )

    spatial_position_2_latitude_longitude = (
        spatial_position_2.latitude,
        spatial_position_2.longitude,
    )

    spatial_position_1_radian = [
        radians(_) for _ in spatial_position_1_latitude_longitude
    ]

    spatial_position_2_radian = [
        radians(_) for _ in spatial_position_2_latitude_longitude
    ]

    return haversine_distances([spatial_position_1_radian, spatial_position_2_radian])


def convert_spatial_position_to_latitude_longitude(
    spatial_position: SpatialPosition,
) -> (float, float):
    """
    Returns a list of latitude and longitude
    :param spatial_position:
    :return:
    """
    return spatial_position.latitude, spatial_position.longitude


def convert_spatial_positions_to_latitudes_longitudes(
    spatial_positions: list[SpatialPosition],
) -> list[(float, float)]:
    """
    Returns a list of latitude and longitude
    :param spatial_positions:
    :return:
    """
    return [
        convert_spatial_position_to_latitude_longitude(spatial)
        for spatial in spatial_positions
    ]


def _convert_to_radians(latitudes_longitudes: np.ndarray) -> np.ndarray:
    return np.deg2rad(latitudes_longitudes)


def _prepare_query_point(reference_point: SpatialPoint) -> np.ndarray:
    return np.deg2rad(
        [
            [
                reference_point.spatial_position.latitude,
                reference_point.spatial_position.longitude,
            ]
        ]
    )


def _get_spatial_points_from_indices(
    indices: np.ndarray, target_points: list[SpatialPoint]
) -> list[SpatialPoint]:
    flat_indices = indices.flatten().astype(int)
    return [target_points[i] for i in flat_indices]


class SkLearningDistanceModel(DistanceModel):
    EARTH_RADIUS_KM = 6371.009

    def get_distance_meters(
        self, spatial_position_1: SpatialPosition, spatial_position_2: SpatialPosition
    ) -> float:
        """
        Returns distance in meters between two spatial points
        :param spatial_position_1: The first spatial instance
        :param spatial_position_2: The second spatial instance
        :return: distance as float in meters
        """
        distance_scale_1 = get_sklearn_haversine_distances(
            spatial_position_1, spatial_position_2
        )[0, 1]
        return distance_scale_1 * self.EARTH_RADIUS_KM * 1000

    def get_distance_km(
        self, spatial_position_1: SpatialPosition, spatial_position_2: SpatialPosition
    ) -> float:
        """
        Returns distance in km between two spatial points
        :param spatial_position_1: The first spatial instance
        :param spatial_position_2: The second spatial instance
        :return: distance as float in km
        """

        distance_scale_1 = get_sklearn_haversine_distances(
            spatial_position_1, spatial_position_2
        )[0, 1]
        return distance_scale_1 * self.EARTH_RADIUS_KM

    def k_closest(
        self,
        reference_point: SpatialPoint,
        target_points: list[SpatialPoint],
        k: int = 1,
    ) -> [SpatialPosition]:
        target_latitudes_longitudes = convert_spatial_positions_to_latitudes_longitudes(
            [target_point.spatial_position for target_point in target_points]
        )

        points_coordinates_radian = np.deg2rad(target_latitudes_longitudes)

        bt = BallTree(points_coordinates_radian, metric="haversine")

        query_position_longitude_latitude = np.array(
            [
                reference_point.spatial_position.latitude,
                reference_point.spatial_position.longitude,
            ]
        )

        query_position_longitude_latitude_radian = np.deg2rad(
            [query_position_longitude_latitude]
        )

        distances, indices = bt.query(
            query_position_longitude_latitude_radian,
            k=k,
        )

        query_result = np.array(target_latitudes_longitudes)[
            indices.flatten().astype(int)
        ]

        spatial_point_result = list(
            filter(
                lambda spatial_point: (
                    spatial_point.spatial_position.latitude,
                    spatial_point.spatial_position.longitude,
                )
                in query_result,
                target_points,
            )
        )

        return spatial_point_result

    def spatial_position_in_range(
        self,
        reference_point: SpatialPoint,
        target_points: list[SpatialPoint],
        range_in_km: int = 1000,
    ) -> list[SpatialPoint]:
        target_latitudes_longitudes = convert_spatial_positions_to_latitudes_longitudes(
            [target_point.spatial_position for target_point in target_points]
        )

        target_latitudes_longitudes = np.array(target_latitudes_longitudes)

        points_coordinates_radian = np.deg2rad(target_latitudes_longitudes)

        tree = BallTree(points_coordinates_radian, metric="haversine")

        query_position_longitude_latitude = np.array(
            [
                reference_point.spatial_position.latitude,
                reference_point.spatial_position.longitude,
            ]
        )

        query_position_longitude_latitude_radian = np.deg2rad(
            [query_position_longitude_latitude]
        )

        distance_max = range_in_km / self.EARTH_RADIUS_KM

        indices = tree.query_radius(
            query_position_longitude_latitude_radian,
            r=distance_max,
            return_distance=False,
        )

        query_result = np.array(target_latitudes_longitudes)[indices[0]]

        spatial_point_result = list(
            filter(
                lambda spatial_point: (
                    spatial_point.spatial_position.latitude,
                    spatial_point.spatial_position.longitude,
                )
                in query_result,
                target_points,
            )
        )

        return spatial_point_result


distance_models_dict = {"geopy": GeopyDistanceModel, "sklearn": SkLearningDistanceModel}
distances_models = distance_models_dict.keys()
