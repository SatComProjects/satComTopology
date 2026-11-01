"""
NetworkX export of a real simulation: light default content, distance on
every edge, model dump on demand, JSON export on every supported networkx
version.
"""

import json
from pathlib import Path

import numpy as np
import pytest
from networkx.readwrite import json_graph

from sat_com_adapter.adapters import NetworkXAdapter
from sat_com_adapter.networkx_builder.networkx_builder import NetworkxBuilder
from sat_com_builder.configuration_manager import BaseConfigurationManager
from sat_com_builder.models import GroundConnectivityProperty, GroundObjectProperty
from sat_com_connectivity.utils import latitude_longitude_altitude_to_x_y_z
from sat_com_model.models import PointOfPresence, SpatialPosition
from tests.sat_com_topology_tests.test_multiple_satellite_configuration import (
    make_basic_4_isl_satellite_installation_intershell_unauthorized,
    make_small_single_walker_shell,
)

GROUND_STATIONS_FILE = (
    Path(__file__).resolve().parents[1] / "performance_scripts/100_ground_stations.txt"
)

NODE_KEYS = {
    "Satellite": {
        "type",
        "object_id",
        "topology_uniq_id",
        "name",
        "shell_id",
        "orbital_phase",
    },
    "GroundStation": {
        "type",
        "object_id",
        "topology_uniq_id",
        "label",
        "ground_domain",
    },
}
EDGE_KEYS = {"type", "source_id", "destination_id", "distance_km"}


@pytest.fixture
def simulation_manager():
    simulation_property = make_small_single_walker_shell(
        make_basic_4_isl_satellite_installation_intershell_unauthorized()
    )
    simulation_property.start_date = "2026-01-01 00:00:00"
    simulation_property.end_date = "2026-01-02 00:00:00"
    simulation_property.ground_objects_properties.append(
        GroundObjectProperty(
            identifier="Ground Stations",
            data_file=GROUND_STATIONS_FILE.as_posix(),
            type="ground_station",
            connectivity_properties=GroundConnectivityProperty(
                elevation_above_horizon=20,
                ground_to_space_connections_strategy="everything-visible",
            ),
        )
    )
    manager = BaseConfigurationManager(simulation_property).load_simulation()
    manager.time_manager.tick(seconds=60)
    return manager


def _straight_line_km(object_a, object_b) -> float:
    a = latitude_longitude_altitude_to_x_y_z(
        *object_a.get_coordinates().to_latitude_longitude_altitude()
    )
    b = latitude_longitude_altitude_to_x_y_z(
        *object_b.get_coordinates().to_latitude_longitude_altitude()
    )
    return float(np.linalg.norm(np.subtract(a, b))) / 1000.0


def test_default_graph_is_light(simulation_manager):
    graph = NetworkXAdapter(simulation_manager).create_full_networkx_graph()

    for _, data in graph.nodes(data=True):
        assert set(data) == NODE_KEYS[data["type"]]
    for _, _, data in graph.edges(data=True):
        expected = EDGE_KEYS | (
            {"direction"} if data["type"] == "InterSatelliteLink" else set()
        )
        assert set(data) == expected
        assert data["distance_km"] > 0


def test_edges_keep_the_link_orientation_and_distance(simulation_manager):
    graph = NetworkXAdapter(simulation_manager).create_full_networkx_graph()

    links = (
        simulation_manager.get_inter_satellites_links()
        + simulation_manager.get_ground_stations_links()
    )
    assert graph.number_of_edges() == len(links)
    for link in links:
        data = graph.get_edge_data(
            link.source.topology_uniq_id, link.destination.topology_uniq_id
        )
        assert data["source_id"] == link.source.topology_uniq_id
        assert data["destination_id"] == link.destination.topology_uniq_id
        assert data["distance_km"] == link.distance_km


def test_model_data_only_on_demand(simulation_manager):
    graph = NetworkXAdapter(simulation_manager).create_full_networkx_graph(
        export_model_data=True
    )

    assert all("model_data" in data for _, data in graph.nodes(data=True))
    assert all("model_data" in data for _, _, data in graph.edges(data=True))


def test_export_link_length_parameter_is_deprecated(simulation_manager):
    with pytest.warns(FutureWarning, match="distance_km"):
        NetworkXAdapter(simulation_manager).create_full_networkx_graph(
            export_link_length=True
        )


def test_adapt_without_building_first_writes_a_json_graph(simulation_manager, tmp_path):
    output = tmp_path / "graph.json"

    NetworkXAdapter(simulation_manager).adapt(str(output))

    exported = json.loads(output.read_text())
    assert "edges" in exported
    try:
        graph = json_graph.node_link_graph(exported, edges="edges")
    except TypeError:  # networkx < 3.4
        graph = json_graph.node_link_graph(exported, link="edges")
    assert graph.number_of_edges() == len(exported["edges"]) > 0


def test_ground_to_ground_link_gets_its_straight_line_distance(simulation_manager):
    ground_station = simulation_manager.get_ground_stations()[0]
    point_of_presence = PointOfPresence(object_id=1, label="Backbone PoP")
    point_of_presence.spatial_position = SpatialPosition(
        latitude=48.85, longitude=2.35, altitude=0.0
    )
    simulation_manager.add_point_of_presence(point_of_presence)
    link = simulation_manager.create_and_add_ground_object_link_connection(
        ground_station, point_of_presence
    )
    assert link.distance_km is None

    builder = NetworkxBuilder(simulation_manager)
    builder.add_topology_objects().add_static_ground_object_links()
    graph = builder.build()

    data = graph.get_edge_data(
        ground_station.topology_uniq_id, point_of_presence.topology_uniq_id
    )
    assert data["distance_km"] == pytest.approx(
        _straight_line_km(ground_station, point_of_presence), rel=1e-12
    )
    # The point of presence is a real node, not one created by the edge.
    assert graph.nodes[point_of_presence.topology_uniq_id]["label"] == "Backbone PoP"
