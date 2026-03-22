from sat_com_model.models import (
    MovementModel,
    T_Shell,
    Satellite,
    GroundStation,
    UserTerminal,
    PointOfPresence,
)


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
