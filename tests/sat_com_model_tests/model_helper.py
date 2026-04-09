import datetime

from sat_com_model.models import (
    Satellite,
    GroundStation,
    UserTerminal,
    MovementModel,
    SpatialPosition,
    WalkerShell,
    SatelliteConfiguration,
    OpticalTerminalInstallationConfiguration,
    OpticalTerminalConfiguration,
    InterSatelliteLinkOrientation,
)

# ---------------------------------------------------------------------------
# Default optical terminal configuration — matches CONDOR gen1 defaults
# ---------------------------------------------------------------------------


def make_default_satellite_configuration() -> SatelliteConfiguration:
    """
    4-terminal configuration matching the default SatelliteConfiguration:
      az=  0°  → INTRA_PLANE_FORWARD
      az= 90°  → INTER_PLANE_LEFT   (also inter-shell capable)
      az=-90°  → INTER_PLANE_RIGHT  (also inter-shell capable)
      az=-180° → INTRA_PLANE_BACKWARD
    """
    terminal_cfg = OpticalTerminalConfiguration()

    return SatelliteConfiguration(
        optical_inter_satellite_link_installations=[
            OpticalTerminalInstallationConfiguration(
                azimuth_angle_configuration=0.0,
                elevation_angle_configuration=-180.0,
                descriptor=InterSatelliteLinkOrientation.INTRA_PLANE_FORWARD,
                orientation_possibilities=[
                    InterSatelliteLinkOrientation.INTRA_PLANE_FORWARD,
                ],
                optical_terminal_property=terminal_cfg,
            ),
            OpticalTerminalInstallationConfiguration(
                azimuth_angle_configuration=90.0,
                elevation_angle_configuration=-180.0,
                descriptor=InterSatelliteLinkOrientation.INTER_PLANE_LEFT,
                orientation_possibilities=[
                    InterSatelliteLinkOrientation.INTER_PLANE_LEFT,
                    InterSatelliteLinkOrientation.INTER_SHELL_LEFT,
                ],
                optical_terminal_property=terminal_cfg,
            ),
            OpticalTerminalInstallationConfiguration(
                azimuth_angle_configuration=-90.0,
                elevation_angle_configuration=-180.0,
                descriptor=InterSatelliteLinkOrientation.INTER_PLANE_RIGHT,
                orientation_possibilities=[
                    InterSatelliteLinkOrientation.INTER_PLANE_RIGHT,
                    InterSatelliteLinkOrientation.INTER_SHELL_RIGHT,
                ],
                optical_terminal_property=terminal_cfg,
            ),
            OpticalTerminalInstallationConfiguration(
                azimuth_angle_configuration=-180.0,
                elevation_angle_configuration=-180.0,
                descriptor=InterSatelliteLinkOrientation.INTRA_PLANE_BACKWARD,
                orientation_possibilities=[
                    InterSatelliteLinkOrientation.INTRA_PLANE_BACKWARD,
                ],
                optical_terminal_property=terminal_cfg,
            ),
        ]
    )


def make_fake_walker_shell(identifier: str = "test-shell") -> WalkerShell:
    """
    Minimal WalkerShell with a full 4-terminal satellite configuration.
    Satellites created with this shell will have optical_link_terminals populated.
    """
    return WalkerShell(
        identifier=identifier,
        amount_of_orbit_plane=1,
        amount_of_satellite_per_orbit_plane=1,
        satellite_configuration=make_default_satellite_configuration(),
    )


# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------


def create_fake_satellite_with_object_id(
    satellite_id: int,
    shell: WalkerShell = None,
    movement_model: MovementModel = None,
) -> Satellite:
    """
    Create a test satellite. If no shell is provided a default WalkerShell
    with 4 optical terminals is used so all ISL-related tests have terminals
    available out of the box.

    If no movement_model is provided, a FakeMovementModel is used by default.
    Set movement_model=False to create a satellite without any movement model.
    """
    if shell is None:
        shell = make_fake_walker_shell()

    # Handle the case where movement_model is explicitly set to False (no movement model)
    if movement_model is False:
        # Don't include movement_model in constructor to allow default (None)
        satellite = Satellite(
            satellite_name=f"Test Satellite {satellite_id}",
            shell=shell,
        )
    else:
        # If movement_model is None or not provided, use FakeMovementModel
        if movement_model is None:
            movement_model = FakeMovementModel()

        satellite = Satellite(
            satellite_name=f"Test Satellite {satellite_id}",
            shell=shell,
            movement_model=movement_model,
        )

    satellite.object_id = satellite_id
    return satellite


def create_fake_ground_station_with_object_id(ground_station_id: int) -> GroundStation:
    ground_station = GroundStation()
    ground_station.object_id = ground_station_id
    ground_station.spatial_position_info = SpatialPosition(
        longitude=0.0,
        latitude=0.0,
        altitude=0.0,
    )
    return ground_station


def create_fake_user_terminal_with_object_id(user_terminal_id: int) -> UserTerminal:
    user_terminal = UserTerminal()
    user_terminal.object_id = user_terminal_id
    user_terminal.spatial_position_info = SpatialPosition(
        longitude=0.0,
        latitude=0.0,
        altitude=0.0,
    )
    return user_terminal


# ---------------------------------------------------------------------------
# FakeMovementModel
# ---------------------------------------------------------------------------


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

    def get_datetime(self) -> datetime.datetime:
        return datetime.datetime.utcnow()

    def get_longitude_latitude(self):
        return SpatialPosition(
            longitude=self.longitude,
            latitude=self.latitude,
            altitude=self.altitude,
        )

    def get_longitude_latitude_altitude(self, delta_t: float = 0.0) -> SpatialPosition:
        return SpatialPosition(
            longitude=self.longitude,
            latitude=self.latitude,
            altitude=self.altitude,
        )

    def get_position_earth_general_inertial(
        self, delta: float = 0.0
    ) -> tuple[float, float, float]:
        return 100.0, 100.0, 100.0

    def get_velocity_earth_general_inertial(
        self, delta: float = 0.0
    ) -> tuple[float, float, float]:
        return 0.5, 0.5, 7.5
