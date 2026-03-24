import time
from datetime import timedelta

from sat_com_application.simulation_manager import SimulationManager
from sat_com_builder.configuration_manager import BaseConfigurationManager
from sat_com_builder.links.inter_satellite_link_generator import (
    generate_walker_delta_constellation_grid,
)
from sat_com_builder.models import (
    SimulationProperty,
    WalkerShellProperty,
    OrbitalConnectivityProperty,
    SatelliteProperty,
    OpticalTerminalInstallationProperty,
    InterSatelliteLinkOrientationProperty,
    DawnDuskSunSynchronousOrbitShellProperty,
    AddressingPlanType,
    OpticalTerminalProperty,
)
from sat_com_connectivity.inter_satellite_link_connectivity.strategies import (
    IntraShellStaticConnectivity,
    InterShellSSOPriorityConnectivity,
)
from sat_com_constellation.models import (
    WalkerConstellationProperty,
    DawnDuskSunSynchronousOrbitConstellationProperty,
)
from sat_com_model.models import (
    InterSatelliteLinkDirection,
    InterSatelliteLink,
    InterSatelliteLinkOrientation,
)


def _timed(label: str):
    start = time.perf_counter()

    def end():
        duration = time.perf_counter() - start
        print(f"{label:<70} | {duration:.4f} s")

    return end


def make_simulation_property():
    return SimulationProperty()


def make_walker_shell_property():
    return WalkerShellProperty(
        constellation_property=WalkerConstellationProperty(
            inclination=53,
            identifier="Walker Test",
            amount_of_orbit_plane=25,
            amount_of_satellite_per_orbit_plane=25,
            mean_revolution_per_day=15,
            phase_difference_between_satellites=True,
        ),
        orbital_connectivity_property=OrbitalConnectivityProperty(),
        satellite_property=SatelliteProperty(),
    )


def make_small_walker_shell_property():
    return WalkerShellProperty(
        constellation_property=WalkerConstellationProperty(
            inclination=53,
            identifier="Walker Test",
            amount_of_orbit_plane=10,
            amount_of_satellite_per_orbit_plane=10,
            mean_revolution_per_day=15,
            phase_difference_between_satellites=True,
        ),
        orbital_connectivity_property=OrbitalConnectivityProperty(),
        satellite_property=SatelliteProperty(),
    )


def make_sso_shell_property():
    return DawnDuskSunSynchronousOrbitShellProperty(
        orbital_connectivity_property=OrbitalConnectivityProperty(),
        satellite_property=SatelliteProperty(),
        constellation_property=DawnDuskSunSynchronousOrbitConstellationProperty(
            identifier="SSo Aurora",
            amount_of_satellite=80,
            altitude_in_km=500,
        ),
    )


def make_three_isl_configuration(M, N) -> SimulationProperty:
    walker_constellation_property = WalkerConstellationProperty(
        inclination=53,
        identifier="Starlink group 7",
        mean_revolution_per_day=15.3,
        phase_difference_between_satellites=True,
        amount_of_orbit_plane=M,
        amount_of_satellite_per_orbit_plane=N,
    )

    walker_shell_property = WalkerShellProperty(
        constellation_property=walker_constellation_property,
        orbital_connectivity_property=OrbitalConnectivityProperty(
            adjacent_inter_satellite_shifting=0
        ),
        static_addressing_plan=AddressingPlanType.CHECKERBOARD_WALKER_DELTA,
        satellite_property=SatelliteProperty(
            optical_inter_satellite_link_installations=[
                OpticalTerminalInstallationProperty(
                    azimuth_angle_configuration=0.0,
                    elevation_angle_configuration=-180,
                    descriptor=InterSatelliteLinkOrientationProperty.INTRA_PLANE_FORWARD,
                    orientation_possibilities=[
                        InterSatelliteLinkOrientationProperty.INTRA_PLANE_FORWARD,
                    ],
                ),
                OpticalTerminalInstallationProperty(
                    azimuth_angle_configuration=-180.0,
                    elevation_angle_configuration=-180,
                    descriptor=InterSatelliteLinkOrientationProperty.INTRA_PLANE_BACKWARD,
                    orientation_possibilities=[
                        InterSatelliteLinkOrientationProperty.INTRA_PLANE_BACKWARD,
                    ],
                ),
                OpticalTerminalInstallationProperty(
                    azimuth_angle_configuration=0.0,
                    elevation_angle_configuration=-180,
                    descriptor=InterSatelliteLinkOrientationProperty.INTER_PLANE_RIGHT,
                    orientation_possibilities=[
                        InterSatelliteLinkOrientationProperty.INTER_PLANE_RIGHT,
                        InterSatelliteLinkOrientationProperty.INTER_PLANE_LEFT,
                    ],
                    optical_terminal_property=OpticalTerminalProperty(
                        max_azimuth_degrees=180
                    ),
                ),
            ]
        ),
    )
    simulation_property = SimulationProperty(
        start_date="01/01/2026 00:00:00",
        end_date="01/01/2026 01:00:00",
        walker_shells=[walker_shell_property],
        inter_satellite_link_connection_strategy=IntraShellStaticConnectivity.type,
        simulation_name="Starlink Gen2 Shell 3ISLs",
    )

    return simulation_property


