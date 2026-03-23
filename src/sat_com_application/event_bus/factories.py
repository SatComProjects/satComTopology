from abc import abstractmethod, ABC
from dataclasses import field, dataclass

from sat_com_application.event_bus.events import (
    ISLCreatedEvent,
    ISLUpdatedEvent,
    ISLRemovedEvent,
    GSLCreatedEvent,
    GSLUpdatedEvent,
    GSLRemovedEvent,
    UTLCreatedEvent,
    UTLUpdatedEvent,
    UTLRemovedEvent,
)
from sat_com_model.models import (
    InterSatelliteLink,
    GroundStationLink,
    UserTerminalLink,
    OpticalConstraint,
)


class AbstractISLEventFactory(ABC):

    @abstractmethod
    def created(
        self,
        link: InterSatelliteLink,
    ) -> ISLCreatedEvent: ...

    @abstractmethod
    def updated(
        self,
        link: InterSatelliteLink,
    ) -> ISLUpdatedEvent:
        pass

    @abstractmethod
    def removed(self, link: InterSatelliteLink) -> ISLRemovedEvent:
        pass


class AbstractGSLEventFactory(ABC):

    @abstractmethod
    def created(self, link: GroundStationLink) -> GSLCreatedEvent:
        pass

    @abstractmethod
    def updated(self, link: GroundStationLink) -> GSLUpdatedEvent:
        pass

    @abstractmethod
    def removed(self, link: GroundStationLink) -> GSLRemovedEvent:
        pass


class AbstractUTLEventFactory(ABC):

    @abstractmethod
    def created(self, link: UserTerminalLink) -> UTLCreatedEvent:
        pass

    @abstractmethod
    def updated(self, link: UserTerminalLink) -> UTLUpdatedEvent:
        pass

    @abstractmethod
    def removed(self, link: UserTerminalLink) -> UTLRemovedEvent:
        pass


def _terminal_id(terminal) -> str | None:
    return str(terminal.terminal_id) if terminal is not None else None


def _constraint_field(constraint: OpticalConstraint | None, field: str) -> float | None:
    """
    Safely read one field from an OpticalConstraint.
    Returns None if the constraint is None or the field itself is None.
    """
    if constraint is None:
        return None
    return getattr(constraint, field, None)


class DefaultISLEventFactory(AbstractISLEventFactory):

    def created(self, link: InterSatelliteLink) -> ISLCreatedEvent:
        return ISLCreatedEvent(
            link_id=link.link_id.hex,
            satellite_a_id=link.source.topology_uniq_id,
            satellite_b_id=link.destination.topology_uniq_id,
            direction=str(link.inter_satellite_direction),
            terminal_a_id=_terminal_id(link.source_optical_terminal),
            terminal_b_id=_terminal_id(link.destination_optical_terminal),
            azimuth_a_deg=_constraint_field(
                link.source_constraint, "azimuth_angle_degree"
            ),
            elevation_a_deg=_constraint_field(
                link.source_constraint, "elevation_angle_degree"
            ),
            angular_velocity_a_deg_s=_constraint_field(
                link.source_constraint, "angular_velocity_rate_degree_per_second"
            ),
            azimuth_b_deg=_constraint_field(
                link.destination_constraint, "azimuth_angle_degree"
            ),
            elevation_b_deg=_constraint_field(
                link.destination_constraint, "elevation_angle_degree"
            ),
            angular_velocity_b_deg_s=_constraint_field(
                link.destination_constraint, "angular_velocity_rate_degree_per_second"
            ),
        )

    def updated(self, link: InterSatelliteLink) -> ISLUpdatedEvent:
        return ISLUpdatedEvent(
            link_id=link.link_id.hex,
            satellite_a_id=link.get_satellite_source().topology_uniq_id,
            satellite_b_id=link.get_satellite_destination().topology_uniq_id,
            terminal_a_id=_terminal_id(link.source_optical_terminal),
            terminal_b_id=_terminal_id(link.destination_optical_terminal),
            azimuth_a_deg=_constraint_field(
                link.source_constraint, "azimuth_angle_degree"
            ),
            elevation_a_deg=_constraint_field(
                link.source_constraint, "elevation_angle_degree"
            ),
            angular_velocity_a_deg_s=_constraint_field(
                link.source_constraint, "angular_velocity_rate_degree_per_second"
            ),
            azimuth_b_deg=_constraint_field(
                link.destination_constraint, "azimuth_angle_degree"
            ),
            elevation_b_deg=_constraint_field(
                link.destination_constraint, "elevation_angle_degree"
            ),
            angular_velocity_b_deg_s=_constraint_field(
                link.destination_constraint, "angular_velocity_rate_degree_per_second"
            ),
        )

    def removed(self, link: InterSatelliteLink) -> ISLRemovedEvent:
        # Must be called BEFORE unbind_terminals() — terminals are still set here
        return ISLRemovedEvent(
            link_id=link.link_id.hex,
            satellite_a_id=link.source.topology_uniq_id,
            satellite_b_id=link.destination.topology_uniq_id,
            direction=str(link.inter_satellite_direction),
            terminal_a_id=_terminal_id(link.source_optical_terminal),
            terminal_b_id=_terminal_id(link.destination_optical_terminal),
        )


