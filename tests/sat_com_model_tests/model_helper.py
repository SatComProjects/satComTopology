from sat_com_model.models import (
    Satellite,
    GroundStation,
    UserTerminal,
    MovementModel,
    SpatialPosition,
)


def create_fake_satellite_with_object_id(satellite_id: int) -> Satellite:
    satellite = Satellite(satellite_name="Test Satellite " + str(satellite_id))
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


class FakeMovementModel(MovementModel):
    def __init__(
        self,
        longitude: float = 100,
        latitude: float = 50,
        altitude: float = 400,
        ascending: bool = False,
    ):
        self.longitude = longitude
        self.latitude = latitude
        self.altitude = altitude
        self.ascending = ascending

    def is_ascending(self) -> bool:
        return self.ascending

    def get_longitude_latitude(self) -> SpatialPosition:
        return SpatialPosition(
            longitude=self.longitude, latitude=self.latitude, altitude=self.altitude
        )

    def get_latitude_longitude_altitude(self) -> (float, float, float):
        return self.latitude, self.longitude, self.altitude

    def get_position_earth_general_inertial(self) -> (float, float, float):
        return 100.0, 100.0, 100.0
