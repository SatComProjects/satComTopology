from pathlib import Path

from sat_com_builder.models import (
    SimulationProperty,
    WalkerShellProperty,
    OrbitalConnectivityProperty,
    WalkerShellType,
    GroundObjectProperty,
    GroundConnectivityProperty,
)
from sat_com_connectivity.inter_satellite_link_connectivity.addressing_plans import (
    AvailableAddressingPlans,
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


def test_time_taken_for_init_performance():
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


def test_time_taken_for_isl_update_performance():
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

    for i in range(100):
        start_time = time.time()
        simulation_manager.time_manager.tick(seconds=10)
        end_time = time.time()

        elapsed_time = end_time - start_time
        print(f"Time taken for update performance: {elapsed_time:.4f} ms")
        average_ticking_time += elapsed_time

    average_ticking_time = average_ticking_time / 100
    print(f"Average time taken for update performance: {average_ticking_time:.4f} ms")


def test_time_taken_for_gsl_update_performance():
    import time
    import cProfile
    import pstats
    from io import StringIO
    from pathlib import Path

    from sat_com_application.event_bus.bus import EventBus
    from sat_com_application.event_bus.factories import EventFactories
    from sat_com_builder.configuration_manager import BaseConfigurationManager

    event_bus = EventBus()
    event_factories = EventFactories()

    test_constellation = generate_test_constellation()
    test_constellation.walker_shells[0].static_addressing_plan = (
        AvailableAddressingPlans.EMPTY
    )
    base_dir = Path(__file__).parent
    data_file_path = Path(base_dir) / "100_ground_stations.txt"

    test_constellation.ground_objects_properties.append(
        GroundObjectProperty(
            identifier="SuperGroundStations",
            data_file=data_file_path.as_posix(),
            type="ground_station",
            connectivity_properties=GroundConnectivityProperty(
                elevation_above_horizon=20,
                ground_to_space_connections_strategy="everything-visible",
            ),
        )
    )

    configuration_manager = BaseConfigurationManager(
        simulation_property=test_constellation,
        event_bus=event_bus,
        event_factories=event_factories,
    )

    profiler = cProfile.Profile()
    profiler.enable()

    t0 = time.perf_counter()
    simulation_manager = configuration_manager.load_simulation()
    elapsed = time.perf_counter() - t0

    profiler.disable()

    print(f"\nload_simulation took {elapsed * 1000:.2f} ms")

    s = StringIO()
    ps = pstats.Stats(profiler, stream=s).sort_stats("cumulative")
    ps.print_stats(40)
    print(s.getvalue())
