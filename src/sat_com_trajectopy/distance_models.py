from geopy.distance import distance

from sat_com_model.models import DistanceModel, SpatialPosition


class GeopyDistanceModel(DistanceModel):
    def get_distance_meters(
        self, spatial_position_1: SpatialPosition, spatial_position_2: SpatialPosition
    ):
        return distance(
            (spatial_position_1.latitude, spatial_position_1.longitude),
            (spatial_position_2.latitude, spatial_position_2.longitude),
        ).meters

    def get_distance_km(
        self, spatial_position_1: SpatialPosition, spatial_position_2: SpatialPosition
    ):
        return distance(
            (spatial_position_1.latitude, spatial_position_1.longitude),
            (spatial_position_2.latitude, spatial_position_2.longitude),
        ).kilometers
