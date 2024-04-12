from sat_com_adapter.cesium_renderer.html_formatter.html_formatters import (
    SatelliteHtmlFormatter,
    InterSatelliteLinkHtmlFormatter,
    GroundStationLinkHtmlFormatter,
    GroundStationHtmlFormatter,
    UserTerminalHtmlFormatter,
    UserTerminalLinkHtmlFormatter,
)
from sat_com_adapter.cesium_renderer.html_renderer.utils import (
    create_sphere,
    create_line,
)
from sat_com_model.models import (
    InterSatelliteLink,
    GroundStationLink,
    GroundStation,
    UserTerminal,
    UserTerminalLink,
    Satellite,
    InterSatelliteLinkDirection,
)


def create_satellite_js(satellite: Satellite) -> str:
    display_color = "LIGHTSTEELBLUE" if satellite.is_ascending() else "KHAKI"

    satellite_js = create_sphere(
        str(satellite.satellite_name),
        satellite.get_coordinates(),
        "topology_object_" + str(satellite.get_topology_uniq_id()),
        display_color,
        30000,
        SatelliteHtmlFormatter(satellite).format_to_html(),
    )

    return satellite_js


def create_inter_satellite_link_js(inter_satellite_link: InterSatelliteLink) -> str:
    display_color = (
        "YELLOWGREEN"
        if inter_satellite_link.inter_satellite_direction
        == InterSatelliteLinkDirection.ORBITAL
        else "PERU"
    )
    link_js = create_line(
        inter_satellite_link.source.get_coordinates(),
        inter_satellite_link.destination.get_coordinates(),
        "link_"
        + str(inter_satellite_link.source.topology_uniq_id)
        + "_"
        + str(inter_satellite_link.destination.topology_uniq_id),
        str(inter_satellite_link.source.topology_uniq_id),
        str(inter_satellite_link.destination.topology_uniq_id),
        display_color,
        InterSatelliteLinkHtmlFormatter(inter_satellite_link).format_to_html(),
        {
            "source": inter_satellite_link.source.topology_uniq_id,
            "destination": inter_satellite_link.destination.topology_uniq_id,
        },
    )

    return link_js


def create_ground_station_link_js(ground_station_link: GroundStationLink) -> str:
    link_js = create_line(
        ground_station_link.source.get_coordinates(),
        ground_station_link.destination.get_coordinates(),
        "link_"
        + str(ground_station_link.source.topology_uniq_id)
        + "_"
        + str(ground_station_link.destination.topology_uniq_id),
        str(ground_station_link.source.topology_uniq_id),
        str(ground_station_link.destination.topology_uniq_id),
        "FIREBRICK",
        GroundStationLinkHtmlFormatter(ground_station_link).format_to_html(),
        {
            "source": ground_station_link.source.topology_uniq_id,
            "destination": ground_station_link.destination.topology_uniq_id,
        },
    )

    return link_js


def create_ground_station_js(ground_station: GroundStation) -> str:
    ground_station_js = create_sphere(
        str(ground_station.get_topology_uniq_id())
        + " "
        + str(ground_station.object_id),
        ground_station.get_coordinates(),
        "topology_object_" + str(ground_station.get_topology_uniq_id()),
        "ORCHID",
        5000,
        GroundStationHtmlFormatter(ground_station).format_to_html(),
    )

    return ground_station_js


def create_user_terminal_js(user_terminal: UserTerminal) -> str:
    terminal_user_js = create_sphere(
        str(user_terminal.get_topology_uniq_id()) + " " + str(user_terminal.object_id),
        user_terminal.get_coordinates(),
        "topology_object_" + str(user_terminal.get_topology_uniq_id()),
        "INDIANRED",
        5000,
        UserTerminalHtmlFormatter(user_terminal).format_to_html(),
    )

    return terminal_user_js


def create_user_terminal_link_js(user_terminal_link: UserTerminalLink) -> str:
    link_js = create_line(
        user_terminal_link.source.get_coordinates(),
        user_terminal_link.destination.get_coordinates(),
        "link_"
        + str(user_terminal_link.source.topology_uniq_id)
        + "_"
        + str(user_terminal_link.destination.topology_uniq_id),
        str(user_terminal_link.source.topology_uniq_id),
        str(user_terminal_link.destination.topology_uniq_id),
        "DEEPPINK",
        UserTerminalLinkHtmlFormatter(user_terminal_link).format_to_html(),
        {
            "source": user_terminal_link.source.topology_uniq_id,
            "destination": user_terminal_link.destination.topology_uniq_id,
        },
    )

    return link_js


def create_socket_connection(socket_server_address_with_port: str):
    js_code = str()
    js_code += f'const socket = new WebSocket("{socket_server_address_with_port}");\n'
    js_code += 'socket.addEventListener("open", function (event) { socket.send("Established new connection!");});;\n'
    return js_code
