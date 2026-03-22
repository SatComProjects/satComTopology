import datetime
from collections import defaultdict
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, cast

from sat_com_application.event_bus.bus import EventBus
from sat_com_application.event_bus.events import (
    GSLCreatedEvent,
    GSLRemovedEvent,
    GSLUpdatedEvent,
    UTLCreatedEvent,
    UTLRemovedEvent,
    UTLUpdatedEvent,
    ISLCreatedEvent,
    ISLRemovedEvent,
    ISLUpdatedEvent,
    EventType,
    Event,
)


class LinkEventType(IntEnum):
    LINK_CONNECTED = 1
    LINK_DISCONNECTED = 2
    LINK_UPDATED = 3


@dataclass
class LinkEvent:
    """
    A single network event affecting one topology node.

    sim_time        : simulation wall-clock time when the event occurs
    event_type      : connected / disconnected / updated
    peer_id         : topology_uniq_id of the other endpoint of the link
    metadata        : optional link state (elevation, distance, duration, ...)
    """

    sim_time: datetime.datetime
    event_type: LinkEventType
    peer_id: int
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "sim_time": self.sim_time.isoformat(),
            "event_type": int(self.event_type),
            "peer_id": self.peer_id,
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# Timeline type alias
# topology_id → sorted list of LinkEvent
# ---------------------------------------------------------------------------
Timeline = dict[int, list[LinkEvent]]


