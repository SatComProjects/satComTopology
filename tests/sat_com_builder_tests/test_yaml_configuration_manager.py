import yaml

from sat_com_application.simulation_manager import SimulationManager
from sat_com_builder.configuration_manager import YamlConfigurationManager

MINIMAL_YAML_CONFIG = {
    "simulation_name": "Yaml Test simulation",
    "start_date": "2024-11-18 00:00:00.000000",
    "end_date": "2024-11-18 00:00:10.000000",
    "movement_model": "pyorbital",
    "distance_model": "sklearn",
    "ground_objects_properties": [],
    "walker_shells": [
        {
            "type": "delta",
            "constellation_property": {
                "identifier": "Walker",
                "amount_of_orbit_plane": 3,
                "amount_of_satellite_per_orbit_plane": 3,
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


def test_yaml_configuration_manager_loads_a_valid_simulation(tmp_path):
    """
    YamlConfigurationManager used to forward the raw YAML dict straight to
    BaseConfigurationManager instead of validating it into a SimulationProperty,
    which raised `AttributeError: 'dict' object has no attribute 'simulation_name'`.
    """
    config_path = tmp_path / "configuration.yaml"
    config_path.write_text(yaml.safe_dump(MINIMAL_YAML_CONFIG))

    yaml_configuration_manager = YamlConfigurationManager(str(config_path))

    simulation_manager = yaml_configuration_manager.load_simulation()

    assert isinstance(simulation_manager, SimulationManager)
    assert simulation_manager.simulation.simulation_name == "Yaml Test simulation"
    assert len(simulation_manager.get_satellites()) == 9