class DefaultGSLEventFactory(AbstractGSLEventFactory):

    def created(self, link: GroundStationLink) -> GSLCreatedEvent:
        return GSLCreatedEvent(
            link_id=link.link_id.hex,
            satellite_id=link.get_satellite().topology_uniq_id,
            ground_station_id=link.get_ground_station().topology_uniq_id,
            elevation_angle=link.elevation_above_horizon_angle,
            estimated_duration=link.estimated_link_duration,
        )

    def updated(self, link: GroundStationLink) -> GSLUpdatedEvent:
        return GSLUpdatedEvent(
            link_id=link.link_id.hex,
            satellite_id=link.get_satellite().topology_uniq_id,
            ground_station_id=link.get_ground_station().topology_uniq_id,
            elevation_above_horizon_angle=link.elevation_above_horizon_angle,
            distance_km=link.distance_km,
            estimated_link_duration=link.estimated_link_duration,
        )

    def removed(self, link: GroundStationLink) -> GSLRemovedEvent:
        return GSLRemovedEvent(
            link_id=link.link_id.hex,
            satellite_id=link.get_satellite().topology_uniq_id,
            ground_station_id=link.get_ground_station().topology_uniq_id,
        )


class DefaultUTLEventFactory(AbstractUTLEventFactory):

    def created(self, link: UserTerminalLink) -> UTLCreatedEvent:
        return UTLCreatedEvent(
            link_id=link.link_id.hex,
            satellite_id=link.get_satellite().topology_uniq_id,
            user_terminal_id=link.get_user_terminal().topology_uniq_id,
            elevation_above_horizon_angle=link.elevation_above_horizon_angle,
            estimated_link_duration=link.estimated_link_duration,
        )

    def updated(self, link: UserTerminalLink) -> UTLUpdatedEvent:
        return UTLUpdatedEvent(
            link_id=link.link_id.hex,
            satellite_id=link.get_satellite().topology_uniq_id,
            user_terminal_id=link.get_user_terminal().topology_uniq_id,
            elevation_above_horizon_angle=link.elevation_above_horizon_angle,
            distance_km=link.distance_km,
            estimated_link_duration=link.estimated_link_duration,
        )

    def removed(self, link: UserTerminalLink) -> UTLRemovedEvent:
        return UTLRemovedEvent(
            link_id=link.link_id.hex,
            satellite_id=link.get_satellite().topology_uniq_id,
            user_terminal_id=link.get_user_terminal().topology_uniq_id,
        )


@dataclass
class EventFactories:
    isl_event_factory: AbstractISLEventFactory = field(
        default_factory=DefaultISLEventFactory
    )
    gsl_event_factory: AbstractGSLEventFactory = field(
        default_factory=DefaultGSLEventFactory
    )
    utl_event_factory: AbstractUTLEventFactory = field(
        default_factory=DefaultUTLEventFactory
    )
