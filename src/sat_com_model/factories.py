from abc import abstractmethod, ABC
from typing import Optional

from sat_com_model.models import (
    MovementModel,
    T_Shell,
    Satellite,
    GroundStation,
    UserTerminal,
    PointOfPresence,
    GroundObjectDomain,
)

# Abstract factories for the topology objects.
#
# The builder never instantiates Satellite / GroundStation / UserTerminal / PointOfPresence
# directly: it goes through these factories. To use your own subclass, implement the
# matching factory and inject it in the configuration manager (see
# sat_com_builder.factories.TopologyObjectFactories).


class AbstractSatelliteFactory(ABC):

    @abstractmethod
    def create_satellite(
        self,
        satellite_name: str,
        object_id: int,
        shell: T_Shell,
        movement_model: MovementModel,
        domain: str = "public",
    ) -> Satellite[T_Shell]:
        """
        Create a satellite with its movement model already set.

        :param satellite_name: Name of the satellite, typically from the TLE.
        :param object_id: Business identifier within its constellation.
        :param shell: Walker or SSO shell the satellite belongs to.
        :param movement_model: Propagation model, fully initialised.
        :param domain: Constellation identifier / owner domain.
        """
        raise NotImplementedError()


class AbstractGroundObjectFactory(ABC):
    """
    Shared signature of the ground object factories (ground station, user terminal,
    point of presence).
    """

    @staticmethod
    def _configure_ground_object(
        ground_object,
        label: str,
        longitude: float,
        latitude: float,
        altitude: float,
        ground_object_domain: Optional[GroundObjectDomain],
    ):
        """Set the fields every ground object shares. Returns the same object."""
        ground_object.set_position(
            longitude=longitude, latitude=latitude, altitude=altitude
        )
        ground_object.label = label
        ground_object.ground_object_domain = ground_object_domain
        return ground_object


class AbstractGroundStationFactory(AbstractGroundObjectFactory):

    @abstractmethod
    def create_ground_station(
        self,
        object_id: int,
        label: str = "unknown",
        longitude: float = 0.0,
        latitude: float = 0.0,
        altitude: float = 0.0,
        ground_object_domain: Optional[GroundObjectDomain] = None,
    ) -> GroundStation:
        """
        Create a ground station.

        :param object_id: Business identifier of the ground station.
        :param label: Human readable name.
        :param longitude: Longitude in degrees.
        :param latitude: Latitude in degrees.
        :param altitude: Altitude in km.
        :param ground_object_domain: Domain of the ground station. Its identifier is used as `domain`.
        """
        raise NotImplementedError()


class AbstractUserTerminalFactory(AbstractGroundObjectFactory):

    @abstractmethod
    def create_user_terminal(
        self,
        object_id: int,
        label: str = "unknown",
        longitude: float = 0.0,
        latitude: float = 0.0,
        altitude: float = 0.0,
        ground_object_domain: Optional[GroundObjectDomain] = None,
    ) -> UserTerminal:
        """
        Create a user terminal. Same parameters as AbstractGroundStationFactory.create_ground_station.
        """
        raise NotImplementedError()


class AbstractPointOfPresenceFactory(AbstractGroundObjectFactory):

    @abstractmethod
    def create_point_of_presence(
        self,
        object_id: int,
        label: str = "unknown",
        longitude: float = 0.0,
        latitude: float = 0.0,
        altitude: float = 0.0,
        ground_object_domain: Optional[GroundObjectDomain] = None,
    ) -> PointOfPresence:
        """
        Create a point of presence. Same parameters as AbstractGroundStationFactory.create_ground_station.
        """
        raise NotImplementedError()


def create_satellite(
    satellite_name: str,
    object_id: int,
    shell: T_Shell,
    movement_model: MovementModel,
    domain: str = "public",
) -> Satellite[T_Shell]:
    """
    Create a Satellite with all mandatory attributes set at construction time.

    Parameters
    ----------
    satellite_name : str
        Name of the satellite, typically from the TLE.
    object_id : int
        Business identifier within its constellation.
    shell : T_Shell
        Walker or SSO shell the satellite belongs to.
    movement_model : MovementModel
        Propagation model — must be fully initialised before passing.
    domain : str
        Constellation identifier / owner domain.
    """
    return Satellite(
        satellite_name=satellite_name,
        object_id=object_id,
        domain=domain,
        shell=shell,
        movement_model=movement_model,
    )


def create_ground_station(
    object_id: int,
    domain: str = "public",
) -> GroundStation:
    """
    Create a GroundStation.

    Parameters
    ----------
    object_id : int
        Business identifier of the ground station.
    domain : str
        Owner domain.
    """
    return GroundStation(object_id=object_id, domain=domain)


def create_user_terminal(
    object_id: int,
    domain: str = "public",
) -> UserTerminal:
    """
    Create a UserTerminal.

    Parameters
    ----------
    object_id : int
        Business identifier of the user terminal.
    domain : str
        Owner domain.
    """
    return UserTerminal(object_id=object_id, domain=domain)


def create_point_of_presence(
    object_id: int,
    domain: str = "public",
) -> PointOfPresence:
    """
    Create a PointOfPresence.

    Parameters
    ----------
    object_id : int
        Business identifier.
    domain : str
        Owner domain.
    """
    return PointOfPresence(object_id=object_id, domain=domain)
