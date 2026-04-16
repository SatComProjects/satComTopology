from pydantic import BaseModel, Field

from sat_com_model.models import GroundObject, Satellite, GroundToSpaceLink


class GroundToSpaceConstraints(BaseModel):
    elevation_angle_above_horizon: float | None = Field(default=None)
    distance_km: float | None = Field(default=None)
    estimated_connection_time: float | None = Field(default=None)


class GroundToSpaceConnection(BaseModel):
    ground_object: GroundObject = Field(default=None)
    satellite: Satellite = Field(default=None)
    ground_to_space_constraints: GroundToSpaceConstraints = Field(
        default_factory=GroundToSpaceConstraints
    )


class GroundToSpaceUpdate(BaseModel):
    ground_to_space_link: GroundToSpaceLink = Field(default=None)

    ground_to_space_constraints: GroundToSpaceConstraints = Field(
        default_factory=GroundToSpaceConstraints
    )


class ComputedGroundObjectConnectionsResult(BaseModel):
    new_ground_object_connections: list[GroundToSpaceConnection] = Field(
        default_factory=list
    )
    updated_links: list[GroundToSpaceUpdate] = Field(default_factory=list)

    obsolete_links: list[GroundToSpaceLink] = Field(default_factory=list)
