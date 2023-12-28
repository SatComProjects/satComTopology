import pytest
from src.sat_com_model.model import (
    Simulation,
    TopologyObject,
    Link,
    Satellite,
    GroundStation,
    UserTerminal,
)

from src.sat_com_model.exception import TopologyObjectNotFoundError
from tests.model_helper import create_fake_satellite_with_satellite_id


class TestSimulation:
    @pytest.fixture
    def simulation(self):
        return Simulation()

    def test_request_an_id(self, simulation):
        id1 = simulation.request_an_id()
        id2 = simulation.request_an_id()
        assert id1 == 0
        assert id2 == 1

    def test_get_objects_from_type(self, simulation):
        # Assuming TopologyObject has a subclass named SubObject

        satellite_object = Satellite()
        ground_station_object = GroundStation()
        user_terminal_object = UserTerminal()
        simulation.topology_objects = [
            satellite_object,
            ground_station_object,
            user_terminal_object,
        ]

        result = simulation.get_objects_from_type(Satellite)
        assert len(result) == 1
        assert all(isinstance(obj, Satellite) for obj in result)

        result = simulation.get_objects_from_type(GroundStation)
        assert len(result) == 1
        assert all(isinstance(obj, GroundStation) for obj in result)

        result = simulation.get_objects_from_type(UserTerminal)
        assert len(result) == 1
        assert all(isinstance(obj, UserTerminal) for obj in result)

        result = simulation.get_objects_from_type(TopologyObject)
        assert len(result) == 3
        assert all(isinstance(obj, TopologyObject) for obj in result)

    def test_get_satellite(self, simulation):
        satellite1 = create_fake_satellite_with_satellite_id(1)
        satellite2 = create_fake_satellite_with_satellite_id(2)
        simulation.topology_objects = [satellite1, satellite2]

        result = simulation.get_satellite(1)
        assert result == satellite1

        with pytest.raises(TopologyObjectNotFoundError):
            simulation.get_satellite(3)
