import pytest
from unittest.mock import Mock

from sat_com_adapter.networkx_builder.networkx_builder import NetworkxBuilder


class TestNetworkxBuilder:
    @pytest.fixture
    def simulation_manager(self):
        mock_manager = Mock()
        mock_manager.time_manager.current_time.strftime.return_value = (
            "2024-10-16 12:34:56.789"
        )
        mock_manager.configuration = {"some_config_key": "some_value"}
        mock_manager.simulation.get_distance_model.return_value.get_distance_meters.return_value = (
            1000
        )
        return mock_manager

    @pytest.fixture
    def network_builder(self, simulation_manager):
        return NetworkxBuilder(simulation_manager)

    @pytest.fixture
    def network_builder_export_position(self, simulation_manager):
        return NetworkxBuilder(simulation_manager, export_positions=True)

    @pytest.fixture
    def network_builder_export_link_length(self, simulation_manager):
        return NetworkxBuilder(simulation_manager, export_link_length=True)

    @pytest.fixture
    def network_builder_export_flows_data(self, simulation_manager):
        return NetworkxBuilder(simulation_manager, enable_export_flows_data=True)

    @pytest.fixture
    def topology_object(self):
        mock_topology_object = Mock()
        mock_topology_object.get_coordinates.return_value = Mock(
            longitude=45, latitude=90, altitude=500
        )
        mock_topology_object.get_type.return_value = "satellite"
        mock_topology_object.object_id = 1
        mock_topology_object.topology_uniq_id = "satellite-1"
        return mock_topology_object

    @pytest.fixture
    def topology_object_2(self):
        mock_topology_object = Mock()
        mock_topology_object.get_coordinates.return_value = Mock(
            longitude=45, latitude=90, altitude=500
        )
        mock_topology_object.get_type.return_value = "satellite"
        mock_topology_object.object_id = 2
        mock_topology_object.topology_uniq_id = "satellite-2"
        return mock_topology_object

    @pytest.fixture
    def link(self, topology_object, topology_object_2):
        mock_link = Mock()
        mock_link.source = topology_object
        mock_link.destination = topology_object_2
        mock_link.type = "inter_satellite"
        mock_link.get_used_capacity_between_hops_unidirectional.side_effect = [100, 200]
        mock_link.total_capacity_between_hops_bidirectional.return_value = 300
        mock_link.link_maximum_capacity = 500
        return mock_link

    def test_add_topology_object(self, network_builder, topology_object):
        network_builder.add_topology_object(topology_object)

        assert topology_object.topology_uniq_id in network_builder.graph
        node_data = network_builder.graph.nodes[topology_object.topology_uniq_id]
        assert node_data["type"] == "satellite"
        assert node_data["object_id"] == topology_object.object_id

    def test_add_link_without_any_data(self, network_builder, topology_object, link):
        network_builder.add_link(link)

        assert network_builder.graph.has_edge(
            link.source.topology_uniq_id, link.destination.topology_uniq_id
        )

        edge_data = network_builder.graph.get_edge_data(
            link.source.topology_uniq_id, link.destination.topology_uniq_id
        )
        assert edge_data["type"] == "inter_satellite"
        assert "distance" not in edge_data
        assert "used_capacity_between_previous_and_last_hop" not in edge_data

    def test_add_link_with_link_length(
        self, network_builder_export_link_length, topology_object, link
    ):
        network_builder_export_link_length.add_link(link)

        assert network_builder_export_link_length.graph.has_edge(
            link.source.topology_uniq_id, link.destination.topology_uniq_id
        )

        edge_data = network_builder_export_link_length.graph.get_edge_data(
            link.source.topology_uniq_id, link.destination.topology_uniq_id
        )
        assert edge_data["type"] == "inter_satellite"
        assert "distance" in edge_data
        assert "used_capacity_between_previous_and_last_hop" not in edge_data

    def test_add_link_with_link_flows_data(
        self,
        network_builder_export_flows_data,
        topology_object,
        topology_object_2,
        link,
    ):
        network_builder_export_flows_data.add_link(link)

        assert network_builder_export_flows_data.graph.has_edge(
            link.source.topology_uniq_id, link.destination.topology_uniq_id
        )

        edge_data = network_builder_export_flows_data.graph.get_edge_data(
            link.source.topology_uniq_id, link.destination.topology_uniq_id
        )
        assert edge_data["type"] == "inter_satellite"
        assert "distance" not in edge_data
        assert "used_capacity_between_previous_and_last_hop" in edge_data

        assert (
            topology_object.topology_uniq_id
            in edge_data["used_capacity_between_previous_and_last_hop"]
        )
        assert (
            topology_object_2.topology_uniq_id
            in edge_data["used_capacity_between_previous_and_last_hop"]
        )

    def test_add_satellites(self, network_builder, simulation_manager):
        satellite = Mock()
        satellite.is_ascending.return_value = True
        satellite.topology_uniq_id = "satellite-1"
        simulation_manager.get_satellites.return_value = [satellite]

        network_builder.add_satellites()

        assert "satellite-1" in network_builder.graph
        node_data = network_builder.graph.nodes["satellite-1"]
        assert node_data["orbital_phase"] == "ascending"
        assert "position" not in node_data

    def test_add_satellites_with_position(
        self, network_builder_export_position, simulation_manager
    ):
        satellite = Mock()
        satellite.is_ascending.return_value = True
        satellite.topology_uniq_id = "satellite-1"

        spatial_position = Mock()
        spatial_position.longitude = 200
        spatial_position.latitude = 90
        spatial_position.altitude = 500

        satellite.get_coordinates.return_value = spatial_position

        simulation_manager.get_satellites.return_value = [satellite]

        network_builder_export_position.add_satellites()

        assert "satellite-1" in network_builder_export_position.graph
        node_data = network_builder_export_position.graph.nodes["satellite-1"]
        assert node_data["orbital_phase"] == "ascending"
        assert "position" in node_data

    def test_add_ground_stations(self, network_builder, simulation_manager):
        ground_station = Mock()
        ground_station.label = "CityA"
        ground_station.topology_uniq_id = "ground-1"
        simulation_manager.get_ground_stations.return_value = [ground_station]

        network_builder.add_ground_stations()

        assert "ground-1" in network_builder.graph
        node_data = network_builder.graph.nodes["ground-1"]
        assert node_data["label"] == "CityA"
        assert "position" not in node_data

    def test_add_ground_stations_with_position(
        self, network_builder_export_position, simulation_manager
    ):
        ground_station = Mock()
        ground_station.label = "CityA"
        ground_station.topology_uniq_id = "ground-1"
        simulation_manager.get_ground_stations.return_value = [ground_station]

        network_builder_export_position.add_ground_stations()

        spatial_position = Mock()
        spatial_position.longitude = 200
        spatial_position.latitude = 90
        spatial_position.altitude = 500

        ground_station.get_coordinates.return_value = spatial_position

        assert "ground-1" in network_builder_export_position.graph
        node_data = network_builder_export_position.graph.nodes["ground-1"]
        assert node_data["label"] == "CityA"
        assert "position" in node_data

    def test_add_ground_station_links(self, network_builder, simulation_manager):
        ground_station_link = Mock()
        ground_station_link.source.topology_uniq_id = "ground-1"
        ground_station_link.destination.topology_uniq_id = "satellite-1"
        ground_station_link.disabled = False
        simulation_manager.get_ground_stations_links.return_value = [
            ground_station_link
        ]

        network_builder.add_ground_station_links()

        assert network_builder.graph.has_edge("ground-1", "satellite-1")
        edge_data = network_builder.graph.get_edge_data("ground-1", "satellite-1")
        assert edge_data["disabled"] is False
