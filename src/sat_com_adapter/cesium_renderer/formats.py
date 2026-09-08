import json

from sat_com_adapter.cesium_renderer.factories import (
    CesiumElementFactory,
    CesiumJavaScriptElementFactory,
    CesiumCZMLElementFactory,
)
from sat_com_adapter.cesium_renderer.html_formatter.html_formatters import HtmlFormatter

from sat_com_adapter.cesium_renderer.models import (
    CesiumProperty,
    CesiumRendererStaticGroundObjectConnectivityProperty,
    CesiumRendererDomainToDomainGroundObjectConnectivity,
    CesiumRendererGroundObjectTypeToTypeRendererCustomProperty,
)
from sat_com_adapter.cesium_renderer.utils import (
    get_topology_object_cesium_unique_identifier,
    get_link_cesium_unique_identifier,
)
from sat_com_model.models import (
    Link,
    InterSatelliteLink,
    GroundStationLink,
    UserTerminalLink,
    Satellite,
    GroundStation,
    UserTerminal,
    InterSatelliteLinkDirection,
    GroundObject,
    GroundObjectLink,
)

SATELLITE_RADIUS = 30000


def _get_walker_shell_identifier(satellite: Satellite):
    """
    walker_shell is Optional on Satellite (e.g. satellites created manually without a shell).
    """
    return satellite.walker_shell.identifier if satellite.walker_shell else None


def _get_ground_object_domain_identifier(ground_object: GroundObject):
    """
    ground_object_domain is Optional on GroundObject (e.g. ground objects created manually without a domain).
    """
    return (
        ground_object.ground_object_domain.identifier
        if ground_object.ground_object_domain
        else None
    )


