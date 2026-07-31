from sat_com_builder.models import (
    SimulationProperty,
    WalkerShellProperty,
    OrbitalConnectivityProperty,
    WalkerShellType,
)
from sat_com_constellation.models import WalkerConstellationProperty


def generate_test_constellation() -> SimulationProperty:
    experience_start: str = "2026-01-01 00:00:00"
    experience_end: str = "2026-01-01 12:00:00"

    return SimulationProperty(
        start_date=experience_start,
        end_date=experience_end,
        walker_shells=[
            WalkerShellProperty(
                type=WalkerShellType.DELTA,
                constellation_property=WalkerConstellationProperty(
                    inclination=70,
                    identifier="Starlink G2",
                    mean_revolution_per_day=10,
                    phase_difference_between_satellites=True,
                    amount_of_orbit_plane=36,
                    amount_of_satellite_per_orbit_plane=20,
                ),
                orbital_connectivity_property=OrbitalConnectivityProperty(),
            )
        ],
    )


def test_time_taken_for_update_performance():
    import time
    from sat_com_application.event_bus.bus import EventBus
    from sat_com_application.event_bus.factories import EventFactories
    from sat_com_builder.configuration_manager import BaseConfigurationManager

    event_bus = EventBus()
    event_factories = EventFactories()
    configuration_manager = BaseConfigurationManager(
        simulation_property=generate_test_constellation(),
        event_bus=event_bus,
        event_factories=event_factories,
    )
    simulation_manager = configuration_manager.load_simulation()
    simulation_manager.time_manager.verbose = True

    average_ticking_time = 0

    for i in range(1):
        start_time = time.time()
        simulation_manager.time_manager.tick(seconds=10)
        end_time = time.time()

        elapsed_time = end_time - start_time
        print(f"Time taken for update performance: {elapsed_time:.4f} ms")
        average_ticking_time += elapsed_time

    average_ticking_time = average_ticking_time / 100
    print(f"Average time taken for update performance: {average_ticking_time:.4f} ms")