def make_basic_4_isl_satellite_installation_intershell_unauthorized():
    return SatelliteProperty(
        optical_inter_satellite_link_installations=[
            OpticalTerminalInstallationProperty(
                azimuth_angle_configuration=0.0,
                elevation_angle_configuration=-180,
                descriptor=InterSatelliteLinkOrientationProperty.INTRA_PLANE_FORWARD,
                orientation_possibilities=[
                    InterSatelliteLinkOrientationProperty.INTRA_PLANE_FORWARD,
                ],
            ),
            OpticalTerminalInstallationProperty(
                azimuth_angle_configuration=90.0,
                elevation_angle_configuration=-180,
                descriptor=InterSatelliteLinkOrientationProperty.INTER_PLANE_LEFT,
                orientation_possibilities=[
                    InterSatelliteLinkOrientationProperty.INTER_PLANE_LEFT,
                ],
            ),
            OpticalTerminalInstallationProperty(
                azimuth_angle_configuration=-90.0,
                elevation_angle_configuration=-180,
                descriptor=InterSatelliteLinkOrientationProperty.INTER_PLANE_RIGHT,
                orientation_possibilities=[
                    InterSatelliteLinkOrientationProperty.INTER_PLANE_RIGHT,
                ],
            ),
            OpticalTerminalInstallationProperty(
                azimuth_angle_configuration=-180.0,
                elevation_angle_configuration=-180,
                descriptor=InterSatelliteLinkOrientationProperty.INTRA_PLANE_BACKWARD,
                orientation_possibilities=[
                    InterSatelliteLinkOrientationProperty.INTRA_PLANE_BACKWARD,
                ],
            ),
        ]
    )


def make_basic_4_isl_satellite_installation_intershell_authorized_on_adjacent():
    return SatelliteProperty(
        optical_inter_satellite_link_installations=[
            OpticalTerminalInstallationProperty(
                azimuth_angle_configuration=0.0,
                elevation_angle_configuration=-180,
                descriptor=InterSatelliteLinkOrientationProperty.INTRA_PLANE_FORWARD,
                orientation_possibilities=[
                    InterSatelliteLinkOrientationProperty.INTRA_PLANE_FORWARD,
                ],
            ),
            OpticalTerminalInstallationProperty(
                azimuth_angle_configuration=90.0,
                elevation_angle_configuration=-180,
                descriptor=InterSatelliteLinkOrientationProperty.INTER_PLANE_LEFT,
                orientation_possibilities=[
                    InterSatelliteLinkOrientationProperty.INTER_PLANE_LEFT,
                    InterSatelliteLinkOrientationProperty.INTER_SHELL_LEFT,
                ],
            ),
            OpticalTerminalInstallationProperty(
                azimuth_angle_configuration=-90.0,
                elevation_angle_configuration=-180,
                descriptor=InterSatelliteLinkOrientationProperty.INTER_PLANE_RIGHT,
                orientation_possibilities=[
                    InterSatelliteLinkOrientationProperty.INTER_PLANE_RIGHT,
                    InterSatelliteLinkOrientationProperty.INTER_SHELL_RIGHT,
                ],
            ),
            OpticalTerminalInstallationProperty(
                azimuth_angle_configuration=-180.0,
                elevation_angle_configuration=-180,
                descriptor=InterSatelliteLinkOrientationProperty.INTRA_PLANE_BACKWARD,
                orientation_possibilities=[
                    InterSatelliteLinkOrientationProperty.INTRA_PLANE_BACKWARD,
                ],
            ),
        ]
    )


