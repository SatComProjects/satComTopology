import asyncio
import datetime
from pathlib import Path

import pytest

from sat_com_adapter.emulator_adapter.emulator_adapter import (
    EmulatorAdapter,
    LinkEventType,
)
from sat_com_application.event_bus.bus import EventBus
from sat_com_application.simulation_manager import SimulationManager
from sat_com_builder.configuration_manager import BaseConfigurationManager
from sat_com_builder.models import SimulationProperty

# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


def _build_simulation_properties(data_file_path: Path) -> SimulationProperty:
    return SimulationProperty(
        **{
            "simulation_name": "Single Shell Simulation",
            "start_date": "2024-11-18 00:00:00.000000",
            "end_date": "2024-11-18 00:05:00.000000",
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
        }
    )


@pytest.fixture(scope="module")
def adapter() -> EmulatorAdapter:
    base_dir = Path(__file__).parent
    data_file_path = Path(base_dir) / "10_ground_stations.txt"

    event_bus = EventBus()

    adapter = EmulatorAdapter(event_bus=event_bus)

    simulation_manager: SimulationManager = BaseConfigurationManager(
        simulation_property=_build_simulation_properties(data_file_path),
        event_bus=event_bus,
    ).load_simulation()

    async def run():
        while (
            simulation_manager.time_manager.current_time
            < simulation_manager.time_manager.end_date
        ):
            simulation_manager.time_manager.tick(60.0)
            await asyncio.sleep(0)

    asyncio.run(run())
    return adapter


# ---------------------------------------------------------------------------
# Timeline structure
# ---------------------------------------------------------------------------


class TestTimelineStructure:

    def test_timeline_is_not_empty(self, adapter):
        assert len(adapter.timeline) > 0

    def test_every_node_has_at_least_one_event(self, adapter):
        for node_id, events in adapter.timeline.items():
            assert len(events) > 0, f"Node {node_id} has no events"

    def test_every_event_has_a_sim_time(self, adapter):
        for node_id, events in adapter.timeline.items():
            for event in events:
                assert (
                    event.sim_time is not None
                ), f"Node {node_id} has an event with no sim_time"

    def test_every_event_has_a_peer_id(self, adapter):
        for node_id, events in adapter.timeline.items():
            for event in events:
                assert event.peer_id is not None
                assert isinstance(event.peer_id, int)

    def test_events_are_sorted_chronologically(self, adapter):
        sorted_timeline = adapter.get_sorted_timeline()
        for node_id, events in sorted_timeline.items():
            times = [e.sim_time for e in events]
            assert times == sorted(
                times
            ), f"Events for node {node_id} are not sorted chronologically"

    def test_sim_time_within_simulation_bounds(self, adapter):
        start = datetime.datetime(2024, 11, 18, 0, 0, 0)
        end = datetime.datetime(2024, 11, 18, 0, 5, 0)
        for node_id, events in adapter.timeline.items():
            for event in events:
                assert (
                    start <= event.sim_time <= end
                ), f"Node {node_id} has event outside simulation bounds: {event.sim_time}"

    def test_peer_id_is_never_self(self, adapter):
        for node_id, events in adapter.timeline.items():
            for event in events:
                assert (
                    event.peer_id != node_id
                ), f"Node {node_id} has an event pointing to itself"


# ---------------------------------------------------------------------------
# Event types
# ---------------------------------------------------------------------------


class TestEventTypes:

    def test_connected_events_exist(self, adapter):
        all_types = {
            event.event_type for events in adapter.timeline.values() for event in events
        }
        assert LinkEventType.LINK_CONNECTED in all_types

    def test_disconnected_events_exist(self, adapter):
        all_types = {
            event.event_type for events in adapter.timeline.values() for event in events
        }
        assert LinkEventType.LINK_DISCONNECTED in all_types

    def test_every_disconnection_has_a_prior_connection(self, adapter):
        """
        Every LINK_DISCONNECTED must have a prior LINK_CONNECTED.
        Guaranteed because the adapter subscribes before load_simulation
        fires any GSLCreatedEvent.
        """
        for node_id, events in adapter.timeline.items():
            connections = {
                e.peer_id
                for e in events
                if e.event_type == LinkEventType.LINK_CONNECTED
            }
            disconnections = {
                e.peer_id
                for e in events
                if e.event_type == LinkEventType.LINK_DISCONNECTED
            }
            for peer in disconnections:
                assert (
                    peer in connections
                ), f"Node {node_id} disconnected from {peer} but no prior connection recorded"

    def test_disconnection_always_after_connection(self, adapter):
        """
        For any (node, peer) pair, every LINK_DISCONNECTED must come after
        its corresponding LINK_CONNECTED. Pairs with no CONNECTED event are
        skipped — they are pre-existing links from before the bus was attached.
        """
        for node_id, events in adapter.timeline.items():
            by_peer: dict[int, list] = {}
            for event in events:
                by_peer.setdefault(event.peer_id, []).append(event)

            for peer_id, peer_events in by_peer.items():
                connected_times = [
                    e.sim_time
                    for e in peer_events
                    if e.event_type == LinkEventType.LINK_CONNECTED
                ]
                disconnected_times = [
                    e.sim_time
                    for e in peer_events
                    if e.event_type == LinkEventType.LINK_DISCONNECTED
                ]

                if not connected_times:
                    # Pre-existing link — no CONNECTED event recorded, skip
                    continue

                for d_time in disconnected_times:
                    assert any(c_time <= d_time for c_time in connected_times), (
                        f"Node {node_id} → peer {peer_id}: "
                        f"disconnection at {d_time} has no prior connection"
                    )


