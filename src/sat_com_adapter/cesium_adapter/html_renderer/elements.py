from sat_com_adapter.cesium_adapter.html_renderer.utils import create_point, create_line
from sat_com_model.models import (
    InterSatelliteLink,
    GroundStationLink,
    GroundStation,
    UserTerminal,
    UserTerminalLink,
    Satellite,
)


def create_satellite_js(satellite: Satellite) -> str:
    satellite_js = create_point(
        str(satellite.get_topology_uniq_id()) + " " + str(satellite.object_id),
        satellite.get_coordinates(),
    )

    return satellite_js


def create_inter_satellite_link_js(inter_satellite_link: InterSatelliteLink) -> str:
    link_js = create_line(
        inter_satellite_link.source.get_coordinates(),
        inter_satellite_link.destination.get_coordinates(),
        str(inter_satellite_link.source.topology_uniq_id),
        str(inter_satellite_link.destination.topology_uniq_id),
    )

    return link_js


def create_ground_station_link_js(ground_station_link: GroundStationLink) -> str:
    link_js = create_line(
        ground_station_link.source.get_coordinates(),
        ground_station_link.destination.get_coordinates(),
        str(ground_station_link.source.topology_uniq_id),
        str(ground_station_link.destination.topology_uniq_id),
        "RED",
    )

    return link_js


def create_ground_station_js(ground_station: GroundStation) -> str:
    ground_station_js = create_point(
        str(ground_station.get_topology_uniq_id())
        + " "
        + str(ground_station.object_id),
        ground_station.get_coordinates(),
        "YELLOW",
    )

    return ground_station_js


def create_user_terminal_js(user_terminal: UserTerminal) -> str:
    terminal_user_js = create_point(
        str(user_terminal.get_topology_uniq_id()) + " " + str(user_terminal.object_id),
        user_terminal.get_coordinates(),
        "ORANGE",
    )

    return terminal_user_js


def create_user_terminal_link_js(user_terminal_link: UserTerminalLink) -> str:
    link_js = create_line(
        user_terminal_link.source.get_coordinates(),
        user_terminal_link.destination.get_coordinates(),
        str(user_terminal_link.source.topology_uniq_id),
        str(user_terminal_link.destination.topology_uniq_id),
        "BLUE",
    )

    return link_js
