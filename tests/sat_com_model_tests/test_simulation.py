import pytest

from sat_com_model.models import (
    Simulation,
)


class TestSimulation:
    @pytest.fixture
    def simulation(self):
        return Simulation()

    def test_request_an_id(self, simulation):
        id1 = simulation.request_an_id()
        id2 = simulation.request_an_id()
        assert id1 == 0
        assert id2 == 1
