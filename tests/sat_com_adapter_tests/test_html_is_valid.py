from pathlib import Path

from sat_com_adapter.cesium_renderer.models import CesiumProperty
from sat_com_adapter.cesium_renderer.renderers import CesiumHtmlRenderer
from sat_com_builder.configuration_manager import BaseConfigurationManager
from sat_com_builder.models import SimulationProperty

import esprima
from bs4 import BeautifulSoup


def test_cesium_html_renderer_returns_valid_html():
    base_dir = Path(__file__).parent
    data_file_path = "./testing_ground_stations.txt"
    data_file_path = Path(base_dir) / data_file_path

    plain_config_walker = {
        "simulation_name": "Small Single Shell Simulation",
        "start_date": "2024-11-18 00:00:00.000000",
        "end_date": "2024-11-25 00:00:00.000000",
        "movement_model": "pyorbital",
        "distance_model": "sklearn",
        "ground_objects_properties": [
            {
                "identifier": "OneWeb Ground Station",
                "data_file": data_file_path.as_posix(),
                "type": "ground_station",
                "connectivity_properties": {
                    "elevation_above_horizon": 20,
                    "ground_to_space_connections_strategy": "everything-visible",
                },
            }
        ],
        "walker_shells": [
            {
                "type": "delta",
                "constellation_property": {
                    "identifier": "Walker",
                    "amount_of_orbit_plane": 15,
                    "amount_of_satellite_per_orbit_plane": 15,
                    "inclination": 53.0,
                    "phase_difference_between_satellites": True,
                    "mean_revolution_per_day": 15.5,
                },
                "orbital_connectivity_property": {
                    "adjacent_inter_satellite_shifting": 0,
                    "maximum_inter_satellite_count": 4,
                    "maximum_inter_satellite_range_distance": 1000,
                    "maximum_ground_station_range": 5000,
                    "maximum_user_terminal_range": 1000,
                    "maximum_connected_ground_object": 10000,
                    "maximum_connected_user_terminal": 1000,
                    "maximum_connected_ground_station": 10,
                },
                "ground_object_white_list": [],
            }
        ],
    }

    simulation_properties = SimulationProperty(**plain_config_walker)

    simulation_manager = BaseConfigurationManager(
        simulation_property=simulation_properties
    )
    simulation_manager = simulation_manager.load_simulation()

    simulation_renderer = CesiumHtmlRenderer(
        simulation_manager=simulation_manager, cesium_renderer_property=CesiumProperty()
    )
    html_code = simulation_renderer.render()

    soup = BeautifulSoup(html_code, "html.parser")

    for script in soup.find_all("script"):
        code = script.string
        if code and code.strip():
            esprima.parseScript(code)
