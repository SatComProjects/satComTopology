class TopologyConnectionError(Exception):
    pass


class ConnectionBetweenSameSatelliteForbiddenError(TopologyConnectionError):
    pass


class ConnectionBetweenSameTopologyForbiddenError(TopologyConnectionError):
    pass


class InterSatelliteConnectionError(TopologyConnectionError):
    pass


class GroundStationConnectionError(TopologyConnectionError):
    pass


class UserTerminalConnectionError(TopologyConnectionError):
    pass


class GroundObjectLinkConnectionError(TopologyConnectionError):
    pass


class SimulationContextError(Exception):
    pass


class TopologyObjectNotFoundError(Exception):
    pass


class TopologyIdentifierNotDefinedError(Exception):
    pass


class OrbitalObjectMovementModelUndefinedError(Exception):
    pass


class DistanceModelUndefinedError(Exception):
    pass


class LinkNotFoundError(Exception):
    pass


class GroundObjectDomainNotFoundError(Exception):
    pass


class WalkerShellNotFoundError(Exception):
    pass


class InvalidGroundObjectTypeError(Exception):
    pass