def make_2_isl_intra_plane_only():
    return SatelliteProperty(
        optical_inter_satellite_link_installations=[
            OpticalTerminalInstallationProperty(
                azimuth_angle_configuration=0.0,
                elevation_angle_configuration=-180,
                descriptor=InterSatelliteLinkOrientationProperty.INTRA_PLANE_FORWARD,
                orientation_possibilities=[
                    InterSatelliteLinkOrientationProperty.INTRA_PLANE_FORWARD,
                ],
            ),
            OpticalTerminalInstallationProperty(
                azimuth_angle_configuration=-180.0,
                elevation_angle_configuration=-180,
                descriptor=InterSatelliteLinkOrientationProperty.INTRA_PLANE_BACKWARD,
                orientation_possibilities=[
                    InterSatelliteLinkOrientationProperty.INTRA_PLANE_BACKWARD,
                ],
            ),
        ]
    )


def make_3_isl_asymmetric():
    return SatelliteProperty(
        optical_inter_satellite_link_installations=[
            # Intra-plane forward
            OpticalTerminalInstallationProperty(
                azimuth_angle_configuration=0.0,
                elevation_angle_configuration=-180,
                descriptor=InterSatelliteLinkOrientationProperty.INTRA_PLANE_FORWARD,
                orientation_possibilities=[
                    InterSatelliteLinkOrientationProperty.INTRA_PLANE_FORWARD,
                ],
            ),
            # Intra-plane backward
            OpticalTerminalInstallationProperty(
                azimuth_angle_configuration=-180.0,
                elevation_angle_configuration=-180,
                descriptor=InterSatelliteLinkOrientationProperty.INTRA_PLANE_BACKWARD,
                orientation_possibilities=[
                    InterSatelliteLinkOrientationProperty.INTRA_PLANE_BACKWARD,
                ],
            ),
            # One inter-plane only (e.g., right)
            OpticalTerminalInstallationProperty(
                azimuth_angle_configuration=-90.0,
                elevation_angle_configuration=-180,
                descriptor=InterSatelliteLinkOrientationProperty.INTER_PLANE_RIGHT,
                orientation_possibilities=[
                    InterSatelliteLinkOrientationProperty.INTER_PLANE_RIGHT,
                ],
            ),
        ]
    )


def make_5_isl_with_single_intershell():
    return SatelliteProperty(
        optical_inter_satellite_link_installations=[
            # Intra-plane
            OpticalTerminalInstallationProperty(
                azimuth_angle_configuration=0.0,
                elevation_angle_configuration=-180,
                descriptor=InterSatelliteLinkOrientationProperty.INTRA_PLANE_FORWARD,
                orientation_possibilities=[
                    InterSatelliteLinkOrientationProperty.INTRA_PLANE_FORWARD,
                ],
            ),
            OpticalTerminalInstallationProperty(
                azimuth_angle_configuration=-180.0,
                elevation_angle_configuration=-180,
                descriptor=InterSatelliteLinkOrientationProperty.INTRA_PLANE_BACKWARD,
                orientation_possibilities=[
                    InterSatelliteLinkOrientationProperty.INTRA_PLANE_BACKWARD,
                ],
            ),
            # Inter-plane
            OpticalTerminalInstallationProperty(
                azimuth_angle_configuration=90.0,
                elevation_angle_configuration=-180,
                descriptor=InterSatelliteLinkOrientationProperty.INTER_PLANE_LEFT,
                orientation_possibilities=[
                    InterSatelliteLinkOrientationProperty.INTER_PLANE_LEFT,
                ],
            ),
            OpticalTerminalInstallationProperty(
                azimuth_angle_configuration=-90.0,
                elevation_angle_configuration=-180,
                descriptor=InterSatelliteLinkOrientationProperty.INTER_PLANE_RIGHT,
                orientation_possibilities=[
                    InterSatelliteLinkOrientationProperty.INTER_PLANE_RIGHT,
                ],
            ),
            # Inter-shell (single, constrained)
            OpticalTerminalInstallationProperty(
                azimuth_angle_configuration=0.0,
                elevation_angle_configuration=0,  # often different elevation
                descriptor=InterSatelliteLinkOrientationProperty.INTER_SHELL_FORWARD,
                orientation_possibilities=[
                    InterSatelliteLinkOrientationProperty.INTER_SHELL_FORWARD,
                ],
            ),
        ]
    )


