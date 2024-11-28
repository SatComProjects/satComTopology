from typing import Optional, List

from pydantic import BaseModel, Field

from sat_com_model.models import WalkerShell, GroundObjectDomain


class CesiumRendererShellProperty(BaseModel):
    ascending_satellite_color: str = Field(default="LIGHTSTEELBLUE")
    descending_satellite_color: str = Field(default="KHAKI")
    satellites_size: float = Field(default=30000)
    adjacent_inter_satellite_link_color: str = Field(default="PERU")
    orbital_inter_satellite_link_color: str = Field(default="YELLOWGREEN")
    inter_satellite_link_width: float = Field(default=1)

    link_flow_width: float = Field(default=1)

    route_link_color: str = Field(default="DARKRED")
    route_link_size: float = Field(default=2)

    satellite_model_path: Optional[str] = Field(default=None)


class ShellCustomProperty(BaseModel):
    shell_identifier: str
    cesium_property: CesiumRendererShellProperty


class CesiumRendererGroundObjectProperty(BaseModel):
    ground_object_color: str = Field(default="ORCHID")
    ground_object_size: float = Field(default=5000)

    ground_object_link_color: str = Field(default="FIREBRICK")

    ground_object_model_path: Optional[str] = Field(default=None)


class GroundObjectDomainCustomProperty(BaseModel):
    ground_object_domain: str
    cesium_property: CesiumRendererGroundObjectProperty


class CesiumProperty(BaseModel):
    shell_to_display: List[str] = Field(default=list())

    display_ground_objects: bool = Field(default=True)
    display_ground_links: bool = Field(default=True)
    display_satellite: bool = Field(default=True)
    display_inter_satellite_link: bool = Field(default=True)

    link_flow_width: float = Field(default=1)

    cesium_token: str | None = Field(default=None)

    cesium_renderer_ground_object_property: CesiumRendererGroundObjectProperty = Field(
        default_factory=CesiumRendererGroundObjectProperty
    )
    cesium_renderer_shell_property: CesiumRendererShellProperty = Field(
        default_factory=CesiumRendererShellProperty
    )

    shell_custom_custom_properties: List[ShellCustomProperty] = Field(default=list())

    ground_object_domain_custom_properties: List[GroundObjectDomainCustomProperty] = (
        Field(default=list())
    )
