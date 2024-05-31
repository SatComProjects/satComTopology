import pytest

from sat_com_model.models import GroundStation, Satellite
from sat_com_trajectopy.distance_models import (
    GeopyDistanceModel,
    SkLearningDistanceModel,
)

from tests.sat_com_model_tests.model_helper import (
    create_fake_satellite_with_object_id,
    FakeMovementModel,
    create_fake_ground_station_with_object_id,
)
from tests.sat_com_topology_trajectopy.coordinates_features import (
    fake_100_satellite_coordinate,
    fake_100_ground_station_positions,
)


def assert_ground_station_are_correctly_linked_with_both_spatial_calculators(
    ground_station: GroundStation, satellites: list[Satellite], range_in_km: int
):
    sklearning_spatial_calculator = SkLearningDistanceModel()
    sklearn_results = sklearning_spatial_calculator.spatial_position_in_range(
        ground_station, satellites, range_in_km
    )

    default_spatial_calculator = GeopyDistanceModel()
    default_results = default_spatial_calculator.spatial_position_in_range(
        ground_station, satellites, range_in_km
    )

    if len(sklearn_results) != len(default_results):
        raise AssertionError()

    for result in sklearn_results:
        assert result in default_results


class TestSkLearningSpatialCalculator:
    @pytest.fixture
    def satellites(self) -> list[Satellite]:
        satellites = []
        for i in range(len(fake_100_satellite_coordinate)):
            satellite = create_fake_satellite_with_object_id(i)
            coordinates = fake_100_satellite_coordinate[i]
            satellite.set_movement_model(
                FakeMovementModel(coordinates[0], coordinates[1], coordinates[2])
            )
            satellites.append(satellite)

        return satellites

    @pytest.fixture
    def ground_stations(self) -> list[GroundStation]:
        ground_stations = []
        for i in range(len(fake_100_ground_station_positions)):
            coordinates = fake_100_ground_station_positions[i]
            ground_station = create_fake_ground_station_with_object_id(i)
            ground_station.spatial_position.longitude = coordinates[0]
            ground_station.spatial_position.latitude = coordinates[1]
            ground_station.spatial_position.altitude = coordinates[2]
            ground_stations.append(ground_station)

        return ground_stations

    def test_that_in_range_satellite_match_with_get_distance_model(
        self, ground_stations: list[GroundStation], satellites: list[Satellite]
    ):
        sklearn_distance_model = SkLearningDistanceModel()
        for ground_station in ground_stations:
            for i in range(10):
                distance_range = i * 100
                satellites_in_range = sklearn_distance_model.spatial_position_in_range(
                    ground_station, satellites, distance_range
                )
                for satellite in satellites_in_range:
                    distance_in_km = sklearn_distance_model.get_distance_km(
                        ground_station.spatial_position, satellite.spatial_position
                    )

                    assert distance_in_km <= distance_range