def make_6_isl_dual_intershell():
    return SatelliteProperty(
        optical_inter_satellite_link_installations=[
            # Intra-plane
            OpticalTerminalInstallationProperty(
                azimuth_angle_configuration=0.0,
                elevation_angle_configuration=-180,
                descriptor=InterSatelliteLinkOrientationProperty.INTRA_PLANE_FORWARD,
                orientation_possibilities=[
                    InterSatelliteLinkOrientationProperty.INTRA_PLANE_FORWARD,
                ],
            ),
            OpticalTerminalInstallationProperty(
                azimuth_angle_configuration=-180.0,
                elevation_angle_configuration=-180,
                descriptor=InterSatelliteLinkOrientationProperty.INTRA_PLANE_BACKWARD,
                orientation_possibilities=[
                    InterSatelliteLinkOrientationProperty.INTRA_PLANE_BACKWARD,
                ],
            ),
            # Inter-plane
            OpticalTerminalInstallationProperty(
                azimuth_angle_configuration=90.0,
                elevation_angle_configuration=-180,
                descriptor=InterSatelliteLinkOrientationProperty.INTER_PLANE_LEFT,
                orientation_possibilities=[
                    InterSatelliteLinkOrientationProperty.INTER_PLANE_LEFT,
                ],
            ),
            OpticalTerminalInstallationProperty(
                azimuth_angle_configuration=-90.0,
                elevation_angle_configuration=-180,
                descriptor=InterSatelliteLinkOrientationProperty.INTER_PLANE_RIGHT,
                orientation_possibilities=[
                    InterSatelliteLinkOrientationProperty.INTER_PLANE_RIGHT,
                ],
            ),
            # Inter-shell (forward/backward)
            OpticalTerminalInstallationProperty(
                azimuth_angle_configuration=0.0,
                elevation_angle_configuration=0,
                descriptor=InterSatelliteLinkOrientationProperty.INTER_SHELL_FORWARD,
                orientation_possibilities=[
                    InterSatelliteLinkOrientationProperty.INTER_SHELL_FORWARD,
                ],
            ),
            OpticalTerminalInstallationProperty(
                azimuth_angle_configuration=-180.0,
                elevation_angle_configuration=0,
                descriptor=InterSatelliteLinkOrientationProperty.INTER_SHELL_BACKWARD,
                orientation_possibilities=[
                    InterSatelliteLinkOrientationProperty.INTER_SHELL_BACKWARD,
                ],
            ),
        ]
    )


def make_sso_and_walker_shell_only_sso_can_inter_shell(
    satellite_sso_config, walker_shell_sat_config
):
    simulation_properties = make_simulation_property()
    walker_shell_properties = make_walker_shell_property()
    simulation_properties.walker_shells.append(walker_shell_properties)
    walker_shell_properties.satellite_property = walker_shell_sat_config

    sso_shell_config = make_sso_shell_property()
    sso_shell_config.satellite_property = satellite_sso_config

    simulation_properties.dawn_dusk_sso_shells.append(sso_shell_config)

    return simulation_properties


def make_sso_and_walker_shell_both_can_inter_shell(
    satellite_sso_config, walker_shell_sat_config
):
    simulation_properties = make_simulation_property()
    walker_shell_properties = make_walker_shell_property()
    simulation_properties.walker_shells.append(walker_shell_properties)
    walker_shell_properties.satellite_property = walker_shell_sat_config

    sso_shell_config = make_sso_shell_property()
    sso_shell_config.satellite_property = satellite_sso_config

    simulation_properties.dawn_dusk_sso_shells.append(sso_shell_config)

    return simulation_properties


def make_small_single_walker_shell(walker_shell_sat_config):
    simulation_properties = make_simulation_property()
    walker_shell_properties = make_small_walker_shell_property()
    simulation_properties.walker_shells.append(walker_shell_properties)
    walker_shell_properties.satellite_property = walker_shell_sat_config
    return simulation_properties


