from datetime import datetime

from pyorbital.orbital import Orbital

from src.sat_com_model.model import MovementModel


class PyOrbitalModel(MovementModel):
    orbital_object: Orbital
    clock: datetime

    def __init__(self, tle: dict, clock: datetime = datetime.now()):
        super().__init__()

        self.satellite_name = tle.get("satellite_name")
        self.line1 = tle.get("line1")
        self.line2 = tle.get("line2")
        orb = Orbital(self.satellite_name, line1=self.line1, line2=self.line2)
        self.orbital_object = orb
        self.clock = clock

    def is_ascending(self) -> bool:
        position, velocity = self.orbital_object.get_position(self.clock)
        # Check the sign of the z-coordinate to determine if in the ascending node
        return velocity[2] > 0

    def get_longitude_latitude(self) -> (float, float, float):
        return self.orbital_object.get_lonlatalt(self.clock)

    def get_position_earth_general_inertial(self) -> (float, float, float):
        return self.orbital_object.get_position(self.clock)
