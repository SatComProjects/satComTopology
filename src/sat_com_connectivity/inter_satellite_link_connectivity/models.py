from pydantic import BaseModel

from sat_com_model.models import Satellite, OpticalLinkTerminal


class OpticISLVisibilityConstraintResult(BaseModel):
    elevation_angle_degree: float
    azimuth_angle_degree: float
    range_distance_km: float
    angular_velocity_rate_degree_per_second: float

    flag_elevation: bool
    flag_azimuth: bool
    flag_range: bool
    flag_overall: bool
    flag_angular_velocity: bool

    flag_bidirectional: bool


class PossibleOpticalLink(BaseModel):
    satellite_a: Satellite
    satellite_b: Satellite

    terminal_a: OpticalLinkTerminal
    terminal_b: OpticalLinkTerminal

    constraint_a_to_b: OpticISLVisibilityConstraintResult
    constraint_b_to_a: OpticISLVisibilityConstraintResult

    bidirectional_possible: bool
    selection_score: float

    class Config:
        arbitrary_types_allowed = True