def test_that_authorized_inter_shell_satellite_do_not_establish_inter_shell_with_this_strategy():

    walker_shell_sat_config = (
        make_basic_4_isl_satellite_installation_intershell_authorized_on_adjacent()
    )

    satellite_sso_config = (
        make_basic_4_isl_satellite_installation_intershell_authorized_on_adjacent()
    )

    simulation_property = make_sso_and_walker_shell_only_sso_can_inter_shell(
        satellite_sso_config, walker_shell_sat_config
    )

    # We configure the IntraShell Strategy, the one that do not allow inter-shell
    simulation_property.inter_satellite_link_connection_strategy = (
        IntraShellStaticConnectivity.type
    )

    simulation_config = BaseConfigurationManager(
        simulation_property=simulation_property
    )
    simulation_manager = simulation_config.load_simulation()

    # Assert not inter-shell link as only one constellation has inter-shell authorized terminal
    for link in simulation_manager.get_inter_satellites_links():
        assert link.inter_satellite_direction != InterSatelliteLinkDirection.INTER_SHELL
        assert (
            link.get_satellite_source().shell == link.get_satellite_destination().shell
        )

    # Record ticking time:
    end = _timed("Ticking Time")
    simulation_manager.time_manager.tick(seconds=60)
    end()


def test_that_unauthorized_inter_shell_satellite_do_not_establish_inter_shell():

    walker_shell_sat_config = (
        make_basic_4_isl_satellite_installation_intershell_authorized_on_adjacent()
    )

    satellite_sso_config = (
        make_basic_4_isl_satellite_installation_intershell_unauthorized()
    )

    simulation_property = make_sso_and_walker_shell_only_sso_can_inter_shell(
        satellite_sso_config, walker_shell_sat_config
    )

    # We configure the IntraShell Strategy, the one that do not allow inter-shell
    simulation_property.inter_satellite_link_connection_strategy = (
        InterShellSSOPriorityConnectivity.type
    )

    simulation_config = BaseConfigurationManager(
        simulation_property=simulation_property
    )
    simulation_manager = simulation_config.load_simulation()

    # Assert not inter-shell link as only one constellation has inter-shell authorized terminal

    for link in simulation_manager.get_inter_satellites_links():
        assert link.inter_satellite_direction != InterSatelliteLinkDirection.INTER_SHELL
        assert (
            link.get_satellite_source().shell == link.get_satellite_destination().shell
        )


def test_inter_shell_links_are_created_when_both_shells_allow_it():
    walker_shell_sat_config = (
        make_basic_4_isl_satellite_installation_intershell_authorized_on_adjacent()
    )

    satellite_sso_config = (
        make_basic_4_isl_satellite_installation_intershell_authorized_on_adjacent()
    )

    simulation_property = make_sso_and_walker_shell_both_can_inter_shell(
        satellite_sso_config, walker_shell_sat_config
    )

    simulation_property.inter_satellite_link_connection_strategy = (
        InterShellSSOPriorityConnectivity.type
    )

    simulation_config = BaseConfigurationManager(
        simulation_property=simulation_property
    )
    simulation_manager = simulation_config.load_simulation()

    # Assert that satellite attitude is near SSO shell altitude
    for satellite in simulation_manager.get_walker_shell_satellites():
        assert satellite.get_coordinates().altitude / 1000 >= 500 - 100
        assert satellite.get_coordinates().altitude / 1000 <= 500 + 100

    isl_shell_detected = [
        link
        for link in simulation_manager.get_inter_satellites_links()
        if link.get_satellite_source().shell != link.get_satellite_destination().shell
    ]

    assert len(isl_shell_detected) > 0

    inter_shell_links = [
        link
        for link in simulation_manager.get_inter_satellites_links()
        if link.inter_satellite_direction == InterSatelliteLinkDirection.INTER_SHELL
    ]

    # At least one inter-shell link must exist
    assert len(inter_shell_links) > 0


def test_inter_satellite_link_terminals_are_consistent():
    walker_shell_sat_config = make_6_isl_dual_intershell()
    satellite_sso_config = make_6_isl_dual_intershell()

    simulation_property = make_sso_and_walker_shell_only_sso_can_inter_shell(
        satellite_sso_config, walker_shell_sat_config
    )

    simulation_property.inter_satellite_link_connection_strategy = (
        InterShellSSOPriorityConnectivity.type
    )

    simulation_config = BaseConfigurationManager(
        simulation_property=simulation_property
    )
    simulation_manager = simulation_config.load_simulation()

    for link in simulation_manager.get_inter_satellites_links():
        source_terminal = link.source_optical_terminal
        dest_terminal = link.destination_optical_terminal

        # Terminals must exist
        assert source_terminal is not None
        assert dest_terminal is not None

        # Terminals must point back to the link
        assert source_terminal.link == link
        assert dest_terminal.link == link

        # Terminals must point to each other
        assert source_terminal.target_optical_link_terminal == dest_terminal
        assert dest_terminal.target_optical_link_terminal == source_terminal


