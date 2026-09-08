from sat_com_adapter.cesium_renderer.formats import CesiumJavaScriptFormat
from sat_com_adapter.cesium_renderer.models import CesiumProperty
from tests.sat_com_model_tests.model_helper import (
    FakeMovementModel,
    create_fake_ground_station_with_object_id,
    create_fake_satellite_with_object_id,
    create_fake_user_terminal_with_object_id,
)


def _cesium_format() -> CesiumJavaScriptFormat:
    return CesiumJavaScriptFormat(CesiumProperty())


def test_create_satellite_without_walker_shell_does_not_raise():
    """
    walker_shell is Optional on Satellite (e.g. a satellite created by hand, without
    going through a WalkerConstellation). create_satellite used to crash with
    `AttributeError: 'NoneType' object has no attribute 'identifier'`.
    """
    satellite = create_fake_satellite_with_object_id(0)
    satellite.set_movement_model(FakeMovementModel())

    _cesium_format().create_satellite(satellite)


def test_create_ground_station_without_ground_object_domain_does_not_raise():
    """
    ground_object_domain is Optional on GroundObject (e.g. a ground station added
    manually through SimulationManager). create_ground_station used to crash with
    `AttributeError: 'NoneType' object has no attribute 'identifier'`.
    """
    ground_station = create_fake_ground_station_with_object_id(0)
    ground_station.set_position(longitude=1, latitude=1, altitude=0)

    _cesium_format().create_ground_station(ground_station)


def test_create_user_terminal_without_ground_object_domain_does_not_raise():
    user_terminal = create_fake_user_terminal_with_object_id(0)
    user_terminal.set_position(longitude=1, latitude=1, altitude=0)

    _cesium_format().create_user_terminal(user_terminal)


def test_create_user_terminal_uses_label():
    """
    create_user_terminal used to read `user_terminal.user_name`, an attribute that
    does not exist on UserTerminal (only `label` does), raising an AttributeError.
    """
    user_terminal = create_fake_user_terminal_with_object_id(0)
    user_terminal.set_position(longitude=1, latitude=1, altitude=0)
    user_terminal.label = "Toulouse"

    rendered = _cesium_format().create_user_terminal(user_terminal)

    assert "Toulouse" in rendered
