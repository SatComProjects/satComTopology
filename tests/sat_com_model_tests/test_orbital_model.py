import pytest

from sat_com_model.exceptions import OrbitalObjectMovementModelUndefinedError
from sat_com_model.models import SpatialPosition
from tests.sat_com_model_tests.model_helper import (
    create_fake_satellite_with_object_id,
    FakeMovementModel,
)


class TestOrbitalModel:
    @pytest.fixture
    def satellite(self):
        return create_fake_satellite_with_object_id(1)

    def test_assert_orbital_model_disabled_if_not_exists(self, satellite):
        with pytest.raises(OrbitalObjectMovementModelUndefinedError):
            satellite.get_movement_model()

    def test_assert_can_define_movement_model(self, satellite):
        fake_movement_model = FakeMovementModel()

        satellite.set_movement_model(fake_movement_model)

        satellite_movement_model = satellite.get_movement_model()

        assert satellite_movement_model is not None

        satellite_is_ascending = satellite.is_ascending()

        assert type(satellite_is_ascending) is bool

        assert type(satellite.get_coordinates()) == SpatialPosition
