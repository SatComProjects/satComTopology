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


class TestDistanceModel:
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

    @pytest.fixture
    def paris_ground_station(self):
        ground_station = create_fake_ground_station_with_object_id(75000)
        ground_station.set_position(latitude=48.85341, longitude=2.3488, altitude=0)
        return ground_station

    @pytest.fixture
    def satellite_close_to_paris(self):
        satellite = create_fake_satellite_with_object_id(983)
        satellite.set_movement_model(
            FakeMovementModel(longitude=2.3488, latitude=48.81, altitude=400)
        )
        return satellite

    @pytest.fixture
    def satellite_far_from_paris(self):
        satellite = create_fake_satellite_with_object_id(999)
        satellite.set_movement_model(
            FakeMovementModel(longitude=95, latitude=-45, altitude=400)
        )
        return satellite

    @pytest.fixture
    def second_satellite_close_to_paris(self):
        satellite = create_fake_satellite_with_object_id(912)
        satellite.set_movement_model(
            FakeMovementModel(longitude=3, latitude=49, altitude=400)
        )
        return satellite

    @pytest.mark.parametrize(
        "distance_model_to_test", (SkLearningDistanceModel, GeopyDistanceModel)
    )
    def test_that_in_range_satellite_match_with_get_distance_model(
        self,
        ground_stations: list[GroundStation],
        satellites: list[Satellite],
        distance_model_to_test,
    ):
        distance_model = distance_model_to_test()

        for ground_station in ground_stations:
            for i in range(5):
                distance_range = i * 100
                satellites_in_range = distance_model.spatial_position_in_range(
                    ground_station, satellites, distance_range
                )
                for satellite in satellites_in_range:
                    distance_in_km = distance_model.get_distance_km(
                        ground_station.spatial_position, satellite.spatial_position
                    )

                    assert distance_in_km <= distance_range

    @pytest.mark.parametrize(
        "distance_model_to_test", (SkLearningDistanceModel, GeopyDistanceModel)
    )
    def test_distance_model_returns_the_closest_satellite(
        self,
        paris_ground_station: GroundStation,
        satellite_close_to_paris: Satellite,
        satellite_far_from_paris: Satellite,
        distance_model_to_test,
    ):
        distance_model = distance_model_to_test()
        closest_satellites = distance_model.k_closest(
            paris_ground_station,
            [satellite_far_from_paris, satellite_close_to_paris],
            k=1,
        )
        closest_satellite = closest_satellites[0]
        assert len(closest_satellites) == 1

        assert isinstance(closest_satellite, Satellite)
        assert closest_satellite.object_id == satellite_close_to_paris.object_id

    @pytest.mark.parametrize(
        "distance_model_to_test", (SkLearningDistanceModel, GeopyDistanceModel)
    )
    def test_distance_model_returns_multiple_closest_satellite(
        self,
        paris_ground_station: GroundStation,
        satellite_close_to_paris: Satellite,
        satellite_far_from_paris: Satellite,
        second_satellite_close_to_paris: Satellite,
        distance_model_to_test,
    ):
        distance_model = distance_model_to_test()
        closest_satellites = distance_model.k_closest(
            paris_ground_station,
            [
                satellite_far_from_paris,
                satellite_close_to_paris,
                second_satellite_close_to_paris,
            ],
            k=2,
        )
        first_closest_satellite = closest_satellites[0]
        second_closest_satellite = closest_satellites[1]
        assert len(closest_satellites) == 2

        assert isinstance(first_closest_satellite, Satellite)
        assert first_closest_satellite.object_id == satellite_close_to_paris.object_id

        assert isinstance(second_closest_satellite, Satellite)
        assert (
            second_closest_satellite.object_id
            == second_satellite_close_to_paris.object_id
        )
