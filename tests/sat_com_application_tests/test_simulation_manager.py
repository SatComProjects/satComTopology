import pytest

from sat_com_application.simulation_manager import SimulationManager
from sat_com_model.exceptions import (
    TopologyObjectNotFoundError,
    TopologyIdentifierNotDefinedError,
)
from sat_com_model.models import Simulation
from tests.sat_com_model_tests.model_helper import (
    create_fake_satellite_with_object_id,
    create_fake_ground_station_with_object_id,
    create_fake_user_terminal_with_object_id,
)


class TestSimulationManager:
    """
    This class regroups every method to manage simulation_service.
    Every function that can manage simulation_service should be here.
    We shouldn't put logic into the models.
    """

    @pytest.fixture
    def simulation(self):
        return Simulation()

    @pytest.fixture
    def simulation_service(self, simulation):
        return SimulationManager(simulation)

    def test_get_satellite(self, simulation_service):
        satellite1 = create_fake_satellite_with_object_id(1)
        satellite2 = create_fake_satellite_with_object_id(2)

        simulation_service.add_satellite(satellite1)
        simulation_service.add_satellite(satellite2)

        result = simulation_service.get_satellite_by_object_id(object_id=1)
        assert result == satellite1

        with pytest.raises(TopologyObjectNotFoundError):
            simulation_service.get_satellite_by_object_id(object_id=3)

    def test_get_ground_station(self, simulation_service):
        ground_station_1 = create_fake_ground_station_with_object_id(1)
        ground_station_2 = create_fake_ground_station_with_object_id(2)

        simulation_service.add_ground_station(ground_station_1)
        simulation_service.add_ground_station(ground_station_2)

        result = simulation_service.get_ground_station_by_object_id(object_id=1)
        assert result == ground_station_1

        with pytest.raises(TopologyObjectNotFoundError):
            simulation_service.get_ground_station_by_object_id(object_id=3)

    def test_get_user_terminal(self, simulation_service):
        user_terminal_1 = create_fake_user_terminal_with_object_id(1)
        user_terminal_2 = create_fake_user_terminal_with_object_id(2)

        simulation_service.add_user_terminals(user_terminal_1)
        simulation_service.add_user_terminals(user_terminal_2)

        result = simulation_service.get_user_terminal_by_object_id(object_id=1)
        assert result == user_terminal_1

        with pytest.raises(TopologyObjectNotFoundError):
            simulation_service.get_user_terminal_by_object_id(object_id=3)

    def test_add_satellite(self, simulation_service):
        simulation_service_id_index = simulation_service.simulation.object_uuid_index
        satellite = create_fake_satellite_with_object_id(1)

        with pytest.raises(TopologyIdentifierNotDefinedError):
            satellite.get_topology_uniq_id()

        simulation_service.add_satellite(satellite)

        assert satellite.get_topology_uniq_id() == simulation_service_id_index

    def test_add_ground_station(self, simulation_service):
        simulation_service_id_index = simulation_service.simulation.object_uuid_index
        ground_station = create_fake_ground_station_with_object_id(1)

        with pytest.raises(TopologyIdentifierNotDefinedError):
            ground_station.get_topology_uniq_id()

        simulation_service.add_ground_station(ground_station)

        assert ground_station.get_topology_uniq_id() == simulation_service_id_index

    def test_add_user_terminal(self, simulation_service):
        simulation_service_id_index = simulation_service.simulation.object_uuid_index
        user_terminal = create_fake_user_terminal_with_object_id(1)

        with pytest.raises(TopologyIdentifierNotDefinedError):
            user_terminal.get_topology_uniq_id()

        simulation_service.add_user_terminals(user_terminal)

        assert user_terminal.get_topology_uniq_id() == simulation_service_id_index

    def test_get_all_topology_objects(self, simulation_service):
        topology_objects = simulation_service.get_all_topology_objects()
        assert len(topology_objects) == 0
        user_terminal = create_fake_user_terminal_with_object_id(1)
        simulation_service.add_user_terminals(user_terminal)

        ground_station = create_fake_ground_station_with_object_id(1)
        simulation_service.add_ground_station(ground_station)

        satellite = create_fake_satellite_with_object_id(1)
        simulation_service.add_satellite(satellite)

        topology_objects = simulation_service.get_all_topology_objects()

        assert len(topology_objects) == 3

    def test_create_inter_satellite_link(self, simulation_service):
        assert len(simulation_service.simulation.inter_satellite_links) == 0
        satellite_1 = create_fake_satellite_with_object_id(1)
        satellite_2 = create_fake_satellite_with_object_id(2)

        simulation_service.add_satellite(satellite_1)
        simulation_service.add_satellite(satellite_2)

        created_link = (
            simulation_service.create_and_add_inter_satellite_link_connection(
                satellite_1, satellite_2
            )
        )

        assert len(simulation_service.simulation.inter_satellite_links) == 1
        assert created_link in simulation_service.simulation.inter_satellite_links
        assert created_link.source.topology_uniq_id == satellite_1.topology_uniq_id
        assert created_link.destination.topology_uniq_id == satellite_2.topology_uniq_id

        assert created_link in satellite_1.links
        assert created_link in satellite_2.links

    def test_create_ground_station_link(self, simulation_service):
        assert len(simulation_service.simulation.ground_station_links) == 0
        ground_station = create_fake_ground_station_with_object_id(1)
        satellite = create_fake_satellite_with_object_id(1)

        simulation_service.add_ground_station(ground_station)
        simulation_service.add_satellite(satellite)

        created_link = simulation_service.create_and_add_ground_station_link_connection(
            satellite, ground_station
        )
        assert len(simulation_service.simulation.ground_station_links) == 1
        assert created_link in simulation_service.simulation.ground_station_links
        assert created_link.source.topology_uniq_id == satellite.topology_uniq_id
        assert (
            created_link.destination.topology_uniq_id == ground_station.topology_uniq_id
        )

        assert created_link in ground_station.links
        assert created_link in satellite.links

    def test_get_connected_satellites_to_ground_station(self, simulation_service):
        """
        get_connected_satellites_to_ground_station used to collect results in a set(),
        but Satellite overrides __eq__ without __hash__, which Python makes unhashable,
        raising `TypeError: unhashable type: 'Satellite'`.
        """
        ground_station = create_fake_ground_station_with_object_id(1)
        satellite_1 = create_fake_satellite_with_object_id(1)
        satellite_2 = create_fake_satellite_with_object_id(2)
        unrelated_satellite = create_fake_satellite_with_object_id(3)

        simulation_service.add_ground_station(ground_station)
        simulation_service.add_satellite(satellite_1)
        simulation_service.add_satellite(satellite_2)
        simulation_service.add_satellite(unrelated_satellite)

        simulation_service.create_and_add_ground_station_link_connection(
            satellite_1, ground_station
        )
        simulation_service.create_and_add_ground_station_link_connection(
            satellite_2, ground_station
        )

        connected_satellites = (
            simulation_service.get_connected_satellites_to_ground_station(
                ground_station
            )
        )

        assert isinstance(connected_satellites, list)
        assert len(connected_satellites) == 2
        assert satellite_1 in connected_satellites
        assert satellite_2 in connected_satellites
        assert unrelated_satellite not in connected_satellites

    def test_get_connected_satellites_to_ground_station_with_no_link(
        self, simulation_service
    ):
        ground_station = create_fake_ground_station_with_object_id(1)
        simulation_service.add_ground_station(ground_station)

        assert (
            simulation_service.get_connected_satellites_to_ground_station(
                ground_station
            )
            == []
        )

    def test_create_user_terminal_link(self, simulation_service):
        assert len(simulation_service.simulation.user_terminal_links) == 0
        satellite = create_fake_satellite_with_object_id(1)

        user_terminal = create_fake_user_terminal_with_object_id(1)

        simulation_service.add_user_terminals(user_terminal)
        simulation_service.add_satellite(satellite)

        created_link = simulation_service.create_and_add_user_terminal_link_connection(
            satellite, user_terminal
        )
        assert len(simulation_service.simulation.user_terminal_links) == 1
        assert created_link in simulation_service.simulation.user_terminal_links
        assert created_link.source.topology_uniq_id == satellite.topology_uniq_id
        assert (
            created_link.destination.topology_uniq_id == user_terminal.topology_uniq_id
        )
        assert created_link in user_terminal.links
        assert created_link in satellite.links

    def test_get_all_links(self, simulation_service):
        assert len(simulation_service.get_all_links()) == 0
        satellite_1 = create_fake_satellite_with_object_id(1)
        satellite_2 = create_fake_satellite_with_object_id(2)

        ground_station = create_fake_ground_station_with_object_id(1)

        user_terminal = create_fake_user_terminal_with_object_id(1)

        simulation_service.add_satellite(satellite_1)
        simulation_service.add_satellite(satellite_2)
        simulation_service.add_ground_station(ground_station)
        simulation_service.add_user_terminals(user_terminal)

        simulation_service.create_and_add_ground_station_link_connection(
            satellite_1, ground_station
        )
        simulation_service.create_and_add_user_terminal_link_connection(
            satellite_2, user_terminal
        )

        simulation_service.create_and_add_inter_satellite_link_connection(
            satellite_1, satellite_2
        )

        assert len(simulation_service.get_all_links()) == 3

    def test_remove_ground_station_link(self, simulation_service):
        ground_station = create_fake_ground_station_with_object_id(1)
        satellite = create_fake_satellite_with_object_id(1)

        simulation_service.add_ground_station(ground_station)
        simulation_service.add_satellite(satellite)

        created_link = simulation_service.create_and_add_ground_station_link_connection(
            satellite, ground_station
        )

        assert len(simulation_service.simulation.ground_station_links) == 1
        assert created_link in ground_station.links
        assert created_link in satellite.links

        simulation_service.remove_ground_station_link(created_link)

        assert len(simulation_service.simulation.ground_station_links) == 0
        assert created_link not in ground_station.links
        assert created_link not in satellite.links

    def test_remove_user_terminal_link(self, simulation_service):
        user_terminal = create_fake_user_terminal_with_object_id(1)
        satellite = create_fake_satellite_with_object_id(1)

        simulation_service.add_user_terminals(user_terminal)
        simulation_service.add_satellite(satellite)

        created_link = simulation_service.create_and_add_user_terminal_link_connection(
            satellite, user_terminal
        )

        assert len(simulation_service.simulation.user_terminal_links) == 1
        assert created_link in user_terminal.links
        assert created_link in satellite.links

        simulation_service.remove_user_terminal_link(created_link)

        assert len(simulation_service.simulation.user_terminal_links) == 0
        assert created_link not in user_terminal.links
        assert created_link not in satellite.links

    def test_assert_remove_inter_satellite_link(self, simulation_service):
        satellite_1 = create_fake_satellite_with_object_id(1)
        satellite_2 = create_fake_satellite_with_object_id(2)

        simulation_service.add_satellite(satellite_1)
        simulation_service.add_satellite(satellite_2)

        created_link = (
            simulation_service.create_and_add_inter_satellite_link_connection(
                satellite_1, satellite_2
            )
        )

        assert len(simulation_service.simulation.inter_satellite_links) == 1
        assert created_link in satellite_1.links
        assert created_link in satellite_2.links

        simulation_service.remove_inter_satellite_link(created_link)

        assert len(simulation_service.simulation.inter_satellite_links) == 0
        assert created_link not in satellite_1.links
        assert created_link not in satellite_2.links
