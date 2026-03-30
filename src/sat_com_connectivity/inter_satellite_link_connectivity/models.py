from datetime import datetime

from pydantic import BaseModel, Field

from sat_com_model.models import (
    Satellite,
    OpticalLinkTerminal,
    InterSatelliteLinkDirection,
    InterSatelliteLink,
)


class OpticISLVisibilityConstraintResult(BaseModel):
    elevation_angle_degree: float
    azimuth_angle_degree: float
    range_distance_km: float
    angular_velocity_rate_degree_per_second: float
    range_rate: float

    estimated_duration: float | None = Field(default=None)

    flag_elevation: bool
    flag_azimuth: bool
    flag_range: bool
    flag_overall: bool
    flag_angular_velocity: bool

    flag_bidirectional: bool


class PossibleOpticalLink(BaseModel):
    satellite_a: Satellite
    satellite_b: Satellite

    terminal_a: OpticalLinkTerminal
    terminal_b: OpticalLinkTerminal

    constraint_a_to_b: OpticISLVisibilityConstraintResult
    constraint_b_to_a: OpticISLVisibilityConstraintResult

    bidirectional_possible: bool
    selection_score: float

    estimated_duration: float | None = Field(default=None)

    temporary_unavailable: bool = Field(default=False)
    estimated_recover_time: float | None = Field(default=None)

    class Config:
        arbitrary_types_allowed = True


class LinkAssociation(BaseModel):
    """
    Describes one intended or existing terminal-to-terminal connection.
    link=None means the ISL has not been created yet (new_links).
    link=<existing> means the ISL already exists (updated_links / obsolete_links).
    """

    satellite_a: Satellite
    terminal_a: OpticalLinkTerminal | None = Field(default=None)
    satellite_b: Satellite
    terminal_b: OpticalLinkTerminal | None = Field(default=None)
    direction: InterSatelliteLinkDirection = Field(
        default=InterSatelliteLinkDirection.UNDEFINED
    )
    link: InterSatelliteLink | None = Field(default=None)

    constraint_a_to_b: OpticISLVisibilityConstraintResult | None = Field(default=None)

    constraint_b_to_a: OpticISLVisibilityConstraintResult | None = Field(default=None)

    temporary_unavailable: bool = Field(default=False)

    recovery_time: datetime | None = Field(default=None)

    model_config = {"arbitrary_types_allowed": True}

    def __repr__(self):
        return f"LinkAssociation({self.satellite_a.topology_uniq_id}:{self.terminal_a.terminal_id} <-> {self.satellite_b.topology_uniq_id}:{self.terminal_b.terminal_id}, direction={self.direction}, link_exists={self.link is not None})"


class InterSatelliteConnectivityResult(BaseModel):
    """
    Pure result object returned by a connectivity strategy.
    The SimulationManager consumes this to mutate simulation state:
      - new_links     → create ISL + bind terminals
      - obsolete_links → remove ISL + unbind terminals
      - updated_links  → update ISL metadata (distance, angular velocity, ...)
    No simulation state is modified inside the strategy.
    """

    new_links: list[LinkAssociation] = Field(default_factory=list)
    obsolete_links: list[LinkAssociation] = Field(default_factory=list)
    updated_links: list[LinkAssociation] = Field(default_factory=list)


class ConnectivityLedger:
    """
    Accumulates ISL decisions across multiple phases.
    Enforces that each link and each terminal appears in exactly one outcome.
    Both phases write to the same ledger — no double-obsolete is possible.
    """

    def __init__(self):
        self._new: list[LinkAssociation] = []
        self._obsolete: list[LinkAssociation] = []
        self._updated: list[LinkAssociation] = []

        self._obsoleted_links: set[InterSatelliteLink] = set()
        self._updated_links: set[InterSatelliteLink] = set()
        self._booked_terminals: set[OpticalLinkTerminal] = set()

    def add_new(self, association: LinkAssociation) -> None:
        self._booked_terminals.add(association.terminal_a)
        self._booked_terminals.add(association.terminal_b)
        self._new.append(association)

    def add_obsolete(self, association: LinkAssociation) -> None:
        if association.link in self._obsoleted_links:
            return  # already scheduled for removal — skip
        self._obsoleted_links.add(association.link)
        self._obsolete.append(association)

    def add_updated(self, association: LinkAssociation) -> None:
        self._updated_links.add(association.link)
        self._booked_terminals.add(association.terminal_a)
        self._booked_terminals.add(association.terminal_b)
        self._updated.append(association)

    def is_terminal_booked(self, terminal: OpticalLinkTerminal) -> bool:
        return terminal in self._booked_terminals

    def is_link_obsoleted(self, link: InterSatelliteLink) -> bool:
        return link in self._obsoleted_links

    def is_link_accounted(self, link: InterSatelliteLink) -> bool:
        return link in self._obsoleted_links or link in self._updated_links

    def to_result(self) -> InterSatelliteConnectivityResult:
        return InterSatelliteConnectivityResult(
            new_links=list(self._new),
            obsolete_links=list(self._obsolete),
            updated_links=list(self._updated),
        )
