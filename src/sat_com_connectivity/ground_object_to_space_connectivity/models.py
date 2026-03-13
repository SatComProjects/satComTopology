from pydantic import BaseModel, Field

from sat_com_model.models import GroundObject, Satellite, GroundToSpaceLink


class GroundToSpaceConnection(BaseModel):
    ground_object: GroundObject = Field(default=None)
    satellite: Satellite = Field(default=None)
    connection_info: dict = Field(default_factory=dict)


class GroundToSpaceUpdate(BaseModel):
    ground_to_space_link: GroundToSpaceLink = Field(default=None)
    connection_info: dict = Field(default_factory=dict)


class ComputedGroundObjectConnectionsResult(BaseModel):
    new_ground_object_connections: list[GroundToSpaceConnection] = Field(
        default_factory=list
    )
    updated_links: list[GroundToSpaceUpdate] = Field(default_factory=list)

    obsolete_links: list[GroundToSpaceLink] = Field(default_factory=list)