def test_no_terminal_is_used_multiple_times():
    walker_shell_sat_config = make_6_isl_dual_intershell()
    satellite_sso_config = make_6_isl_dual_intershell()

    simulation_property = make_sso_and_walker_shell_only_sso_can_inter_shell(
        satellite_sso_config, walker_shell_sat_config
    )

    simulation_property.inter_satellite_link_connection_strategy = (
        InterShellSSOPriorityConnectivity.type
    )

    simulation_config = BaseConfigurationManager(
        simulation_property=simulation_property
    )
    simulation_manager = simulation_config.load_simulation()

    used_terminals = set()

    for link in simulation_manager.get_inter_satellites_links():
        for terminal in (
            link.source_optical_terminal,
            link.destination_optical_terminal,
        ):
            assert terminal not in used_terminals
            used_terminals.add(terminal)


def test_links_remain_consistent_after_time_tick():
    walker_shell_sat_config = make_5_isl_with_single_intershell()
    satellite_sso_config = make_5_isl_with_single_intershell()

    simulation_property = make_sso_and_walker_shell_only_sso_can_inter_shell(
        satellite_sso_config, walker_shell_sat_config
    )

    simulation_property.inter_satellite_link_connection_strategy = (
        InterShellSSOPriorityConnectivity.type
    )

    simulation_config = BaseConfigurationManager(
        simulation_property=simulation_property
    )
    simulation_manager = simulation_config.load_simulation()

    simulation_manager.time_manager.verbose = True
    simulation_manager.time_manager.tick(seconds=60)

    for link in simulation_manager.get_inter_satellites_links():
        # Link endpoints must still be valid satellites
        assert link.get_satellite_source() is not None
        assert link.get_satellite_destination() is not None

        # Terminals must still be consistent
        if link.source_optical_terminal:
            assert link.source_optical_terminal.link == link

        if link.destination_optical_terminal:
            assert link.destination_optical_terminal.link == link


def test_that_5_isl_configuration_always_maintain_adjacent_orbital_intra_and_uses_fifth_one_as_inter_shell():
    walker_shell_sat_config = make_5_isl_with_single_intershell()
    satellite_sso_config = make_5_isl_with_single_intershell()

    simulation_property = make_sso_and_walker_shell_only_sso_can_inter_shell(
        satellite_sso_config, walker_shell_sat_config
    )
    simulation_config = BaseConfigurationManager(
        simulation_property=simulation_property
    )
    simulation_manager = simulation_config.load_simulation()

    for satellite in simulation_manager.get_walker_shell_satellites():
        isl_links = [
            link for link in satellite.links if isinstance(link, InterSatelliteLink)
        ]
        assert len(isl_links) >= 4

        if len(isl_links) == 5:
            for link in isl_links:
                if (
                    link.get_satellite_source().shell
                    != link.get_satellite_destination().shell
                ):
                    assert (
                        link.inter_satellite_direction
                        == InterSatelliteLinkDirection.INTER_SHELL
                    )
                    assert (
                        InterSatelliteLinkOrientation.INTER_PLANE_RIGHT
                        not in link.source_optical_terminal.orientation_possibilities
                    )
                    assert (
                        InterSatelliteLinkOrientation.INTER_PLANE_LEFT
                        not in link.source_optical_terminal.orientation_possibilities
                    )
                    assert (
                        InterSatelliteLinkOrientation.INTRA_PLANE_FORWARD
                        not in link.source_optical_terminal.orientation_possibilities
                    )
                    assert (
                        InterSatelliteLinkOrientation.INTRA_PLANE_BACKWARD
                        not in link.source_optical_terminal.orientation_possibilities
                    )

    for satellite in simulation_manager.get_sso_shell_satellites():
        isl_links = [
            link for link in satellite.links if isinstance(link, InterSatelliteLink)
        ]
        assert len(isl_links) >= 2

        if len(isl_links) == 2:
            for link in isl_links:
                # Assert that those are orbital links
                assert (
                    link.inter_satellite_direction
                    == InterSatelliteLinkDirection.ORBITAL
                )
                assert (
                    link.get_satellite_source().shell
                    == link.get_satellite_destination().shell
                )
                assert (
                    InterSatelliteLinkOrientation.INTRA_PLANE_FORWARD
                    in link.source_optical_terminal.orientation_possibilities
                    or InterSatelliteLinkOrientation.INTRA_PLANE_BACKWARD
                    in link.source_optical_terminal.orientation_possibilities
                )
                assert (
                    InterSatelliteLinkOrientation.INTRA_PLANE_BACKWARD
                    in link.destination_optical_terminal.orientation_possibilities
                    or InterSatelliteLinkOrientation.INTRA_PLANE_FORWARD
                    in link.destination_optical_terminal.orientation_possibilities
                )


