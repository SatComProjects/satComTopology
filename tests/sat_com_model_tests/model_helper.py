from sat_com_model.model import Satellite, GroundStation, UserTerminal


def create_fake_satellite_with_object_id(satellite_id: int) -> Satellite:
    satellite = Satellite()
    satellite.object_id = satellite_id
    return satellite


def create_fake_ground_station_with_object_id(
    ground_station_id: int,
) -> GroundStation:
    ground_station = GroundStation()
    ground_station.object_id = ground_station_id
    return ground_station


def create_fake_user_terminal_with_object_id(
    user_terminal_id: int,
) -> UserTerminal:
    user_terminal = UserTerminal()
    user_terminal.object_id = user_terminal_id
    return user_terminal
