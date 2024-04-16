from sat_com_adapter.cesium_renderer.czml_formatter.czml_elements import (
    create_sphere_czml,
    create_line_czml,
)
from sat_com_adapter.cesium_renderer.html_formatter.html_formatters import (
    SatelliteHtmlFormatter,
    InterSatelliteLinkHtmlFormatter,
    GroundStationLinkHtmlFormatter,
    GroundStationHtmlFormatter,
    UserTerminalHtmlFormatter,
    UserTerminalLinkHtmlFormatter,
)
from sat_com_adapter.cesium_renderer.utils import (
    get_topology_object_cesium_unique_identifier,
    get_link_cesium_unique_identifier,
)
from sat_com_model.models import (
    Satellite,
    InterSatelliteLink,
    InterSatelliteLinkDirection,
    GroundStationLink,
    GroundStation,
    UserTerminal,
    UserTerminalLink,
    Link,
)

SATELLITE_RADIUS = 30000


def create_satellite_czml(satellite: Satellite):
    display_color = "LIGHTSTEELBLUE" if satellite.is_ascending() else "KHAKI"
    cesium_uniq_identifier = get_topology_object_cesium_unique_identifier(
        satellite.topology_uniq_id
    )

    satellite_js = create_sphere_czml(
        sphere_name=satellite.satellite_name,
        position=satellite.get_coordinates(),
        cesium_uniq_identifier=cesium_uniq_identifier,
        color=display_color,
        radius=SATELLITE_RADIUS,
        description=SatelliteHtmlFormatter(satellite).format_to_html(),
    )

    return satellite_js


def create_link_czml(link: Link, color, description, properties: dict):
    source = link.source
    destination = link.destination
    link_unique_id = get_link_cesium_unique_identifier(
        source.topology_uniq_id, destination.topology_uniq_id
    )
    properties.update(
        {
            "source": source.topology_uniq_id,
            "destination": destination.topology_uniq_id,
        }
    )

    created_link = create_line_czml(
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


def create_ground_station_czml(ground_station: GroundStation) -> dict:
    display_color = "ORCHID"

    cesium_uniq_identifier = get_topology_object_cesium_unique_identifier(
        ground_station.topology_uniq_id
    )

    ground_station_name = "{city} {object_id}. {topology_id}".format(
        city=ground_station.city,
        object_id=ground_station.object_id,
        topology_id=ground_station.topology_uniq_id,
    )

    ground_station_js = create_sphere_czml(
        sphere_name=ground_station_name,
        position=ground_station.get_coordinates(),
        cesium_uniq_identifier=cesium_uniq_identifier,
        color=display_color,
        radius=5000,
        description=GroundStationHtmlFormatter(ground_station).format_to_html(),
    )

    return ground_station_js


def create_user_terminal_czml(user_terminal: UserTerminal) -> dict:
    display_color = "INDIANRED"

    cesium_uniq_identifier = get_topology_object_cesium_unique_identifier(
        user_terminal.topology_uniq_id
    )

    ground_station_name = "{username} {object_id}. {topology_id}".format(
        username=user_terminal.user_name,
        object_id=user_terminal.object_id,
        topology_id=user_terminal.topology_uniq_id,
    )

    terminal_user_js = create_sphere_czml(
        sphere_name=ground_station_name,
        position=user_terminal.get_coordinates(),
        cesium_uniq_identifier=cesium_uniq_identifier,
        color=display_color,
        radius=5000,
        description=UserTerminalHtmlFormatter(user_terminal).format_to_html(),
    )

    return terminal_user_js


def create_inter_satellite_link_czml(inter_satellite_link: InterSatelliteLink) -> dict:
    display_color = (
        "YELLOWGREEN"
        if inter_satellite_link.inter_satellite_direction
        == InterSatelliteLinkDirection.ORBITAL
        else "PERU"
    )

    html_description = (
        InterSatelliteLinkHtmlFormatter(inter_satellite_link).format_to_html(),
    )

    return create_link_czml(
        link=inter_satellite_link,
        color=display_color,
        description=html_description,
        properties={},
    )


def create_ground_station_link_czml(ground_station_link: GroundStationLink) -> dict:
    display_color = "FIREBRICK"

    html_description = (
        GroundStationLinkHtmlFormatter(ground_station_link).format_to_html(),
    )

    return create_link_czml(
        link=ground_station_link,
        color=display_color,
        description=html_description,
        properties={},
    )


def create_user_terminal_link_czml(user_terminal_link: UserTerminalLink) -> dict:
    display_color = "DEEPPINK"

    html_description = (
        UserTerminalLinkHtmlFormatter(user_terminal_link).format_to_html(),
    )

    return create_link_czml(
        link=user_terminal_link,
        color=display_color,
        description=html_description,
        properties={},
    )
