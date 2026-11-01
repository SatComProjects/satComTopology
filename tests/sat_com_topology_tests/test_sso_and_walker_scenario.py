from pathlib import Path

from sat_com_builder.configuration_manager import BaseConfigurationManager
from sat_com_builder.models import SimulationProperty
from sat_com_connectivity.inter_satellite_link_connectivity.strategies import (
    InterShellSSOPriorityConnectivity,
)
from sat_com_model.models import InterSatelliteLinkDirection


def test_load_sso_and_walker_scenario():
    base_dir = Path(__file__).parent
    print(base_dir)
    data_file_path = "./testing_ground_stations.txt"
    data_file_path = Path(base_dir) / data_file_path

    plain_config_walker = {
        "simulation_name": "Single Shell Simulation",
        "start_date": "2024-11-18 00:00:00.000000",
        "end_date": "2024-11-18 23:59:00.000000",
        "movement_model": "pyorbital",
        "distance_model": "sklearn",
        "ground_objects_properties": [
            {
                "identifier": "OneWeb Ground Station",
                "data_file": str(data_file_path),
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
                    "identifier": "Andromeda Walker",
                    "amount_of_orbit_plane": 20,
                    "amount_of_satellite_per_orbit_plane": 15,
                    "inclination": 70.0,
                    "phase_difference_between_satellites": True,
                    "mean_revolution_per_day": 12,
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
        "dawn_dusk_sso_shells": [
            {
                "constellation_property": {
                    "identifier": "Aurora SSO",
                    "altitude_in_km": 600.0,  # Specific to SSO
                    "amount_of_satellite": 80,
                },
                "orbital_connectivity_property": {
                    "adjacent_inter_satellite_shifting": 0,
                    "maximum_connected_ground_object": 10000,
                    "maximum_connected_user_terminal": 1000,
                    "maximum_connected_ground_station": 10,
                },
                "ground_object_white_list": [],
                "constellation_white_list": [],
            }
        ],
        "inter_satellite_link_connection_strategy": InterShellSSOPriorityConnectivity.type,
    }
    simulation_properties = SimulationProperty(**plain_config_walker)

    simulation_manager = BaseConfigurationManager(
        simulation_property=simulation_properties
    )
    simulation_manager = simulation_manager.load_simulation()

    # Assert that two addressing plan has been instantiated
    assert len(simulation_manager.shell_addressing_plans) == 2

    walker_shells = simulation_manager.get_walker_shells()
    sso_shells = simulation_manager.get_sso_shells()

    assert len(walker_shells) == 1
    assert len(sso_shells) == 1

    walker_shell = walker_shells[0]
    sso_shell = sso_shells[0]

    number_of_plan_for_walker_shell = 0
    number_of_plan_for_sso_shell = 0

    # Assert each shell (walker_shell,sso_shell)  has an addressing plan in simulation_manager.shell_addressing_plans
    for shell, plan in simulation_manager.shell_addressing_plans:
        if shell == sso_shell:
            number_of_plan_for_walker_shell += 1
        if shell == walker_shell:
            number_of_plan_for_sso_shell += 1

    assert number_of_plan_for_walker_shell == 1
    assert number_of_plan_for_sso_shell == 1

    for isl in simulation_manager.get_inter_satellites_links():
        if isl.inter_satellite_direction == InterSatelliteLinkDirection.INTER_SHELL:
            assert (
                isl.source_optical_terminal.host_satellite == isl.get_satellite_source()
            )
            assert (
                isl.destination_optical_terminal.host_satellite
                == isl.get_satellite_destination()
            )
            assert (
                isl.get_satellite_source().shell
                != isl.get_satellite_destination().shell
            )

        if isl.inter_satellite_direction == InterSatelliteLinkDirection.ORBITAL:
            assert (
                isl.source_optical_terminal.host_satellite == isl.get_satellite_source()
            )
            assert (
                isl.destination_optical_terminal.host_satellite
                == isl.get_satellite_destination()
            )
            assert (
                isl.get_satellite_source().shell
                == isl.get_satellite_destination().shell
            )

            if isl.get_satellite_source().shell == sso_shell:
                max_satellite_plane_id = sso_shell.amount_of_satellite - 1
            else:
                max_satellite_plane_id = (
                    walker_shell.amount_of_satellite_per_orbit_plane - 1
                )

            object_difference = abs(
                isl.get_satellite_source().object_id
                - isl.get_satellite_destination().object_id
            )

            assert (
                object_difference == 1 or object_difference == max_satellite_plane_id
            ), "Orbital Satellites Should have 1 different in object_id"

        if isl.inter_satellite_direction == InterSatelliteLinkDirection.ADJACENT:
            assert (
                isl.source_optical_terminal.host_satellite == isl.get_satellite_source()
                or isl.source_optical_terminal.host_satellite
                == isl.get_satellite_destination()
            )
            assert (
                isl.source_optical_terminal.target_optical_link_terminal.host_satellite
                == isl.get_satellite_source()
                or isl.source_optical_terminal.target_optical_link_terminal.host_satellite
                == isl.get_satellite_destination()
            )
            assert (
                isl.get_satellite_source().shell
                == isl.get_satellite_destination().shell
            )
            if isl.get_satellite_source().shell == sso_shell:
                assert (
                    False
                ), "SSO Shell cannot have adjacent ISL, Adjacent can only be INTERSHELL"