def assert_basic_walker_shell_four_intra_shell_simulation_is_valid(
    simulation_manager: SimulationManager,
):
    shell = simulation_manager.get_walker_shells()[0]
    grid = generate_walker_delta_constellation_grid(
        number_orbits=shell.amount_of_orbit_plane,
        isl_shift=shell.adjacent_inter_satellite_shifting,
        number_satellites_per_orbit=shell.amount_of_satellite_per_orbit_plane,
    )
    for satellite in simulation_manager.get_satellites():
        isl = [isl for isl in satellite.links if isinstance(isl, InterSatelliteLink)]
        assert len(isl) == 4

    isls_copy = simulation_manager.get_inter_satellites_links().copy()

    for satellite_source_object_id, satellite_destination_object_id, direction in grid:
        satellite_source = simulation_manager.get_satellite_by_object_id(
            object_id=satellite_source_object_id, domain=shell.identifier
        )
        satellite_destination = simulation_manager.get_satellite_by_object_id(
            object_id=satellite_destination_object_id, domain=shell.identifier
        )
        assert (
            satellite_source is not None
        ), f"Satellite source with object_id {satellite_source_object_id} not found in shell {shell.identifier}"
        assert (
            satellite_destination is not None
        ), f"Satellite destination with object_id {satellite_destination_object_id} not found in shell {shell.identifier}"

        link = next(
            (
                link
                for link in isls_copy
                if link.source.object_id == satellite_source_object_id
                and link.destination.object_id == satellite_destination_object_id
                and link.inter_satellite_direction == direction
            ),
            None,
        )
        assert (
            link is not None
        ), f"ISL not found between {satellite_source_object_id} and {satellite_destination_object_id} with direction {direction}"

        if link is not None:
            isls_copy.remove(link)


def test_one_basic_walker_shell_for_10_minutes():
    walker_shell_sat_config = make_5_isl_with_single_intershell()
    simulation_property = make_small_single_walker_shell(walker_shell_sat_config)
    simulation_config = BaseConfigurationManager(
        simulation_property=simulation_property
    )
    simulation_manager = simulation_config.load_simulation()

    delta_in_seconds = 30

    test_time = 10 * 60

    simulation_manager.time_manager.verbose = True

    end = simulation_manager.time_manager.get_current_time() + timedelta(
        seconds=test_time
    )
    i = 0
    while simulation_manager.time_manager.get_current_time() < end:
        print(f"Testing t+{i}")
        assert_basic_walker_shell_four_intra_shell_simulation_is_valid(
            simulation_manager=simulation_manager
        )
        i += delta_in_seconds
        simulation_manager.time_manager.tick(seconds=delta_in_seconds)


def test_that_checkerboard_grid_has_3_isl():

    result_matrice: list[tuple[int, int, int]] = []
    m = 10
    n = 120
    simulation_property = make_three_isl_configuration(M=m, N=n)

    simulation_config = BaseConfigurationManager(
        simulation_property=simulation_property
    )
    simulation_manager = simulation_config.load_simulation()

    for satellite in simulation_manager.get_satellites():
        isls = [
            link for link in satellite.links if isinstance(link, InterSatelliteLink)
        ]
        if len(isls) != 3:
            result: tuple[int, int, int] = (m, n, 0)
            result_matrice.append(result)
            break

    print(result_matrice)
