import uuid
from typing import List

from pydantic import BaseModel, Field


class Event(BaseModel):
    """
    Event class
    """

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    date: str

    def __eq__(self, other):
        return isinstance(other, Event) and self.id == other.id

    def __hash__(self):
        return hash(self.id)


class TopologyChangeEvent(Event):
    nodes_to_add: List[dict]
    nodes_to_remove: List[dict]

    links_to_add: List[dict]
    links_to_remove: List[dict]
