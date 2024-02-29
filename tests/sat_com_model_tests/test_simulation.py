import pytest
from sat_com_model.model import (
    Simulation,
)

from sat_com_model.exception import (
    TopologyObjectNotFoundError,
    TopologyIdentifierNotDefined,
)
from tests.sat_com_model_tests.model_helper import (
    create_fake_satellite_with_object_id,
    create_fake_ground_station_with_object_id,
    create_fake_user_terminal_with_object_id,
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

    def test_get_satellite(self, simulation):
        satellite1 = create_fake_satellite_with_object_id(1)
        satellite2 = create_fake_satellite_with_object_id(2)

        simulation.add_satellite(satellite1)
        simulation.add_satellite(satellite2)

        result = simulation.get_satellite_by_object_id(object_id=1)
        assert result == satellite1

        with pytest.raises(TopologyObjectNotFoundError):
            simulation.get_satellite_by_object_id(object_id=3)

    def test_get_ground_station(self, simulation):
        ground_station_1 = create_fake_ground_station_with_object_id(1)
        ground_station_2 = create_fake_ground_station_with_object_id(2)

        simulation.add_ground_station(ground_station_1)
        simulation.add_ground_station(ground_station_2)

        result = simulation.get_ground_station_by_object_id(object_id=1)
        assert result == ground_station_1

        with pytest.raises(TopologyObjectNotFoundError):
            simulation.get_ground_station_by_object_id(object_id=3)

    def test_get_user_terminal(self, simulation):
        user_terminal_1 = create_fake_user_terminal_with_object_id(1)
        user_terminal_2 = create_fake_user_terminal_with_object_id(2)

        simulation.add_user_terminals(user_terminal_1)
        simulation.add_user_terminals(user_terminal_2)

        result = simulation.get_user_terminal_by_object_id(object_id=1)
        assert result == user_terminal_1

        with pytest.raises(TopologyObjectNotFoundError):
            simulation.get_user_terminal_by_object_id(object_id=3)

    def test_add_satellite(self, simulation):
        simulation_id_index = simulation.object_uuid_index
        satellite = create_fake_satellite_with_object_id(1)

        with pytest.raises(TopologyIdentifierNotDefined):
            satellite.get_topology_uniq_id()

        simulation.add_satellite(satellite)

        assert satellite.get_topology_uniq_id() == simulation_id_index

    def test_add_ground_station(self, simulation):
        simulation_id_index = simulation.object_uuid_index
        ground_station = create_fake_ground_station_with_object_id(1)

        with pytest.raises(TopologyIdentifierNotDefined):
            ground_station.get_topology_uniq_id()

        simulation.add_ground_station(ground_station)

        assert ground_station.get_topology_uniq_id() == simulation_id_index

    def test_add_user_terminal(self, simulation):
        simulation_id_index = simulation.object_uuid_index
        user_terminal = create_fake_user_terminal_with_object_id(1)

        with pytest.raises(TopologyIdentifierNotDefined):
            user_terminal.get_topology_uniq_id()

        simulation.add_user_terminals(user_terminal)

        assert user_terminal.get_topology_uniq_id() == simulation_id_index

    def test_get_all_topology_objects(self, simulation):
        topology_objects = simulation.get_all_topology_objects()
        assert len(topology_objects) == 0
        user_terminal = create_fake_user_terminal_with_object_id(1)
        simulation.add_user_terminals(user_terminal)

        ground_station = create_fake_ground_station_with_object_id(1)
        simulation.add_ground_station(ground_station)

        satellite = create_fake_satellite_with_object_id(1)
        simulation.add_satellite(satellite)

        topology_objects = simulation.get_all_topology_objects()

        assert len(topology_objects) == 3

    def test_create_inter_satellite_link(self, simulation):
        assert len(simulation.inter_satellite_links) == 0
        satellite_1 = create_fake_satellite_with_object_id(1)
        satellite_2 = create_fake_satellite_with_object_id(2)

        created_link = simulation.create_inter_satellite_link_connection(
            satellite_1, satellite_2
        )

        assert len(simulation.inter_satellite_links) == 1
        assert created_link in simulation.inter_satellite_links
        assert created_link.source.topology_uniq_id == satellite_1.topology_uniq_id
        assert created_link.destination.topology_uniq_id == satellite_2.topology_uniq_id

    def test_create_ground_station_link(self, simulation):
        assert len(simulation.ground_station_links) == 0
        ground_station = create_fake_ground_station_with_object_id(1)
        satellite = create_fake_satellite_with_object_id(1)

        created_link = simulation.create_ground_station_link_connection(
            satellite, ground_station
        )
        assert len(simulation.ground_station_links) == 1
        assert created_link in simulation.ground_station_links
        assert created_link.source.topology_uniq_id == satellite.topology_uniq_id
        assert (
            created_link.destination.topology_uniq_id == ground_station.topology_uniq_id
        )

    def test_create_user_terminal_link(self, simulation):
        assert len(simulation.user_terminal_links) == 0
        satellite = create_fake_satellite_with_object_id(1)
        user_terminal = create_fake_user_terminal_with_object_id(1)

        created_link = simulation.create_user_terminal_link_connection(
            satellite, user_terminal
        )
        assert len(simulation.user_terminal_links) == 1
        assert created_link in simulation.user_terminal_links
        assert created_link.source.topology_uniq_id == satellite.topology_uniq_id
        assert (
            created_link.destination.topology_uniq_id == user_terminal.topology_uniq_id
        )

    def test_get_all_links(self, simulation):
        assert len(simulation.get_all_links()) == 0
        satellite_1 = create_fake_satellite_with_object_id(1)
        satellite_2 = create_fake_satellite_with_object_id(2)

        ground_station = create_fake_ground_station_with_object_id(1)

        user_terminal = create_fake_user_terminal_with_object_id(1)

        simulation.create_ground_station_link_connection(satellite_1, ground_station)
        simulation.create_user_terminal_link_connection(satellite_2, user_terminal)

        simulation.create_inter_satellite_link_connection(satellite_1, satellite_2)

        assert len(simulation.get_all_links()) == 3