class CesiumFormat:
    cesium_element_creator: CesiumElementFactory

    def __init__(self, cesium_property: CesiumProperty):
        self.cesium_property = cesium_property

        self.ground_objects_custom_properties = {
            ground_object_custom_property.ground_object_domain: ground_object_custom_property.cesium_property
            for ground_object_custom_property in self.cesium_property.ground_object_domain_custom_properties
        }
        self.shells_customs_properties = {
            shell_custom_property.shell_identifier: shell_custom_property.cesium_property
            for shell_custom_property in self.cesium_property.shell_custom_properties
        }

    def create_link(
        self,
        link: Link,
        color,
        width: float,
        description: str,
        on_ground: bool,
        properties: dict,
    ):
        source = link.source
        destination = link.destination

        link_unique_id = get_link_cesium_unique_identifier(
            source.topology_uniq_id, destination.topology_uniq_id
        )

        if properties is None:
            properties = {}

        properties.update(
            {
                "source": source.topology_uniq_id,
                "destination": destination.topology_uniq_id,
                "type": link.type,
            }
        )
        created_link = self.cesium_element_creator.create_line(
            position_a=source.get_coordinates(),
            position_b=destination.get_coordinates(),
            cesium_uniq_identifier=link_unique_id,
            a_name=str(source.topology_uniq_id),
            b_name=str(destination.topology_uniq_id),
            width=width,
            color=color,
            on_ground=on_ground,
            description=description,
            properties=properties,
        )
        return created_link

    def create_satellite(self, satellite: Satellite, properties: dict = None):
        satellites_cesium_property = self.shells_customs_properties.get(
            _get_walker_shell_identifier(satellite),
            self.cesium_property.cesium_renderer_shell_property,
        )

        display_color = (
            satellites_cesium_property.ascending_satellite_color
            if satellite.is_ascending()
            else satellites_cesium_property.descending_satellite_color
        )
        cesium_uniq_identifier = get_topology_object_cesium_unique_identifier(
            satellite.topology_uniq_id
        )
        if properties is None:
            properties = dict()

        properties.update(**satellite.model_dump(mode="json", exclude_none=True))

        satellite_js = self.cesium_element_creator.create_sphere(
            sphere_name=satellite.satellite_name,
            position=satellite.get_coordinates(),
            cesium_uniq_identifier=cesium_uniq_identifier,
            color=display_color,
            radius=satellites_cesium_property.satellites_size,
            description=HtmlFormatter(satellite).format(),
            properties=properties,
        )

        return satellite_js

    def create_ground_station(
        self, ground_station: GroundStation, properties: dict = None
    ):
        ground_object_domain_properties = self.ground_objects_custom_properties.get(
            _get_ground_object_domain_identifier(ground_station),
            self.cesium_property.cesium_renderer_ground_object_property,
        )

        display_color = ground_object_domain_properties.ground_object_color

        cesium_uniq_identifier = get_topology_object_cesium_unique_identifier(
            ground_station.topology_uniq_id
        )

        ground_station_name = "{label} {object_id}. {topology_id}".format(
            label=ground_station.label,
            object_id=ground_station.object_id,
            topology_id=ground_station.topology_uniq_id,
        )

        if properties is None:
            properties = dict()

        properties.update(**ground_station.model_dump(mode="json", exclude_none=True))

        ground_station_js = self.cesium_element_creator.create_sphere(
            sphere_name=ground_station_name,
            position=ground_station.get_coordinates(),
            cesium_uniq_identifier=cesium_uniq_identifier,
            color=display_color,
            radius=ground_object_domain_properties.ground_object_size,
            description=HtmlFormatter(ground_station).format(),
            properties=properties,
        )

        return ground_station_js

    def create_user_terminal(
        self, user_terminal: UserTerminal, properties: dict = None
    ):
        ground_object_domain_properties = self.ground_objects_custom_properties.get(
            _get_ground_object_domain_identifier(user_terminal),
            self.cesium_property.cesium_renderer_ground_object_property,
        )

        display_color = ground_object_domain_properties.ground_object_color

        cesium_uniq_identifier = get_topology_object_cesium_unique_identifier(
            user_terminal.topology_uniq_id
        )

        user_terminal_name = "{label} {object_id}. {topology_id}".format(
            label=user_terminal.label,
            object_id=user_terminal.object_id,
            topology_id=user_terminal.topology_uniq_id,
        )

        if properties is None:
            properties = dict()

        properties.update(**user_terminal.model_dump(mode="json"))

        terminal_user_js = self.cesium_element_creator.create_sphere(
            sphere_name=user_terminal_name,
            position=user_terminal.get_coordinates(),
            cesium_uniq_identifier=cesium_uniq_identifier,
            color=display_color,
            radius=ground_object_domain_properties.ground_object_size,
            description=HtmlFormatter(user_terminal).format(),
            properties=properties,
        )

        return terminal_user_js

    def create_ground_station_link(self, ground_station_link: GroundStationLink):
        if isinstance(ground_station_link.source, GroundObject):
            ground_object_property = self.ground_objects_custom_properties.get(
                _get_ground_object_domain_identifier(ground_station_link.source),
                self.cesium_property.cesium_renderer_ground_object_property,
            )
        else:
            ground_object_property = self.ground_objects_custom_properties.get(
                _get_ground_object_domain_identifier(ground_station_link.destination),
                self.cesium_property.cesium_renderer_ground_object_property,
            )

        html_description = HtmlFormatter(ground_station_link).format()

        properties = dict()
        properties.update(
            **ground_station_link.model_dump(mode="json", exclude_none=True)
        )

        return self.create_link(
            link=ground_station_link,
            color=ground_object_property.ground_object_link_color,
            width=ground_object_property.ground_object_link_width,
            description=html_description,
            on_ground=False,
            properties=properties,
        )

    def create_user_terminal_link(
        self, user_terminal_link: UserTerminalLink, properties: dict = None
    ):
        if isinstance(user_terminal_link.source, GroundObject):
            ground_object_property = self.ground_objects_custom_properties.get(
                _get_ground_object_domain_identifier(user_terminal_link.source),
                self.cesium_property.cesium_renderer_ground_object_property,
            )
        else:
            ground_object_property = self.ground_objects_custom_properties.get(
                _get_ground_object_domain_identifier(user_terminal_link.destination),
                self.cesium_property.cesium_renderer_ground_object_property,
            )

        html_description = HtmlFormatter(user_terminal_link).format()

        if properties is None:
            properties = dict()

        properties.update(
            **user_terminal_link.model_dump(mode="json", exclude_none=True)
        )

        return self.create_link(
            link=user_terminal_link,
            color=ground_object_property.ground_object_link_color,
            width=ground_object_property.ground_object_link_width,
            description=html_description,
            on_ground=False,
            properties=properties,
        )

    def create_inter_satellite_link_flow(
        self,
        inter_satellite_link: InterSatelliteLink,
        maximum_capacity: float,
        properties: dict = None,
    ):
        color_level = (
            inter_satellite_link.total_capacity_between_hops_bidirectional()
            / maximum_capacity
        ) * 100

        html_description = HtmlFormatter(inter_satellite_link).format()

        html_description += "{source} to {destination}: {capacity}/{max_capacity}<br>".format(
            source=inter_satellite_link.source.topology_uniq_id,
            destination=inter_satellite_link.destination.topology_uniq_id,
            capacity=inter_satellite_link.get_used_capacity_between_hops_unidirectional(
                inter_satellite_link.source, inter_satellite_link.destination
            ),
            max_capacity=inter_satellite_link.link_maximum_capacity,
        )

        html_description += "{source} to {destination}: {capacity}/{max_capacity}<br>".format(
            source=inter_satellite_link.destination.topology_uniq_id,
            destination=inter_satellite_link.source.topology_uniq_id,
            capacity=inter_satellite_link.get_used_capacity_between_hops_unidirectional(
                inter_satellite_link.destination, inter_satellite_link.source
            ),
            max_capacity=inter_satellite_link.link_maximum_capacity,
        )

        if properties is None:
            properties = dict()

        properties.update(
            **inter_satellite_link.model_dump(mode="json", exclude_none=True)
        )

        return self.create_link(
            link=inter_satellite_link,
            color="COLOR_GREEN_TO_RED_" + str(int(color_level)),
            description=html_description,
            width=self.cesium_property.link_flow_width,
            on_ground=False,
            properties=properties,
        )

    def create_inter_satellite_link(
        self, inter_satellite_link: InterSatelliteLink, properties: dict = None
    ):
        satellites_property = self.shells_customs_properties.get(
            _get_walker_shell_identifier(inter_satellite_link.source),
            self.cesium_property.cesium_renderer_shell_property,
        )

        display_color = (
            satellites_property.orbital_inter_satellite_link_color
            if inter_satellite_link.inter_satellite_direction
            == InterSatelliteLinkDirection.ORBITAL
            else satellites_property.adjacent_inter_satellite_link_color
        )

        html_description = HtmlFormatter(inter_satellite_link).format()

        if properties is None:
            properties = dict()
        properties.update(
            **inter_satellite_link.model_dump(mode="json", exclude_none=True)
        )

        return self.create_link(
            link=inter_satellite_link,
            color=display_color,
            width=satellites_property.inter_satellite_link_width,
            description=html_description,
            on_ground=False,
            properties=properties,
        )

    def __get_connectivity_properties(
        self, ground_object_link: GroundObjectLink
    ) -> CesiumRendererStaticGroundObjectConnectivityProperty:
        source = ground_object_link.source
        destination = ground_object_link.destination

        custom_static_properties = (
            self.cesium_property.cesium_static_custom_ground_connectivity_properties
        )

        for properties in custom_static_properties:
            if isinstance(
                properties, CesiumRendererDomainToDomainGroundObjectConnectivity
            ):
                source_domain_identifier = _get_ground_object_domain_identifier(source)
                destination_domain_identifier = _get_ground_object_domain_identifier(
                    destination
                )
                if (
                    properties.domain_a == source_domain_identifier
                    and properties.domain_b == destination_domain_identifier
                ) or (
                    properties.domain_a == destination_domain_identifier
                    and properties.domain_b == source_domain_identifier
                ):
                    return properties.cesium_static_ground_object_connectivity_property

            if isinstance(
                properties, CesiumRendererGroundObjectTypeToTypeRendererCustomProperty
            ):
                if (
                    properties.type_a == source.type
                    and properties.type_b == destination.type
                ) or (
                    properties.type_a == destination.type
                    and properties.type_b == source.type
                ):
                    return properties.cesium_static_ground_object_connectivity_property

        return self.cesium_property.cesium_static_ground_property_connectivity_property

    def create_static_ground_objects_link(
        self, ground_object_link: GroundObjectLink, properties: dict = None
    ):

        ground_object_property = self.__get_connectivity_properties(ground_object_link)

        html_description = HtmlFormatter(ground_object_link).format()

        if properties is None:
            properties = dict()

        properties.update(
            **ground_object_link.model_dump(mode="json", exclude_none=True)
        )

        return self.create_link(
            link=ground_object_link,
            color=ground_object_property.ground_object_to_ground_object_link_color,
            width=ground_object_property.ground_object_to_ground_object_link_width,
            description=html_description,
            on_ground=True,
            properties=properties,
        )


class CesiumJavaScriptFormat(CesiumFormat):
    cesium_element_creator = CesiumJavaScriptElementFactory()


class CesiumCZMLFormat(CesiumFormat):
    cesium_element_creator = CesiumCZMLElementFactory()