# ---------------------------------------------------------------------------
# Symmetry — both endpoints must record the same event
# ---------------------------------------------------------------------------


class TestTimelineSymmetry:

    def test_connection_events_are_symmetric(self, adapter):
        """
        If node A records LINK_CONNECTED to B at time T,
        node B must also record LINK_CONNECTED to A at time T.
        """
        for node_id, events in adapter.timeline.items():
            for event in events:
                if event.event_type != LinkEventType.LINK_CONNECTED:
                    continue
                peer_events = adapter.timeline.get(event.peer_id, [])
                mirror = [
                    e
                    for e in peer_events
                    if e.event_type == LinkEventType.LINK_CONNECTED
                    and e.peer_id == node_id
                    and e.sim_time == event.sim_time
                ]
                assert len(mirror) == 1, (
                    f"Node {node_id} has LINK_CONNECTED to {event.peer_id} at "
                    f"{event.sim_time} but no symmetric event on the peer side"
                )

    def test_disconnection_events_are_symmetric(self, adapter):
        for node_id, events in adapter.timeline.items():
            for event in events:
                if event.event_type != LinkEventType.LINK_DISCONNECTED:
                    continue
                peer_events = adapter.timeline.get(event.peer_id, [])
                mirror = [
                    e
                    for e in peer_events
                    if e.event_type == LinkEventType.LINK_DISCONNECTED
                    and e.peer_id == node_id
                    and e.sim_time == event.sim_time
                ]
                assert len(mirror) == 1, (
                    f"Node {node_id} has LINK_DISCONNECTED to {event.peer_id} at "
                    f"{event.sim_time} but no symmetric event on the peer side"
                )


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------


class TestSerialisation:

    def test_to_dict_keys_are_strings(self, adapter):
        d = adapter.to_dict()
        for key in d.keys():
            assert isinstance(key, str)

    def test_to_dict_values_are_lists(self, adapter):
        d = adapter.to_dict()
        for value in d.values():
            assert isinstance(value, list)

    def test_to_dict_events_have_required_fields(self, adapter):
        d = adapter.to_dict()
        for node_id, events in d.items():
            for event in events:
                assert "sim_time" in event, f"Missing sim_time for node {node_id}"
                assert "event_type" in event, f"Missing event_type for node {node_id}"
                assert "peer_id" in event, f"Missing peer_id for node {node_id}"
                assert "metadata" in event, f"Missing metadata for node {node_id}"

    def test_to_dict_is_json_serialisable(self, adapter):
        import json

        d = adapter.to_dict()
        try:
            json.dumps(d)
        except (TypeError, ValueError) as e:
            pytest.fail(f"Timeline is not JSON serialisable: {e}")


# ---------------------------------------------------------------------------
# Mininet script
# ---------------------------------------------------------------------------


class TestMininetScript:

    def test_mininet_script_is_a_string(self, adapter):
        assert isinstance(adapter.to_mininet_script(), str)

    def test_mininet_script_contains_replay_function(self, adapter):
        assert "def replay(net, start_time):" in adapter.to_mininet_script()

    def test_mininet_script_contains_addLink(self, adapter):
        assert "net.addLink" in adapter.to_mininet_script()

    def test_mininet_script_contains_delLink(self, adapter):
        assert "net.delLink" in adapter.to_mininet_script()

    def test_mininet_script_node_names_follow_convention(self, adapter):
        import re

        node_refs = re.findall(r"node_(\d+)", adapter.to_mininet_script())
        assert len(node_refs) > 0
        for ref in node_refs:
            assert ref.isdigit()

    def test_mininet_script_offsets_are_non_negative(self, adapter):
        import re

        offsets = re.findall(r"start_time \+ ([\d.]+)", adapter.to_mininet_script())
        for offset in offsets:
            assert float(offset) >= 0.0
