from sat_com_model.models import Satellite, GroundObject, GroundObjectDomain
from tests.sat_com_model_tests.model_helper import FakeMovementModel


def make_fake_satellite():
    satellite = Satellite(
        topology_uniq_id=1,
        object_id=1,
        satellite_name="FakeSat",
    )
    satellite.set_movement_model(FakeMovementModel())

    return satellite


def make_fake_ground_object():
    groud_object = GroundObject(
        topology_uniq_id=2,
        object_id=1,
        label="FakeGround",
        ground_object_domain=GroundObjectDomain(
            identifier="fake_ground_domain",
            type="ground_station",
            elevation_above_horizon=25,
            maximum_satellite_range_distance=1000,
        ),
        links=[],
    )
    groud_object.set_position(
        longitude=0,
        latitude=0,
        altitude=0,
    )
    return groud_object