class EmulatorAdapter:
    """
    Passive listener that records every link lifecycle event per topology node.

    The adapter does NOT run the simulation — it only subscribes to the event bus
    and builds the timeline as events arrive. The simulation is ticked externally.

    Usage:
        event_bus = EventBus()
        simulation_manager = BaseConfigurationManager(
            simulation_property=properties,
            event_bus=event_bus,
        ).load_simulation()

        adapter = EmulatorAdapter(event_bus=event_bus)

        # Tick the simulation externally
        simulation_manager.time_manager.tick_until_the_end(granularity_in_seconds=60)

        timeline = adapter.timeline
    """

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.timeline: Timeline = defaultdict(list)
        self._register_handlers()

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _record(self, node_id: int, event: LinkEvent):
        existing = self.timeline[node_id]
        is_duplicate = any(
            e.sim_time == event.sim_time
            and e.event_type == event.event_type
            and e.peer_id == event.peer_id
            for e in existing
        )
        if not is_duplicate:
            existing.append(event)

    def _record_for_both(
        self,
        id_a: int,
        id_b: int,
        event_type: LinkEventType,
        sim_time: datetime.datetime,
        metadata: dict = None,
    ):
        metadata = metadata or {}
        self._record(
            id_a, LinkEvent(sim_time, event_type, peer_id=id_b, metadata=metadata)
        )
        self._record(
            id_b, LinkEvent(sim_time, event_type, peer_id=id_a, metadata=metadata)
        )

    # -----------------------------------------------------------------------
    # Event handlers
    # -----------------------------------------------------------------------

    async def _on_gsl_created(self, event: Event):
        e = cast(GSLCreatedEvent, event)
        self._record_for_both(
            e.satellite_id,
            e.ground_station_id,
            LinkEventType.LINK_CONNECTED,
            e.sim_time,
            metadata={
                "elevation_angle": e.elevation_angle,
                "estimated_duration": e.estimated_duration,
                "distance_km": e.distance_km,
            },
        )

    async def _on_gsl_updated(self, event: Event):
        e = cast(GSLUpdatedEvent, event)
        self._record_for_both(
            e.satellite_id,
            e.ground_station_id,
            LinkEventType.LINK_UPDATED,
            e.sim_time,
            metadata={
                "elevation_angle": e.elevation_above_horizon_angle,
                "distance_km": e.distance_km,
                "estimated_duration": e.estimated_link_duration,
            },
        )

    async def _on_gsl_removed(self, event: Event):
        e = cast(GSLRemovedEvent, event)
        self._record_for_both(
            e.satellite_id,
            e.ground_station_id,
            LinkEventType.LINK_DISCONNECTED,
            e.sim_time,
        )

    async def _on_utl_created(self, event: Event):
        e = cast(UTLCreatedEvent, event)
        self._record_for_both(
            e.satellite_id,
            e.user_terminal_id,
            LinkEventType.LINK_CONNECTED,
            e.sim_time,
            metadata={
                "elevation_angle": e.elevation_above_horizon_angle,
                "estimated_duration": e.estimated_link_duration,
                "distance_km": e.distance_km,
            },
        )

    async def _on_utl_updated(self, event: Event):
        e = cast(UTLUpdatedEvent, event)
        self._record_for_both(
            e.satellite_id,
            e.user_terminal_id,
            LinkEventType.LINK_UPDATED,
            e.sim_time,
            metadata={
                "elevation_angle": e.elevation_above_horizon_angle,
                "distance_km": e.distance_km,
                "estimated_duration": e.estimated_link_duration,
            },
        )

    async def _on_utl_removed(self, event: Event):
        e = cast(UTLRemovedEvent, event)
        self._record_for_both(
            e.satellite_id,
            e.user_terminal_id,
            LinkEventType.LINK_DISCONNECTED,
            e.sim_time,
        )

    async def _on_isl_created(self, event: Event):
        e = cast(ISLCreatedEvent, event)
        self._record_for_both(
            e.satellite_a_id,
            e.satellite_b_id,
            LinkEventType.LINK_CONNECTED,
            e.sim_time,
        )

    async def _on_isl_updated(self, event: Event):
        e = cast(ISLUpdatedEvent, event)
        self._record_for_both(
            e.satellite_a_id,
            e.satellite_b_id,
            LinkEventType.LINK_UPDATED,
            e.sim_time,
            metadata={"distance_km": e.distance_km},
        )

    async def _on_isl_removed(self, event: Event):
        e = cast(ISLRemovedEvent, event)
        self._record_for_both(
            e.satellite_a_id,
            e.satellite_b_id,
            LinkEventType.LINK_DISCONNECTED,
            e.sim_time,
        )

    def _register_handlers(self):
        self.event_bus.subscribe(EventType.GSL_CREATED, self._on_gsl_created)
        self.event_bus.subscribe(EventType.GSL_UPDATED, self._on_gsl_updated)
        self.event_bus.subscribe(EventType.GSL_REMOVED, self._on_gsl_removed)
        self.event_bus.subscribe(EventType.UTL_CREATED, self._on_utl_created)
        self.event_bus.subscribe(EventType.UTL_UPDATED, self._on_utl_updated)
        self.event_bus.subscribe(EventType.UTL_REMOVED, self._on_utl_removed)
        self.event_bus.subscribe(EventType.ISL_CREATED, self._on_isl_created)
        self.event_bus.subscribe(EventType.ISL_UPDATED, self._on_isl_updated)
        self.event_bus.subscribe(EventType.ISL_REMOVED, self._on_isl_removed)

    def get_sorted_timeline(self) -> Timeline:
        """Return the timeline with each node's events sorted chronologically."""
        return {
            node_id: sorted(events, key=lambda e: e.sim_time)
            for node_id, events in self.timeline.items()
        }

    # -----------------------------------------------------------------------
    # Export
    # -----------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            str(node_id): [e.to_dict() for e in events]
            for node_id, events in self.get_sorted_timeline().items()
        }

    def to_mininet_script(self, start_time: datetime.datetime = None) -> str:
        all_events = [
            (node_id, event)
            for node_id, events in self.get_sorted_timeline().items()
            for event in events
            if node_id < event.peer_id
        ]
        all_events.sort(key=lambda x: x[1].sim_time)

        if not all_events:
            return "# No events recorded."

        t0 = start_time or all_events[0][1].sim_time

        lines = [
            "# Auto-generated Mininet event script",
            "# topology_uniq_id maps to Mininet host/switch names: node_<id>",
            "import time",
            "",
            "def replay(net, start_time):",
        ]

        for node_id, event in all_events:
            offset_s = (event.sim_time - t0).total_seconds()
            node_a = f"node_{node_id}"
            node_b = f"node_{event.peer_id}"

            if event.event_type == LinkEventType.LINK_CONNECTED:
                cmd = f"    net.addLink({node_a}, {node_b})"
            elif event.event_type == LinkEventType.LINK_DISCONNECTED:
                cmd = f"    net.delLink(net.linksBetween({node_a}, {node_b})[0])"
            else:
                cmd = f"    # UPDATE {node_a} ↔ {node_b} metadata={event.metadata}"

            lines.append(
                f"    time.sleep(max(0, start_time + {offset_s:.3f} - time.time()))"
            )
            lines.append(cmd)

        lines.append("")
        return "\n".join(lines)
