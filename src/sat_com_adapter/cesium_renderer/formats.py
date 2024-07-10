from sat_com_adapter.cesium_renderer.factories import (
    CesiumElementFactory,
    CesiumJavaScriptElementFactory,
    CesiumCZMLElementFactory,
)
from sat_com_adapter.cesium_renderer.html_formatter.html_formatters import (
    UserTerminalHtmlFormatter,
    GroundStationHtmlFormatter,
    GroundStationLinkHtmlFormatter,
    UserTerminalLinkHtmlFormatter,
    InterSatelliteLinkHtmlFormatter,
    SatelliteHtmlFormatter,
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
)

SATELLITE_RADIUS = 30000


class CesiumFormat:
    cesium_element_creator: CesiumElementFactory

    def create_link(self, link: Link, color, description, properties: dict):
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
            color=color,
            description=description,
            properties=properties,
        )
        return created_link

    def create_satellite(self, satellite: Satellite, properties: dict = None):
        display_color = "LIGHTSTEELBLUE" if satellite.is_ascending() else "KHAKI"
        cesium_uniq_identifier = get_topology_object_cesium_unique_identifier(
            satellite.topology_uniq_id
        )

        if properties is None:
            properties = {}

        properties.update(
            {
                "orbital_node": (
                    "ascending" if satellite.is_ascending() else "descending"
                ),
                "type": satellite.type,
            }
        )

        satellite_js = self.cesium_element_creator.create_sphere(
            sphere_name=satellite.satellite_name,
            position=satellite.get_coordinates(),
            cesium_uniq_identifier=cesium_uniq_identifier,
            color=display_color,
            radius=SATELLITE_RADIUS,
            description=SatelliteHtmlFormatter(satellite).format_to_html(),
            properties=properties,
        )

        return satellite_js

    def create_ground_station(
        self, ground_station: GroundStation, properties: dict = None
    ):
        display_color = "ORCHID"

        cesium_uniq_identifier = get_topology_object_cesium_unique_identifier(
            ground_station.topology_uniq_id
        )

        ground_station_name = "{city} {object_id}. {topology_id}".format(
            city=ground_station.city,
            object_id=ground_station.object_id,
            topology_id=ground_station.topology_uniq_id,
        )
        if properties is None:
            properties = {}

        properties.update({"type": ground_station.type})

        ground_station_js = self.cesium_element_creator.create_sphere(
            sphere_name=ground_station_name,
            position=ground_station.get_coordinates(),
            cesium_uniq_identifier=cesium_uniq_identifier,
            color=display_color,
            radius=5000,
            description=GroundStationHtmlFormatter(ground_station).format_to_html(),
            properties=properties,
        )

        return ground_station_js

    def create_user_terminal(self, user_terminal: UserTerminal):
        display_color = "INDIANRED"

        cesium_uniq_identifier = get_topology_object_cesium_unique_identifier(
            user_terminal.topology_uniq_id
        )

        ground_station_name = "{username} {object_id}. {topology_id}".format(
            username=user_terminal.user_name,
            object_id=user_terminal.object_id,
            topology_id=user_terminal.topology_uniq_id,
        )

        terminal_user_js = self.cesium_element_creator.create_sphere(
            sphere_name=ground_station_name,
            position=user_terminal.get_coordinates(),
            cesium_uniq_identifier=cesium_uniq_identifier,
            color=display_color,
            radius=5000,
            description=UserTerminalHtmlFormatter(user_terminal).format_to_html(),
        )

        return terminal_user_js

    def create_ground_station_link(self, ground_station_link: GroundStationLink):
        display_color = "FIREBRICK"

        html_description = (
            GroundStationLinkHtmlFormatter(ground_station_link).format_to_html(),
        )

        return self.create_link(
            link=ground_station_link,
            color=display_color,
            description=html_description,
            properties={},
        )

    def create_user_terminal_link(self, user_terminal_link: UserTerminalLink):
        display_color = "DEEPPINK"

        html_description = (
            UserTerminalLinkHtmlFormatter(user_terminal_link).format_to_html(),
        )

        return self.create_link(
            link=user_terminal_link,
            color=display_color,
            description=html_description,
            properties={},
        )

    def create_inter_satellite_link_flow(
        self, inter_satellite_link: InterSatelliteLink
    ):
        color_level = (
            inter_satellite_link.total_capacity_between_hops_bidirectional()
            / (inter_satellite_link.link_maximum_capacity * 2)
        ) * 100

        html_description = InterSatelliteLinkHtmlFormatter(
            inter_satellite_link
        ).format_to_html()
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
        return self.create_link(
            link=inter_satellite_link,
            color="COLOR_GREEN_TO_RED_" + str(int(color_level)),
            description=html_description,
            properties={},
        )

    def create_inter_satellite_link(self, inter_satellite_link: InterSatelliteLink):
        display_color = (
            "YELLOWGREEN"
            if inter_satellite_link.inter_satellite_direction
            == InterSatelliteLinkDirection.ORBITAL
            else "PERU"
        )

        html_description = (
            InterSatelliteLinkHtmlFormatter(inter_satellite_link).format_to_html(),
        )

        return self.create_link(
            link=inter_satellite_link,
            color=display_color,
            description=html_description,
            properties={},
        )


class CesiumJavaScriptFormat(CesiumFormat):
    cesium_element_creator = CesiumJavaScriptElementFactory()


class CesiumCZMLFormat(CesiumFormat):
    cesium_element_creator = CesiumCZMLElementFactory()
