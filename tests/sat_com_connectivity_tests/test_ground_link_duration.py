"""
Estimated duration of the ground-to-space links.

The SimulationManager estimates, in one vectorised batch, the time each new link
of an elevation-based strategy will last, stores the predicted disconnection
time on the link and refreshes the remaining duration at every update.
"""

import datetime
from pathlib import Path

import numpy as np
import pytest

from sat_com_application.event_bus.factories import DefaultGSLEventFactory
from sat_com_builder.configuration_manager import BaseConfigurationManager
from sat_com_builder.models import GroundConnectivityProperty, GroundObjectProperty
from sat_com_connectivity.ground_object_to_space_connectivity.connection_duration_utils import (
    DURATION_HORIZON_SECONDS,
    estimate_disconnection_delays,
    estimate_time_until_disconnection,
)
from tests.sat_com_topology_tests.test_multiple_satellite_configuration import (
    make_basic_4_isl_satellite_installation_intershell_unauthorized,
    make_small_single_walker_shell,
)

GROUND_STATIONS_FILE = (
    Path(__file__).resolve().parents[1] / "performance_scripts/100_ground_stations.txt"
)
TICK_SECONDS = 10


def _simulation(ground_strategy: str, ground_type: str = "ground_station"):
    simulation_property = make_small_single_walker_shell(
        make_basic_4_isl_satellite_installation_intershell_unauthorized()
    )
    simulation_property.start_date = "2026-01-01 00:00:00"
    simulation_property.end_date = "2026-01-02 00:00:00"
    simulation_property.ground_objects_properties.append(
        GroundObjectProperty(
            identifier="Ground",
            data_file=GROUND_STATIONS_FILE.as_posix(),
            type=ground_type,
            connectivity_properties=GroundConnectivityProperty(
                elevation_above_horizon=20,
                ground_to_space_connections_strategy=ground_strategy,
            ),
        )
    )
    return BaseConfigurationManager(simulation_property).load_simulation()


def _ground_links(manager):
    return manager.get_ground_stations_links() + manager.get_user_terminal_links()


def _satellite_and_ground(link):
    return link.get_space_object(), link.get_ground_object()


# ---------------------------------------------------------------------------
# Estimator
# ---------------------------------------------------------------------------


def test_vectorised_estimate_matches_the_exact_estimator():
    manager = _simulation("everything-visible")
    links = manager.get_ground_stations_links()
    pairs = [_satellite_and_ground(link) for link in links[:: max(1, len(links) // 25)]]

    vectorised = estimate_disconnection_delays(
        [s for s, _ in pairs],
        [g for _, g in pairs],
        manager.time_manager.current_time,
        manager.satellite_state_cache,
    )
    exact = [
        estimate_time_until_disconnection(
            g, s, tol=0.01, max_time=DURATION_HORIZON_SECONDS
        )
        for s, g in pairs
    ]

    assert np.max(np.abs(vectorised - np.array(exact))) < 0.5


def test_estimate_of_an_empty_batch():
    assert (
        len(estimate_disconnection_delays([], [], datetime.datetime(2026, 1, 1))) == 0
    )


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "ground_strategy, ground_type",
    [
        ("everything-visible", "ground_station"),
        ("best-angle-until-disconnection", "user_terminal"),
    ],
)
def test_links_disappear_at_the_first_tick_after_their_predicted_disconnection(
    ground_strategy, ground_type
):
    manager = _simulation(ground_strategy, ground_type)
    predicted = {}
    checked = 0

    for _ in range(60):
        before = {link.link_id: link for link in _ground_links(manager)}
        for link in before.values():
            predicted.setdefault(link.link_id, link.estimated_disconnection_time)

        manager.time_manager.tick(seconds=TICK_SECONDS)
        now = manager.time_manager.current_time
        after = {link.link_id for link in _ground_links(manager)}

        for link_id in set(before) - after:
            end = predicted[link_id]
            if end is None:  # created at bootstrap, before a time step
                continue
            # Removed at the first tick after the predicted end (0.5 s margin).
            assert end <= now + datetime.timedelta(seconds=0.5)
            assert end > now - datetime.timedelta(seconds=TICK_SECONDS + 0.5)
            checked += 1

    assert checked > 10


@pytest.mark.parametrize(
    "ground_strategy, ground_type",
    [
        ("everything-visible", "ground_station"),
        ("best-angle-until-disconnection", "user_terminal"),
    ],
)
def test_remaining_duration_is_refreshed_every_tick(ground_strategy, ground_type):
    manager = _simulation(ground_strategy, ground_type)
    for _ in range(3):
        manager.time_manager.tick(seconds=TICK_SECONDS)

    now = manager.time_manager.current_time
    links = _ground_links(manager)
    assert links
    for link in links:
        assert link.estimated_disconnection_time is not None
        expected = max(0.0, (link.estimated_disconnection_time - now).total_seconds())
        assert link.estimated_link_duration == pytest.approx(expected)


def test_distance_based_strategies_get_no_duration():
    manager = _simulation("best-range-until-disconnection")
    manager.time_manager.tick(seconds=TICK_SECONDS)

    for link in manager.get_ground_stations_links():
        assert link.estimated_disconnection_time is None
        assert link.estimated_link_duration == -1


def test_events_carry_the_disconnection_time_and_the_distance():
    manager = _simulation("everything-visible")
    manager.time_manager.tick(seconds=TICK_SECONDS)
    link = manager.get_ground_stations_links()[0]

    factory = DefaultGSLEventFactory()
    created, updated = factory.created(link), factory.updated(link)

    assert created.estimated_disconnection_time == link.estimated_disconnection_time
    assert updated.estimated_disconnection_time == link.estimated_disconnection_time
    assert created.distance_km == link.distance_km
