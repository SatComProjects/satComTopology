"""
GSL_UPDATED / UTL_UPDATED events for the ground links an until-disconnection
strategy keeps.

Such a strategy refreshes the elevation and the distance of a kept link in place,
without returning it as an updated link. The SimulationManager must still publish
its update, otherwise an event subscriber (an emulator, a graph built from the
events) keeps the distance of the link creation.
"""

from pathlib import Path

import pytest

from sat_com_application.event_bus.bus import EventBus
from sat_com_application.event_bus.events import EventType
from sat_com_builder.configuration_manager import BaseConfigurationManager
from sat_com_builder.models import GroundConnectivityProperty, GroundObjectProperty
from tests.sat_com_topology_tests.test_multiple_satellite_configuration import (
    make_basic_4_isl_satellite_installation_intershell_unauthorized,
    make_small_single_walker_shell,
)

GROUND_STATIONS_FILE = (
    Path(__file__).resolve().parents[1] / "performance_scripts/100_ground_stations.txt"
)
TICK_SECONDS = 10

EVENT_TYPES = {
    "ground_station": (
        EventType.GSL_CREATED,
        EventType.GSL_UPDATED,
        EventType.GSL_REMOVED,
    ),
    "user_terminal": (
        EventType.UTL_CREATED,
        EventType.UTL_UPDATED,
        EventType.UTL_REMOVED,
    ),
}


def _simulation_with_events(ground_strategy: str, ground_type: str):
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

    events = []

    async def record(event):
        events.append(event)

    event_bus = EventBus()
    for event_type in EVENT_TYPES[ground_type]:
        event_bus.subscribe(event_type, record)

    manager = BaseConfigurationManager(
        simulation_property, event_bus=event_bus
    ).load_simulation()
    return manager, events


def _ground_links(manager, ground_type):
    if ground_type == "ground_station":
        return manager.get_ground_stations_links()
    return manager.get_user_terminal_links()


@pytest.mark.parametrize("ground_type", ["ground_station", "user_terminal"])
@pytest.mark.parametrize(
    "ground_strategy",
    ["best-angle-until-disconnection", "best-angle-until-disconnection-ordered"],
)
def test_a_kept_link_publishes_its_update_with_the_refreshed_distance(
    ground_strategy, ground_type
):
    created_type, updated_type, _ = EVENT_TYPES[ground_type]
    manager, events = _simulation_with_events(ground_strategy, ground_type)
    links_before = {
        link.link_id.hex: link.distance_km
        for link in _ground_links(manager, ground_type)
    }
    assert links_before, "the test needs ground links"

    events.clear()
    manager.time_manager.tick(TICK_SECONDS)

    kept_links = {
        link.link_id.hex: link
        for link in _ground_links(manager, ground_type)
        if link.link_id.hex in links_before
    }
    assert kept_links, "the test needs links kept over the tick"

    updated_events = {
        event.link_id: event for event in events if event.type == updated_type
    }
    for link_id, link in kept_links.items():
        assert link_id in updated_events, "a kept link must publish its update"
        event = updated_events[link_id]
        assert event.distance_km == pytest.approx(link.distance_km)
        assert event.sim_time == manager.time_manager.current_time

    moved = [
        link_id
        for link_id, link in kept_links.items()
        if link.distance_km != links_before[link_id]
    ]
    assert moved, "the satellites moved: the distance of the kept links changed"

    # One event per link and per tick: a created link only publishes its creation.
    created_ids = {event.link_id for event in events if event.type == created_type}
    assert not created_ids & set(updated_events)
    assert len(updated_events) == len([e for e in events if e.type == updated_type])


@pytest.mark.parametrize("ground_type", ["ground_station", "user_terminal"])
def test_kept_links_are_not_updated_twice_with_an_explicit_update_strategy(ground_type):
    """everything-visible returns its kept links as updated links: one event each."""
    _, updated_type, _ = EVENT_TYPES[ground_type]
    manager, events = _simulation_with_events("everything-visible", ground_type)

    events.clear()
    manager.time_manager.tick(TICK_SECONDS)

    updated_ids = [event.link_id for event in events if event.type == updated_type]
    assert updated_ids
    assert len(updated_ids) == len(set(updated_ids))


def test_no_event_bus_no_error():
    simulation_property = make_small_single_walker_shell(
        make_basic_4_isl_satellite_installation_intershell_unauthorized()
    )
    simulation_property.ground_objects_properties.append(
        GroundObjectProperty(
            identifier="Ground",
            data_file=GROUND_STATIONS_FILE.as_posix(),
            type="ground_station",
            connectivity_properties=GroundConnectivityProperty(
                ground_to_space_connections_strategy="best-angle-until-disconnection",
            ),
        )
    )
    manager = BaseConfigurationManager(simulation_property).load_simulation()
    manager.time_manager.tick(TICK_SECONDS)
    assert manager.get_ground_stations_links()
