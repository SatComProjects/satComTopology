from dataclasses import dataclass, field
from typing import Optional

from sat_com_model.factories import (
    AbstractSatelliteFactory,
    AbstractGroundStationFactory,
    AbstractUserTerminalFactory,
    AbstractPointOfPresenceFactory,
)
from sat_com_model.models import (
    Satellite,
    T_Shell,
    MovementModel,
    GroundStation,
    UserTerminal,
    PointOfPresence,
    GroundObjectDomain,
)


def _domain_identifier(ground_object_domain: Optional[GroundObjectDomain]) -> str:
    return ground_object_domain.identifier if ground_object_domain else "public"


class DefaultSatelliteFactory(AbstractSatelliteFactory):

    def create_satellite(
        self,
        satellite_name: str,
        object_id: int,
        shell: T_Shell,
        movement_model: MovementModel,
        domain: str = "public",
    ) -> Satellite[T_Shell]:
        return Satellite(
            satellite_name=satellite_name,
            object_id=object_id,
            domain=domain,
            shell=shell,
            movement_model=movement_model,
        )


class DefaultGroundStationFactory(AbstractGroundStationFactory):

    def create_ground_station(
        self,
        object_id: int,
        label: str = "unknown",
        longitude: float = 0.0,
        latitude: float = 0.0,
        altitude: float = 0.0,
        ground_object_domain: Optional[GroundObjectDomain] = None,
    ) -> GroundStation:
        ground_station = GroundStation(
            object_id=object_id, domain=_domain_identifier(ground_object_domain)
        )
        return self._configure_ground_object(
            ground_station, label, longitude, latitude, altitude, ground_object_domain
        )


class DefaultUserTerminalFactory(AbstractUserTerminalFactory):

    def create_user_terminal(
        self,
        object_id: int,
        label: str = "unknown",
        longitude: float = 0.0,
        latitude: float = 0.0,
        altitude: float = 0.0,
        ground_object_domain: Optional[GroundObjectDomain] = None,
    ) -> UserTerminal:
        user_terminal = UserTerminal(
            object_id=object_id, domain=_domain_identifier(ground_object_domain)
        )
        return self._configure_ground_object(
            user_terminal, label, longitude, latitude, altitude, ground_object_domain
        )


class DefaultPointOfPresenceFactory(AbstractPointOfPresenceFactory):

    def create_point_of_presence(
        self,
        object_id: int,
        label: str = "unknown",
        longitude: float = 0.0,
        latitude: float = 0.0,
        altitude: float = 0.0,
        ground_object_domain: Optional[GroundObjectDomain] = None,
    ) -> PointOfPresence:
        point_of_presence = PointOfPresence(
            object_id=object_id, domain=_domain_identifier(ground_object_domain)
        )
        return self._configure_ground_object(
            point_of_presence,
            label,
            longitude,
            latitude,
            altitude,
            ground_object_domain,
        )


@dataclass
class TopologyObjectFactories:
    """
    Factories used by the configuration manager to build the topology objects.

    Replace any field with your own factory to build your own subclass, e.g.:

        class MySatelliteFactory(AbstractSatelliteFactory):
            def create_satellite(self, satellite_name, object_id, shell, movement_model, domain="public"):
                return MySatellite(...)

        YamlConfigurationManager(
            "config.yaml",
            topology_object_factories=TopologyObjectFactories(satellite_factory=MySatelliteFactory()),
        )
    """

    satellite_factory: AbstractSatelliteFactory = field(
        default_factory=DefaultSatelliteFactory
    )
    ground_station_factory: AbstractGroundStationFactory = field(
        default_factory=DefaultGroundStationFactory
    )
    user_terminal_factory: AbstractUserTerminalFactory = field(
        default_factory=DefaultUserTerminalFactory
    )
    point_of_presence_factory: AbstractPointOfPresenceFactory = field(
        default_factory=DefaultPointOfPresenceFactory
    )
