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
    link_id: str

    type: EventType = EventType.ISL_CREATED
    satellite_a_id: int
    satellite_b_id: int

    direction: str | None = None
    distance_km: float | None = None

    terminal_a_id: str | None = None  # OpticalLinkTerminal.terminal_id as str
    terminal_b_id: str | None = None

    azimuth_a_deg: float | None = None
    elevation_a_deg: float | None = None
    angular_velocity_a_deg_s: float | None = None
    range_rate: float | None = None

    estimated_duration_a: float | None = None
    estimated_duration_b: float | None = None

    azimuth_b_deg: float | None = None
    elevation_b_deg: float | None = None
    angular_velocity_b_deg_s: float | None = None


class ISLUpdatedEvent(Event):
    link_id: str

    type: EventType = EventType.ISL_UPDATED
    satellite_a_id: int
    satellite_b_id: int

    direction: str | None = None
    distance_km: float | None = None

    terminal_a_id: str | None = None
    terminal_b_id: str | None = None

    azimuth_a_deg: float | None = None
    elevation_a_deg: float | None = None
    angular_velocity_a_deg_s: float | None = None
    range_rate: float | None = None

    azimuth_b_deg: float | None = None
    elevation_b_deg: float | None = None
    angular_velocity_b_deg_s: float | None = None


class ISLRemovedEvent(Event):
    link_id: str
    type: EventType = EventType.ISL_REMOVED
    satellite_a_id: int
    satellite_b_id: int

    direction: str | None = None
    terminal_a_id: str | None = None
    terminal_b_id: str | None = None


# -------------------------
# Ground Station Link
# -------------------------
class GSLCreatedEvent(Event):
    link_id: str
    type: EventType = EventType.GSL_CREATED
    satellite_id: int
    ground_station_id: int
    distance_km: float | None = None
    elevation_angle: float | None = None
    estimated_duration_a: float | None = None


class GSLUpdatedEvent(Event):
    link_id: str
    type: EventType = EventType.GSL_UPDATED
    satellite_id: int
    ground_station_id: int
    distance_km: float | None = None
    elevation_above_horizon_angle: float | None = None
    estimated_link_duration: float | None = None


class GSLRemovedEvent(Event):
    link_id: str
    type: EventType = EventType.GSL_REMOVED
    satellite_id: int
    ground_station_id: int


# -------------------------
# User Terminal Link
# -------------------------
class UTLCreatedEvent(Event):
    link_id: str
    type: EventType = EventType.UTL_CREATED
    satellite_id: int
    user_terminal_id: int
    distance_km: float | None = None
    elevation_above_horizon_angle: float | None = None
    estimated_link_duration: float | None = None


class UTLUpdatedEvent(Event):
    link_id: str
    type: EventType = EventType.UTL_UPDATED
    satellite_id: int
    user_terminal_id: int
    distance_km: float | None = None
    elevation_above_horizon_angle: float | None = None
    estimated_link_duration: float | None = None


class UTLRemovedEvent(Event):
    link_id: str
    type: EventType = EventType.UTL_REMOVED
    satellite_id: int
    user_terminal_id: int


# -------------------------
# Ground Object Link
# -------------------------
class GOLCreatedEvent(Event):
    link_id: str
    type: EventType = EventType.GOL_CREATED
    ground_object_a_id: int
    ground_object_b_id: int
    distance_km: float | None = None


class GOLUpdatedEvent(Event):
    link_id: str
    type: EventType = EventType.GOL_UPDATED
    ground_object_a_id: int
    ground_object_b_id: int
    distance_km: float | None = None


class GOLRemovedEvent(Event):
    link_id: str
    type: EventType = EventType.GOL_REMOVED
    ground_object_a_id: int
    ground_object_b_id: int
