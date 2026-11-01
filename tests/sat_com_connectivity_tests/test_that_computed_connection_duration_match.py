import datetime

from sat_com_builder.configuration_manager import BaseConfigurationManager
from sat_com_builder.models import (
    SimulationProperty,
    WalkerShellProperty,
    OrbitalConnectivityProperty,
)
from sat_com_connectivity.ground_object_to_space_connectivity.connection_duration_utils import (
    estimate_time_until_disconnection,
)
from sat_com_constellation.models import WalkerConstellationProperty
from sat_com_model.models import GroundStation, GroundObjectDomain, GroundStationLink


def test_that_the_computed_windows_duration_match():
    print("Test That the computed windows duration match")
    # Load simple constellation
    small_constellation_property = SimulationProperty()

    walker_shell = WalkerShellProperty(
        constellation_property=WalkerConstellationProperty(
            identifier="delta test",
            inclination=53,
            amount_of_orbit_plane=25,
            amount_of_satellite_per_orbit_plane=25,
            mean_revolution_per_day=13.5,
            phase_difference_between_satellites=True,
        ),
        type="delta",
        orbital_connectivity_property=OrbitalConnectivityProperty(),
    )

    small_constellation_property.walker_shells.append(walker_shell)

    simulation_loader = BaseConfigurationManager(
        simulation_property=small_constellation_property
    )
    simulation_manager = simulation_loader.load_simulation()

    ground_station = GroundStation()
    ground_station.label = "Paris"
    ground_station.set_position(latitude=48.8566, longitude=2.3522, altitude=0)
    ground_station.ground_object_domain = GroundObjectDomain(
        identifier="Test Domain",
        type="ground_station",
        elevation_above_horizon=10,
        ground_to_space_connections_strategy="best-angle-until-disconnection",
    )

    simulation_manager.add_ground_station(ground_station)
    simulation_manager.time_manager.tick(seconds=0)

    ground_stations_links = simulation_manager.get_ground_stations_links()
    assert len(ground_stations_links) == 1

    ground_station_link = ground_stations_links[0]
    first_satellite_topology_object_id = (
        ground_station_link.get_satellite().topology_uniq_id
    )

    time_until_disconnection_s = estimate_time_until_disconnection(
        ground_object=ground_station_link.get_ground_station(),
        satellite=ground_station_link.get_satellite(),
    )

    t = simulation_manager.time_manager.current_time
    print(
        f"Current time:        {t.strftime('%Y-%m-%d %H:%M:%S')}.{t.microsecond // 1000:03d}"
    )
    print(f"Connected to:        Satellite {first_satellite_topology_object_id}")
    print(f"Time until handover: {time_until_disconnection_s:.3f}s")

    handover_time = t + datetime.timedelta(seconds=time_until_disconnection_s)
    print(
        f"Handover expected at {handover_time.strftime('%Y-%m-%d %H:%M:%S')}.{handover_time.microsecond // 1000:03d}"
    )

    delta_s = 0.100
    t_before_handover_s = time_until_disconnection_s - delta_s

    simulation_manager.time_manager.tick(seconds=t_before_handover_s)
    t = simulation_manager.time_manager.current_time
    print(
        f"\nCurrent time (500ms before handover): {t.strftime('%Y-%m-%d %H:%M:%S')}.{t.microsecond // 1000:03d}"
    )

    assert len(ground_station.links) == 1
    link = ground_station.links[0]
    assert isinstance(link, GroundStationLink)
    assert link.get_satellite() == ground_station_link.get_satellite(), (
        f"Expected connection to {first_satellite_topology_object_id}, "
        f"got {link.get_satellite().topology_uniq_id}"
    )
    print(f"Still connected to:  Satellite {link.get_satellite().topology_uniq_id} ✓")

    # --- Tick 1000ms forward (500ms past handover): satellite should be disconnected ---
    simulation_manager.time_manager.tick(seconds=2 * delta_s)
    t = simulation_manager.time_manager.current_time
    print(
        f"\nCurrent time (500ms after handover):  {t.strftime('%Y-%m-%d %H:%M:%S')}.{t.microsecond // 1000:03d}"
    )

    assert len(ground_station.links) == 1 or len(ground_station.links) == 0
    if len(ground_station.links) == 1:
        link = ground_station.links[0]
        if isinstance(link, GroundStationLink):
            assert (
                link.get_satellite() != ground_station_link.get_satellite()
            ), f"Still connected to {first_satellite_topology_object_id} — handover did not occur"
            print(
                f"Handed over to:      Satellite {link.get_satellite().topology_uniq_id} ✓"
            )
    else:
        print("No active link after handover ✓")


