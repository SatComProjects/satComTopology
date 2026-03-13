from sat_com_adapter.cesium_renderer.models import (
    CesiumProperty,
    ShellCustomProperty,
    CesiumRendererShellProperty,
)
from sat_com_adapter.cesium_renderer.renderers import CesiumHtmlRenderer
from sat_com_builder.configuration_manager import BaseConfigurationManager
from sat_com_builder.models import SimulationProperty
from sat_com_connectivity.inter_satellite_link_connectivity.optical_helpers import (
    compute_OISL_possible_links,
    compute_OISL_links,
)
from sat_com_model.models import (
    InterSatelliteLinkDirection,
    InterSatelliteLink,
    Satellite,
    OpticalInterSatelliteLink,
    OpticalConstraint,
)


def test_compute_oils_connectivity_between_adjacent_satellites():
    # small constellation walker configuration (10x10):
    plain_config_walker = {
        "simulation_name": "Single Shell Simulation",
        "start_date": "2024-11-18 00:00:00.000000",
        "end_date": "2024-11-18 23:59:00.000000",
        "movement_model": "pyorbital",
        "distance_model": "sklearn",
        "walker_shells": [
            {
                "type": "delta",
                "constellation_property": {
                    "identifier": "Andromeda Walker",
                    "amount_of_orbit_plane": 10,
                    "amount_of_satellite_per_orbit_plane": 10,
                    "inclination": 53.0,
                    "phase_difference_between_satellites": True,
                    "mean_revolution_per_day": 13,
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

    # load simulation
    simulation_properties = SimulationProperty(**plain_config_walker)
    base_config_manager = BaseConfigurationManager(
        simulation_property=simulation_properties
    )
    simulation_manager = base_config_manager.load_simulation()

    first_satellite = simulation_manager.get_satellites()[0]

    adjacent_links = [
        link
        for link in first_satellite.links
        if (
            isinstance(link, InterSatelliteLink)
            and link.inter_satellite_direction == InterSatelliteLinkDirection.ADJACENT
        )
    ]

    assert (
        len(adjacent_links) == 2
    ), "There should be  2 adjacent link for the first satellite in the walker constellation"

    adjacent_satellites = [
        satellite
        for satellite in [
            adjacent_links[0].source,
            adjacent_links[0].destination,
            adjacent_links[1].source,
            adjacent_links[1].destination,
        ]
        if satellite.topology_uniq_id != first_satellite.topology_uniq_id
        and isinstance(satellite, Satellite)
    ]

    assert (
        len(first_satellite.optical_link_terminals) >= 1
    ), "The first satellite should have 1 optical link terminal"

    for adjacent_satellite in adjacent_satellites:
        assert (
            len(adjacent_satellite.optical_link_terminals) >= 1
        ), "The adjacent satellite should have 1 optical link terminal"

    constraints = compute_OISL_links(
        satellites_group_1=[first_satellite],
        satellites_group_2=[
            satellite
            for satellite in simulation_manager.get_satellites()
            if satellite != first_satellite
        ],
        maximum_range_to_filter_in_km=7800,
    )

    # export cesium
    simulation_renderer = CesiumHtmlRenderer(
        simulation_manager=simulation_manager, cesium_renderer_property=CesiumProperty()
    )
    simulation_renderer.add_satellites()

    for constraint in constraints:
        print(
            f"Constraint between {constraint.satellite_a.satellite_name} and {constraint.satellite_b.satellite_name}:"
        )
        optical_intersatellite_link = OpticalInterSatelliteLink()

        optical_intersatellite_link.connect(
            source=constraint.satellite_a,
            destination=constraint.satellite_b,
            inter_satellite_direction=InterSatelliteLinkDirection.UNDEFINED,
        )

        optical_intersatellite_link.source_constraint = OpticalConstraint(
            azimuth_angle_degree=constraint.constraint_a_to_b.azimuth_angle_degree,
            elevation_angle_degree=constraint.constraint_a_to_b.elevation_angle_degree,
            range_distance_km=constraint.constraint_a_to_b.range_distance_km,
            angular_velocity_rate_degree_per_second=constraint.constraint_b_to_a.angular_velocity_rate_degree_per_second,
        )

        optical_intersatellite_link.destination_constraint = OpticalConstraint(
            azimuth_angle_degree=constraint.constraint_b_to_a.azimuth_angle_degree,
            elevation_angle_degree=constraint.constraint_b_to_a.elevation_angle_degree,
            range_distance_km=constraint.constraint_b_to_a.range_distance_km,
            angular_velocity_rate_degree_per_second=constraint.constraint_b_to_a.angular_velocity_rate_degree_per_second,
        )

        constraint.terminal_a.possible_links.append(optical_intersatellite_link)

        constraint.terminal_b.possible_links.append(optical_intersatellite_link)

        simulation_renderer.add_link(
            optical_intersatellite_link,
            color="GREEN" if constraint.bidirectional_possible else "RED",
        )

    html_code = simulation_renderer.render()


def test_connectivity_between_sso_and_walker_shells():
    # small constellation walker configuration (10x10):
    plain_config_walker = {
        "simulation_name": "Single Shell Simulation",
        "start_date": "2024-11-18 00:00:00.000000",
        "end_date": "2024-11-18 23:59:00.000000",
        "movement_model": "pyorbital",
        "distance_model": "sklearn",
        "walker_shells": [
            {
                "type": "delta",
                "constellation_property": {
                    "identifier": "Andromeda Walker",
                    "amount_of_orbit_plane": 10,
                    "amount_of_satellite_per_orbit_plane": 10,
                    "inclination": 53.0,
                    "phase_difference_between_satellites": True,
                    "mean_revolution_per_day": 13,
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
        "dawn_dusk_sso_shells": [
            {
                "constellation_property": {
                    "identifier": "Aurora SSO",
                    "altitude_in_km": 600.0,  # Specific to SSO
                    "amount_of_satellite": 80,
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
                "constellation_white_list": [],
            }
        ],
    }

    # load simulation
    simulation_properties = SimulationProperty(**plain_config_walker)
    base_config_manager = BaseConfigurationManager(
        simulation_property=simulation_properties
    )
    simulation_manager = base_config_manager.load_simulation()

    constraints = compute_OISL_possible_links(
        satellites_group_1=simulation_manager.get_sso_shell_satellites(),
        satellites_group_2=simulation_manager.get_walker_shell_satellites(),
    )

    cesium_property = CesiumProperty()
    cesium_property.shell_custom_properties.append(
        ShellCustomProperty(
            shell_identifier="Aurora SSO",
            cesium_property=CesiumRendererShellProperty(
                ascending_satellite_color="ORANGE",
                descending_satellite_color="ORANGE",
            ),
        )
    )
    # export cesium
    simulation_renderer = CesiumHtmlRenderer(
        simulation_manager=simulation_manager, cesium_renderer_property=cesium_property
    )
    simulation_renderer.add_satellites()

    for constraint in constraints:
        print(
            f"Constraint between {constraint.satellite_a.satellite_name} and {constraint.satellite_b.satellite_name}:"
        )
        optical_intersatellite_link = OpticalInterSatelliteLink()

        optical_intersatellite_link.connect(
            source=constraint.satellite_a,
            destination=constraint.satellite_b,
            inter_satellite_direction=InterSatelliteLinkDirection.UNDEFINED,
        )

        optical_intersatellite_link.source_constraint = OpticalConstraint(
            azimuth_angle_degree=constraint.constraint_a_to_b.azimuth_angle_degree,
            elevation_angle_degree=constraint.constraint_a_to_b.elevation_angle_degree,
            range_distance_km=constraint.constraint_a_to_b.range_distance_km,
            angular_velocity_rate_degree_per_second=constraint.constraint_b_to_a.angular_velocity_rate_degree_per_second,
        )

        optical_intersatellite_link.destination_constraint = OpticalConstraint(
            azimuth_angle_degree=constraint.constraint_b_to_a.azimuth_angle_degree,
            elevation_angle_degree=constraint.constraint_b_to_a.elevation_angle_degree,
            range_distance_km=constraint.constraint_b_to_a.range_distance_km,
            angular_velocity_rate_degree_per_second=constraint.constraint_b_to_a.angular_velocity_rate_degree_per_second,
        )

        constraint.terminal_a.possible_links.append(optical_intersatellite_link)

        constraint.terminal_b.possible_links.append(optical_intersatellite_link)

        simulation_renderer.add_link(
            optical_intersatellite_link,
            color="LIGHTGREEN" if constraint.bidirectional_possible else "RED",
        )

    html_code = simulation_renderer.render()
