from pathlib import Path

from sat_com_builder.configuration_manager import BaseConfigurationManager
from sat_com_builder.models import SimulationProperty
from sat_com_model.models import InterSatelliteLink, Satellite


def test_load_single_shell_simulation():
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

    assert len(simulation_manager.get_satellites()) == 300
    assert len(simulation_manager.get_ground_stations()) == 1

    assert all(
        1_600_000 <= satellite.get_coordinates().altitude <= 1_800_000
        for satellite in simulation_manager.get_satellites()
    )

    assert len(simulation_manager.simulation.walker_shells) == 1
    assert len(simulation_manager.simulation.ground_object_domains) == 1 + 1

    assert simulation_manager.simulation.ground_object_domains[0].identifier == "public"

    # Assert that every satellite have 4 isl
    assert all(
        len([link for link in satellite.links if isinstance(link, InterSatelliteLink)])
        == 4
        for satellite in simulation_manager.get_satellites()
    )
    assert len(simulation_manager.get_ground_stations()[0].links) == 16

    simulation_manager.get_ground_stations()[
        0
    ].ground_object_domain.ground_to_space_connections_strategy = (
        "best-angle-until-disconnection"
    )

    simulation_manager.time_manager.execute_actions()

    assert len(simulation_manager.get_ground_stations()[0].links) == 1

    only_existing_link = simulation_manager.get_ground_stations()[0].links[0]
    satellite_connected_to_the_link = (
        only_existing_link.destination
        if isinstance(only_existing_link.destination, Satellite)
        else only_existing_link.source
    )

    assert satellite_connected_to_the_link.topology_uniq_id == 201

    simulation_manager.time_manager.tick(seconds=60)

    only_existing_link = simulation_manager.get_ground_stations()[0].links[0]
    satellite_connected_to_the_link = (
        only_existing_link.destination
        if isinstance(only_existing_link.destination, Satellite)
        else only_existing_link.source
    )

    assert satellite_connected_to_the_link.topology_uniq_id == 201

    simulation_manager.time_manager.tick(seconds=60)

    only_existing_link = simulation_manager.get_ground_stations()[0].links[0]
    satellite_connected_to_the_link = (
        only_existing_link.destination
        if isinstance(only_existing_link.destination, Satellite)
        else only_existing_link.source
    )

    assert satellite_connected_to_the_link.topology_uniq_id == 201

    simulation_manager.time_manager.tick(seconds=240)

    only_existing_link = simulation_manager.get_ground_stations()[0].links[0]
    satellite_connected_to_the_link = (
        only_existing_link.destination
        if isinstance(only_existing_link.destination, Satellite)
        else only_existing_link.source
    )

    assert satellite_connected_to_the_link.topology_uniq_id == 201

    simulation_manager.time_manager.tick(seconds=10)

    only_existing_link = simulation_manager.get_ground_stations()[0].links[0]
    satellite_connected_to_the_link = (
        only_existing_link.destination
        if isinstance(only_existing_link.destination, Satellite)
        else only_existing_link.source
    )

    assert satellite_connected_to_the_link.topology_uniq_id == 200
