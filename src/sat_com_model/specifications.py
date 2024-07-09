from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from sat_com_model.models import TopologyObject, Link


class BaseSpecification(ABC):
    @abstractmethod
    def is_satisfied_by(self, candidate: Any) -> bool:
        raise NotImplementedError()

    def __call__(self, candidate: Any) -> bool:
        return self.is_satisfied_by(candidate)

    def __and__(self, other: "BaseSpecification") -> "AndSpecification":
        return AndSpecification(self, other)

    def __or__(self, other: "BaseSpecification") -> "OrSpecification":
        return OrSpecification(self, other)

    def __neg__(self) -> "NotSpecification":
        return NotSpecification(self)


@dataclass(frozen=True)
class AndSpecification(BaseSpecification):
    first: BaseSpecification
    second: BaseSpecification

    def is_satisfied_by(self, candidate: Any) -> bool:
        return self.first.is_satisfied_by(candidate) and self.second.is_satisfied_by(
            candidate
        )


@dataclass(frozen=True)
class OrSpecification(BaseSpecification):
    first: BaseSpecification
    second: BaseSpecification

    def is_satisfied_by(self, candidate: Any) -> bool:
        return self.first.is_satisfied_by(candidate) or self.second.is_satisfied_by(
            candidate
        )


@dataclass(frozen=True)
class NotSpecification(BaseSpecification):
    subject: BaseSpecification

    def is_satisfied_by(self, candidate: Any) -> bool:
        return not self.subject.is_satisfied_by(candidate)


@dataclass
class SourceDestinationMatchWithLinkSpecification(BaseSpecification):
    def __init__(self, source: TopologyObject, destination: TopologyObject):
        self.source = source
        self.destination = destination

    def is_satisfied_by(self, candidate: Link) -> bool:
        return (
            self.source == candidate.source
            and self.destination == candidate.destination
        )
