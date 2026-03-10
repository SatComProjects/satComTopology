from pydantic import BaseModel


class OpticISLVisibilityConstraintResult(BaseModel):
    elevation_angle_degree: float
    azimuth_angle_degree: float
    range_distance_km: float
    azimuth_angular_velocity_rate_degree_per_second: float
    elevation_angular_velocity_rate_degree_per_second: float

    flag_elevation: bool
    flag_azimuth: bool
    flag_range: bool
    flag_overall: bool
    flag_angular_velocity: bool

    flag_bidirectional: bool
