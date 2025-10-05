from sat_com_model.models import (
    Satellite,
    GroundObject,
    GroundObjectDomain,
    WalkerShell,
)
from tests.sat_com_model_tests.model_helper import FakeMovementModel


def make_fake_satellite():
    satellite = Satellite(
        topology_uniq_id=1,
        object_id=1,
        satellite_name="FakeSat",
    )
    satellite.set_movement_model(FakeMovementModel())

    return satellite


def make_fake_satellite_small_close_polar_shell():
    satellite = Satellite(
        topology_uniq_id=1,
        object_id=1,
        satellite_name="FakeSatPolar",
        walker_shell=WalkerShell(
            adjacent_inter_satellite_shifting=0,
            inclination=88,
            amount_of_satellite_per_orbit_plane=20,
            amount_of_orbit_plane=6,
            identifier="fake_polar_shell",
            type="delta",
        ),
    )
    satellite.set_movement_model(FakeMovementModel())
    return satellite


def make_fake_satellite_with_low_shell():
    satellite = Satellite(
        topology_uniq_id=1,
        object_id=1,
        satellite_name="FakeSatLow",
        walker_shell=WalkerShell(
            adjacent_inter_satellite_shifting=0,
            inclination=30,
            amount_of_satellite_per_orbit_plane=10,
            amount_of_orbit_plane=10,
            identifier="fake_low_shell",
            type="delta",
            mean_revolution_per_day=15.5,  # very low orbit
        ),
    )
    satellite.set_movement_model(FakeMovementModel())
    return satellite


def make_fake_satellite_with_high_shell():
    satellite = Satellite(
        topology_uniq_id=1,
        object_id=1,
        satellite_name="FakeSatHigh",
        walker_shell=WalkerShell(
            adjacent_inter_satellite_shifting=0,
            inclination=30,
            amount_of_satellite_per_orbit_plane=10,
            amount_of_orbit_plane=10,
            identifier="fake_high_shell",
            type="delta",
            mean_revolution_per_day=14,  # High orbit
        ),
    )
    satellite.set_movement_model(FakeMovementModel())
    return satellite


def make_fake_satellite_big_low_inclination_shell():
    satellite = Satellite(
        topology_uniq_id=1,
        object_id=1,
        satellite_name="FakeSatInclined",
        walker_shell=WalkerShell(
            adjacent_inter_satellite_shifting=0,
            inclination=53,
            amount_of_satellite_per_orbit_plane=22,
            amount_of_orbit_plane=40,
            identifier="fake_inclined_shell",
            type="delta",
        ),
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
