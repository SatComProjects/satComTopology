from geopy.distance import distance

from sat_com_model.models import DistanceModel, SpatialPosition


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
