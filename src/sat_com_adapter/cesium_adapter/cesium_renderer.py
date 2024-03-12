from sat_com_adapter.cesium_adapter.html_renderer.base import (
    get_full_html,
)
from sat_com_adapter.cesium_adapter.html_renderer.elements import (
    create_satellite_js,
    create_inter_satellite_link_js,
    create_ground_station_link_js,
    create_user_terminal_js,
    create_ground_station_js,
    create_user_terminal_link_js,
)
from sat_com_adapter.cesium_adapter.html_renderer.utils import (
    create_line,
    create_background_color,
)
from sat_com_application.simulation_manager import SimulationManager
from sat_com_model.models import (
    TopologyObject,
    Link,
    InterSatelliteLink,
    GroundStationLink,
    UserTerminalLink,
)


class CesiumRenderer:
    elements_to_display: str = str()

    simulation_manager: SimulationManager

    cesium_token: str

    def __init__(
        self, simulation_manager: SimulationManager, cesium_token: str = str()
    ):
        self.cesium_token = cesium_token
        self.simulation_manager = simulation_manager

    def append_next(self, next_code: str):
        self.elements_to_display += "\n"
        self.elements_to_display += next_code

    def add_satellites(self) -> "CesiumRenderer":
        for satellite in self.simulation_manager.get_satellites():
            self.append_next(create_satellite_js(satellite))
        return self

    def add_inter_satellite_links(self) -> "CesiumRenderer":
        for (
            inter_satellite_link
        ) in self.simulation_manager.get_inter_satellites_links():
            self.append_next(create_inter_satellite_link_js(inter_satellite_link))
        return self

    def add_ground_station_links(self) -> "CesiumRenderer":
        for ground_station_link in self.simulation_manager.get_ground_stations_links():
            self.append_next(create_ground_station_link_js(ground_station_link))
        return self

    def add_user_terminal_links(self) -> "CesiumRenderer":
        for terminal_link in self.simulation_manager.get_user_terminal_links():
            self.append_next(create_user_terminal_link_js(terminal_link))

        return self

    def add_terminal_users(self) -> "CesiumRenderer":
        for terminal_user in self.simulation_manager.get_user_terminals():
            self.append_next(create_user_terminal_js(terminal_user))
        return self

    def add_ground_stations(self) -> "CesiumRenderer":
        for ground_station in self.simulation_manager.get_ground_stations():
            self.append_next(create_ground_station_js(ground_station))

        return self

    def add_topology_objects(self) -> "CesiumRenderer":
        self.add_satellites()
        self.add_ground_stations()
        self.add_terminal_users()

        return self

    def add_links(self) -> "CesiumRenderer":
        self.add_inter_satellite_links()
        self.add_ground_station_links()
        self.add_user_terminal_links()

        return self

    def add_route(
        self, topology_object_a: TopologyObject, topology_object_b: TopologyObject
    ) -> "CesiumRenderer":
        self.append_next(
            create_line(
                topology_object_a.get_coordinates(),
                topology_object_b.get_coordinates(),
                str(topology_object_a.topology_uniq_id),
                str(topology_object_b.topology_uniq_id),
                "PINK",
            )
        )

        return self

    def add_route_from_link(
        self, link: Link, underlined: bool = False
    ) -> "CesiumRenderer":
        source = link.source
        destination = link.destination

        if underlined:
            self.append_next(
                create_line(
                    source.get_coordinates(),
                    destination.get_coordinates(),
                    str(source.topology_uniq_id),
                    str(destination.topology_uniq_id),
                    "RED",
                )
            )

        if isinstance(link, InterSatelliteLink):
            self.append_next(create_inter_satellite_link_js(link))

        if isinstance(link, GroundStationLink):
            self.append_next(create_ground_station_link_js(link))

        if isinstance(link, UserTerminalLink):
            self.append_next(create_user_terminal_link_js(link))

        return self

    def add_white_background_color(self) -> "CesiumRenderer":
        self.append_next(create_background_color())

        return self

    def render(self):
        whole_html = get_full_html(
            cesium_token=self.cesium_token, elements=self.elements_to_display
        )

        return whole_html
