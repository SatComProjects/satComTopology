import copy

import pytest
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


def test_yaml_configuration_manager_uses_ballard_layout(tmp_path):
    """A delta shell's Ballard block distributes without resizing it.

    The original 3x4 / 53 deg / 15.5 rev/day inputs must survive the design
    step; only the inter-plane phasing is selected.
    """
    configuration = copy.deepcopy(MINIMAL_YAML_CONFIG)
    walker_shell = configuration["walker_shells"][0]
    walker_shell["constellation_property"].update(
        {
            "amount_of_orbit_plane": 3,
            "amount_of_satellite_per_orbit_plane": 4,
            "inclination": 53.0,
            "mean_revolution_per_day": 15.5,
            "design": {
                "method": "ballard",
                "phasing_factors": [1],
                "time_samples": 360,
            },
        }
    )

    config_path = tmp_path / "ballard_layout.yaml"
    config_path.write_text(yaml.safe_dump(configuration))

    simulation_manager = YamlConfigurationManager(str(config_path)).load_simulation()
    shells = simulation_manager.get_walker_shells()

    assert len(shells) == 1
    shell = shells[0]
    assert shell.amount_of_orbit_plane == 3
    assert shell.amount_of_satellite_per_orbit_plane == 4
    assert shell.inclination == 53.0
    assert shell.mean_revolution_per_day == 15.5
    assert len(simulation_manager.get_satellites()) == 12

    mean_anomalies = [
        round(float(satellite.movement_model.line2[43:51]), 3)
        for satellite in simulation_manager.get_satellites()[:8]
    ]
    assert mean_anomalies == [
        0.0,
        90.0,
        180.0,
        270.0,
        30.0,
        120.0,
        210.0,
        300.0,
    ]


def test_yaml_configuration_manager_uses_ballard_sizing(tmp_path):
    """`mode: sizing` changes the shell geometry before TLE generation."""
    configuration = copy.deepcopy(MINIMAL_YAML_CONFIG)
    walker_shell = configuration["walker_shells"][0]
    walker_shell["constellation_property"].update(
        {
            "amount_of_orbit_plane": 3,
            "amount_of_satellite_per_orbit_plane": 4,
            "inclination": 53.0,
            "mean_revolution_per_day": 15.5,
            "design": {
                "method": "ballard",
                "mode": "sizing",
                "plane_counts": [3],
                "phasing_factors": [1],
                "inclination_min_deg": 48.0,
                "inclination_max_deg": 54.0,
                "inclination_step_deg": 2.0,
                "time_samples": 360,
            },
        }
    )

    config_path = tmp_path / "ballard_sizing.yaml"
    config_path.write_text(yaml.safe_dump(configuration))

    simulation_manager = YamlConfigurationManager(str(config_path)).load_simulation()
    shell = simulation_manager.get_walker_shells()[0]

    assert shell.amount_of_orbit_plane == 3
    assert shell.amount_of_satellite_per_orbit_plane == 4
    assert shell.inclination == pytest.approx(50.7, abs=0.2)
    assert shell.mean_revolution_per_day == pytest.approx(6.75, abs=0.05)
    assert len(simulation_manager.get_satellites()) == 12
