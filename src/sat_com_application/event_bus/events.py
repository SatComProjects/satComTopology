from datetime import datetime
from enum import Enum, auto
from pydantic import BaseModel


class EventType(Enum):
    ISL_CREATED = auto()
    ISL_UPDATED = auto()
    ISL_REMOVED = auto()

    GSL_CREATED = auto()
    GSL_UPDATED = auto()
    GSL_REMOVED = auto()

    UTL_CREATED = auto()
    UTL_UPDATED = auto()
    UTL_REMOVED = auto()

    GOL_CREATED = auto()
    GOL_UPDATED = auto()
    GOL_REMOVED = auto()


class Event(BaseModel):
    sim_time: datetime | None = None
    type: EventType

    model_config = {"arbitrary_types_allowed": True}


# -------------------------
# Inter-Satellite Link
# -------------------------
class ISLCreatedEvent(Event):
    type: EventType = EventType.ISL_CREATED
    satellite_a_id: int
    satellite_b_id: int
    distance_km: float | None = None


class ISLUpdatedEvent(Event):
    type: EventType = EventType.ISL_UPDATED
    satellite_a_id: int
    satellite_b_id: int
    distance_km: float | None = None


class ISLRemovedEvent(Event):
    type: EventType = EventType.ISL_REMOVED
    satellite_a_id: int
    satellite_b_id: int


# -------------------------
# Ground Station Link
# -------------------------
class GSLCreatedEvent(Event):
    type: EventType = EventType.GSL_CREATED
    satellite_id: int
    ground_station_id: int
    distance_km: float | None = None
    elevation_angle: float | None = None
    estimated_duration: float | None = None


class GSLUpdatedEvent(Event):
    type: EventType = EventType.GSL_UPDATED
    satellite_id: int
    ground_station_id: int
    distance_km: float | None = None
    elevation_above_horizon_angle: float | None = None
    estimated_link_duration: float | None = None


class GSLRemovedEvent(Event):
    type: EventType = EventType.GSL_REMOVED
    satellite_id: int
    ground_station_id: int


# -------------------------
# User Terminal Link
# -------------------------
class UTLCreatedEvent(Event):
    type: EventType = EventType.UTL_CREATED
    satellite_id: int
    user_terminal_id: int
    distance_km: float | None = None
    elevation_above_horizon_angle: float | None = None
    estimated_link_duration: float | None = None


class UTLUpdatedEvent(Event):
    type: EventType = EventType.UTL_UPDATED
    satellite_id: int
    user_terminal_id: int
    distance_km: float | None = None
    elevation_above_horizon_angle: float | None = None
    estimated_link_duration: float | None = None


class UTLRemovedEvent(Event):
    type: EventType = EventType.UTL_REMOVED
    satellite_id: int
    user_terminal_id: int


# -------------------------
# Ground Object Link
# -------------------------
class GOLCreatedEvent(Event):
    type: EventType = EventType.GOL_CREATED
    ground_object_a_id: int
    ground_object_b_id: int
    distance_km: float | None = None


class GOLUpdatedEvent(Event):
    type: EventType = EventType.GOL_UPDATED
    ground_object_a_id: int
    ground_object_b_id: int
    distance_km: float | None = None


class GOLRemovedEvent(Event):
    type: EventType = EventType.GOL_REMOVED
    ground_object_a_id: int
    ground_object_b_id: int
