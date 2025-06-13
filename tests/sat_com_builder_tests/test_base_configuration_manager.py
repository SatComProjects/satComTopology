from unittest.mock import patch

from sat_com_builder.configuration_manager import BaseConfigurationManager
from sat_com_builder.models import SimulationProperty
from sat_com_connectivity.ground_object_to_space_connectivity.ground_connection_strategy_registry import (
    GROUND_TO_SPACE_CONNECTION_STRATEGY_REGISTRY,
)
from sat_com_model.models import (
    GroundStation,
    UserTerminal,
    SpatialPosition,
    GroundObjectDomain,
)
from tests.sat_com_builder_tests.models import FakeGroundToSpaceConnectionStrategy
from tests.sat_com_builder_tests.multishell_config import multi_shell_config


class TestBaseConfigurationManager:
    @patch("sat_com_builder.configuration_manager.generate_user_terminal_from_file")
    @patch("sat_com_builder.configuration_manager.generate_ground_stations_from_file")
    def test_base_configuration_manager_create_multi_shell_constellation(
        self,
        generate_ground_stations_from_file,
        generate_user_terminal_from_file,
    ):
        GROUND_TO_SPACE_CONNECTION_STRATEGY_REGISTRY.update(
            {"fake_strategy": FakeGroundToSpaceConnectionStrategy}
        )

        generate_ground_stations_from_file.return_value = [
            GroundStation(
                label="Paris",
                object_id=0,
                spatial_position_info=SpatialPosition(
                    longitude=1, latitude=1, altitude=10
                ),
                ground_object_domain=GroundObjectDomain(
                    identifier="test_gs",
                    type="ground_station",
                    ground_to_space_connections_strategy="fake_strategy",
                ),
            ),
            GroundStation(
                label="Marseille",
                object_id=1,
                spatial_position_info=SpatialPosition(
                    longitude=1, latitude=1, altitude=10
                ),
                ground_object_domain=GroundObjectDomain(
                    identifier="test_gs",
                    type="ground_station",
                    ground_to_space_connections_strategy="fake_strategy",
                ),
            ),
            GroundStation(
                label="Lyon",
                object_id=2,
                spatial_position_info=SpatialPosition(
                    longitude=1, latitude=1, altitude=10
                ),
                ground_object_domain=GroundObjectDomain(
                    identifier="test_gs",
                    type="ground_station",
                    ground_to_space_connections_strategy="fake_strategy",
                ),
            ),
            GroundStation(
                label="Turin",
                object_id=3,
                spatial_position_info=SpatialPosition(
                    longitude=1, latitude=1, altitude=10
                ),
                ground_object_domain=GroundObjectDomain(
                    identifier="test_gs",
                    type="ground_station",
                    ground_to_space_connections_strategy="fake_strategy",
                ),
            ),
        ]
        generate_user_terminal_from_file.return_value = [
            UserTerminal(
                label="Louis",
                object_id=0,
                spatial_position_info=SpatialPosition(
                    longitude=1, latitude=1, altitude=10
                ),
                ground_object_domain=GroundObjectDomain(
                    identifier="test_ut",
                    type="user_terminal",
                    ground_to_space_connections_strategy="fake_strategy",
                ),
            ),
            UserTerminal(
                label="Leon",
                object_id=1,
                spatial_position_info=SpatialPosition(
                    longitude=1, latitude=1, altitude=10
                ),
                ground_object_domain=GroundObjectDomain(
                    identifier="test_ut",
                    type="user_terminal",
                    ground_to_space_connections_strategy="fake_strategy",
                ),
            ),
            UserTerminal(
                label="Marie",
                object_id=2,
                spatial_position_info=SpatialPosition(
                    longitude=1, latitude=1, altitude=10
                ),
                ground_object_domain=GroundObjectDomain(
                    identifier="test_ut",
                    type="user_terminal",
                    ground_to_space_connections_strategy="fake_strategy",
                ),
            ),
            UserTerminal(
                label="Anne",
                object_id=2,
                spatial_position_info=SpatialPosition(
                    longitude=1, latitude=1, altitude=10
                ),
                ground_object_domain=GroundObjectDomain(
                    identifier="test_ut",
                    type="user_terminal",
                    ground_to_space_connections_strategy="fake_strategy",
                ),
            ),
        ]

        configuration = multi_shell_config
        simulation_property = SimulationProperty(**configuration)
        base_configuration_manager = BaseConfigurationManager(simulation_property)

        simulation_manager = base_configuration_manager.load_simulation()

        amounts_of_satellites = [
            (
                shell.constellation_property.amount_of_satellite_per_orbit_plane
                * shell.constellation_property.amount_of_orbit_plane
            )
            for shell in simulation_property.walker_shells
        ]

        total_amount_of_satellite = sum(amounts_of_satellites)

        assert len(simulation_manager.get_satellites()) == total_amount_of_satellite

        assert len(simulation_manager.simulation.walker_shells) == 2

        assert len(simulation_manager.simulation.ground_object_domains) == 3

        assert all(
            (
                ground_object.get("identifier")
                in [
                    domain.identifier
                    for domain in simulation_manager.simulation.ground_object_domains
                ]
                for ground_object in multi_shell_config.get("ground_objects_properties")
            )
        )

        print(len(simulation_manager.simulation.walker_shells))
        print(multi_shell_config.get("walker_shells"))

        assert all(
            (
                walker_shell.get("constellation_property").get("identifier")
                in [
                    walker_shell.identifier
                    for walker_shell in simulation_manager.simulation.walker_shells
                ]
                for walker_shell in multi_shell_config.get("walker_shells")
            )
        )

        assert len(simulation_manager.get_ground_stations()) == 4

        assert len(simulation_manager.get_user_terminals()) == 4
