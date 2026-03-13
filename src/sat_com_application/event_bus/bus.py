import asyncio
from typing import Callable, Awaitable

from pydantic import BaseModel

from sat_com_application.event_bus.events import EventType, Event

Handler = Callable[[Event], Awaitable[None]]


class EventBus(BaseModel):
    _listeners: dict[EventType, list[Handler]] = {}

    model_config = {"arbitrary_types_allowed": True}

    def subscribe(self, event_type: EventType, handler: Handler):
        self._listeners.setdefault(event_type, []).append(handler)

    async def publish(self, event: Event):
        handlers = self._listeners.get(event.type, [])
        await asyncio.gather(*[h(event) for h in handlers])