def test_that_ten_consecutive_handovers_match_predicted_disconnection_times():
    print(
        "Test That ten consecutive handover times match predicted disconnection times"
    )

    small_constellation_property = SimulationProperty()

    walker_shell = WalkerShellProperty(
        constellation_property=WalkerConstellationProperty(
            identifier="delta test",
            inclination=53,
            amount_of_orbit_plane=25,
            amount_of_satellite_per_orbit_plane=25,
            mean_revolution_per_day=13.5,
            phase_difference_between_satellites=True,
        ),
        type="delta",
        orbital_connectivity_property=OrbitalConnectivityProperty(),
    )

    small_constellation_property.walker_shells.append(walker_shell)

    simulation_loader = BaseConfigurationManager(
        simulation_property=small_constellation_property
    )
    simulation_manager = simulation_loader.load_simulation()

    ground_station = GroundStation()
    ground_station.label = "Paris"
    ground_station.set_position(latitude=48.8566, longitude=2.3522, altitude=0)
    ground_station.ground_object_domain = GroundObjectDomain(
        identifier="Test Domain",
        type="ground_station",
        elevation_above_horizon=10,
        ground_to_space_connections_strategy="best-angle-until-disconnection",
    )

    simulation_manager.add_ground_station(ground_station)
    simulation_manager.time_manager.tick(seconds=0)

    delta_s = 1.5  # safety margin in seconds around predicted handover

    for handover_index in range(10):
        print(f"\n--- Handover {handover_index + 1} / 10 ---")

        ground_stations_links = simulation_manager.get_ground_stations_links()
        assert len(ground_stations_links) == 1, (
            f"Handover {handover_index + 1}: expected 1 active link, "
            f"got {len(ground_stations_links)}"
        )

        ground_station_link = ground_stations_links[0]
        current_satellite = ground_station_link.get_satellite()
        current_satellite_id = current_satellite.topology_uniq_id

        t = simulation_manager.time_manager.current_time
        print(
            f"Current time:   {t.strftime('%Y-%m-%d %H:%M:%S')}.{t.microsecond // 1000:03d}"
        )
        print(f"Connected to:   Satellite {current_satellite_id}")

        time_until_disconnection_s = estimate_time_until_disconnection(
            ground_object=ground_station_link.get_ground_station(),
            satellite=current_satellite,
        )
        print(f"Predicted disconnection in: {time_until_disconnection_s:.3f}s")

        handover_time = t + datetime.timedelta(seconds=time_until_disconnection_s)
        print(
            f"Handover expected at: "
            f"{handover_time.strftime('%Y-%m-%d %H:%M:%S')}.{handover_time.microsecond // 1000:03d}"
        )

        # --- Tick to delta_s BEFORE predicted handover: must still be connected ---
        simulation_manager.time_manager.tick(
            seconds=time_until_disconnection_s - delta_s
        )
        t = simulation_manager.time_manager.current_time
        print(
            f"Time ({delta_s}s before handover): {t.strftime('%Y-%m-%d %H:%M:%S')}.{t.microsecond // 1000:03d}"
        )

        assert (
            len(ground_station.links) == 1
        ), f"Handover {handover_index + 1}: expected link to still exist {delta_s}s before handover"
        link = ground_station.links[0]
        assert isinstance(link, GroundStationLink)
        assert link.get_satellite() == current_satellite, (
            f"Handover {handover_index + 1}: expected connection to {current_satellite_id}, "
            f"got {link.get_satellite().topology_uniq_id}"
        )
        print(f"Still connected to: Satellite {current_satellite_id} ✓")

        # --- Tick 2*delta_s forward (delta_s PAST predicted handover): must have handed over ---
        simulation_manager.time_manager.tick(seconds=2 * delta_s)
        t = simulation_manager.time_manager.current_time
        print(
            f"Time ({delta_s}s after handover):  {t.strftime('%Y-%m-%d %H:%M:%S')}.{t.microsecond // 1000:03d}"
        )

        assert (
            len(ground_station.links) == 1 or len(ground_station.links) == 0
        ), f"Handover {handover_index + 1}: unexpected number of links: {len(ground_station.links)}"

        if len(ground_station.links) == 1:
            link = ground_station.links[0]
            if isinstance(link, GroundStationLink):
                assert link.get_satellite() != current_satellite, (
                    f"Handover {handover_index + 1}: still connected to {current_satellite_id} "
                    f"— handover did not occur"
                )
                print(
                    f"Handed over to: Satellite {link.get_satellite().topology_uniq_id} ✓"
                )
        else:
            print("No active link after handover ✓")

    print("\n10 consecutive handovers validated successfully ✓")
