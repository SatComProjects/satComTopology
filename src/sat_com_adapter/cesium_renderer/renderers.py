from typing import Any

from sat_com_adapter.cesium_renderer.factories import (
    get_full_html,
    create_background_color,
)
from sat_com_adapter.cesium_renderer.formats import (
    CesiumFormat,
    CesiumJavaScriptFormat,
    CesiumCZMLFormat,
)
from sat_com_adapter.cesium_renderer.html_formatter.html_formatters import HtmlFormatter
from sat_com_adapter.cesium_renderer.models import CesiumProperty
from sat_com_application.simulation_manager import SimulationManager
from sat_com_model.models import (
    Link,
    InterSatelliteLink,
    GroundStationLink,
    UserTerminalLink,
    Satellite,
    GroundObjectLink,
)


class CesiumRenderer:
    elements_to_display: []

    simulation_manager: SimulationManager

    cesium_renderer_property: CesiumProperty

    cesium_token: str

    cesium_format: CesiumFormat

    def __init__(
        self,
        simulation_manager: SimulationManager,
        cesium_renderer_property: CesiumProperty = None,
    ):
        if cesium_renderer_property is None:
            cesium_renderer_property = CesiumProperty()

        self.cesium_token = cesium_renderer_property.cesium_token

        self.cesium_renderer_property = cesium_renderer_property
        self.simulation_manager = simulation_manager
        self.elements_to_display = []

    def append_next(self, next_element: any) -> "CesiumRenderer":
        """
        Append new code to the Cesium Html file.
        :param next_element: Code to append to the Cesium, should be escaped
        :return: current instance of CesiumRenderer
        """

        self.elements_to_display.append(next_element)

        return self

    def add_specified_satellites(self, satellites: list[Satellite]) -> "CesiumRenderer":
        """
        Add satellites given in parameters to the Cesium Render.
        :param satellites: List of satellites to display
        :return: current instance of CesiumRenderer
        """
        for satellite in satellites:
            self.append_next(self.cesium_format.create_satellite(satellite))
        return self

    def add_satellites(self) -> "CesiumRenderer":
        """
        Add satellites to the Render.
        :return: current instance of CesiumRenderer
        """
        satellites_to_display = self.simulation_manager.get_satellites()
        return self.add_specified_satellites(satellites_to_display)

    def add_only_ascending_satellites(self) -> "CesiumRenderer":
        """
        Add only ascending satellites to the Render.
        :return: current instance of CesiumRenderer
        """
        satellites_to_display = self.simulation_manager.get_ascending_satellites()
        return self.add_specified_satellites(satellites_to_display)

    def add_only_descending_satellites(self) -> "CesiumRenderer":
        """
        Add only descending satellites to the Render.
        :return:
        """
        satellites_to_display = self.simulation_manager.get_descending_satellites()
        return self.add_specified_satellites(satellites_to_display)

    def add_inter_satellite_links(self) -> "CesiumRenderer":
        """
        Add inter satellite links to the Render.
        :return:  current instance of CesiumRenderer
        """

        for (
            inter_satellite_link
        ) in self.simulation_manager.get_inter_satellites_links():
            self.append_next(
                self.cesium_format.create_inter_satellite_link(inter_satellite_link)
            )
        return self

    def add_ground_station_links(self) -> "CesiumRenderer":
        """
        Add ground station links to the render.
        :return:  current instance of CesiumRenderer
        """

        for ground_station_link in list(
            filter(
                lambda ground_station_link_object: not ground_station_link_object.disabled,
                self.simulation_manager.get_ground_stations_links(),
            )
        ):
            self.append_next(
                self.cesium_format.create_ground_station_link(ground_station_link)
            )
        return self

    def add_user_terminal_links(self) -> "CesiumRenderer":
        """
        Add user terminal links to the render.
        :return:  current instance of CesiumRenderer
        """
        for terminal_link in self.simulation_manager.get_user_terminal_links():
            self.append_next(
                self.cesium_format.create_user_terminal_link(terminal_link)
            )

        return self

    def add_terminal_users(self) -> "CesiumRenderer":
        """
        Add terminal users to the render.
        :return:  current instance of CesiumRenderer
        """
        for terminal_user in self.simulation_manager.get_user_terminals():
            self.append_next(self.cesium_format.create_user_terminal(terminal_user))
        return self

    def add_ground_stations(self) -> "CesiumRenderer":
        """
        Add ground stations to the render.
        :return:  current instance of CesiumRenderer
        """
        for ground_station in self.simulation_manager.get_ground_stations():
            self.append_next(self.cesium_format.create_ground_station(ground_station))

        return self

    def add_topology_objects(self) -> "CesiumRenderer":
        """
        Add every topology objects to the render.
        :return:  current instance of CesiumRenderer
        """
        self.add_satellites()
        self.add_ground_stations()
        self.add_terminal_users()

        return self

    def add_links(self) -> "CesiumRenderer":
        """
        Add every link to the render.
        :return:  current instance of CesiumRenderer
        """
        self.add_inter_satellite_links()
        self.add_ground_station_links()
        self.add_user_terminal_links()

        return self

    def add_route_from_link(
        self, link: Link, underlined: bool = False, color: str = "RED"
    ) -> "CesiumRenderer":
        """
        Underline a link based on the link given in parameter
        :param link: Link instance to display
        :param color:  Underlined color of the link
        :param underlined: if true, a new color will be set for the link. If not the link will keep its native color
        :return: current instance of CesiumRenderer
        """

        if underlined:
            return self.append_next(
                self.cesium_format.create_link(
                    link=link,
                    color=color,
                    width=3.0,
                    description=HtmlFormatter(link).format(),
                    properties={},
                    on_ground=False,
                )
            )

        if isinstance(link, InterSatelliteLink):
            self.append_next(self.cesium_format.create_inter_satellite_link(link))

        if isinstance(link, GroundStationLink):
            self.append_next(self.cesium_format.create_ground_station_link(link))

        if isinstance(link, UserTerminalLink):
            self.append_next(self.cesium_format.create_user_terminal_link(link))

        if isinstance(link, GroundObjectLink):
            self.append_next(self.cesium_format.create_static_ground_objects_link(link))

        return self

    def add_all_routes_from_links(self, links: list[Link]) -> "CesiumRenderer":
        """
        Add all routes from a list of link.
        :param links: list of links
        :return: current instance of CesiumRenderer
        """
        for link in links:
            self.add_route_from_link(link)

        return self

    def add_white_background_color(self) -> "CesiumRenderer":
        """
        Set the background color to white. Only supported for JavaScript export.
        :return:
        """
        if isinstance(self.cesium_format, CesiumJavaScriptFormat):
            return self.append_next(create_background_color())

        return self

    def add_inter_satellites_flows(self) -> "CesiumRenderer":
        link_capacities = [
            link.total_capacity_between_hops_bidirectional()
            for link in self.simulation_manager.get_inter_satellites_links()
        ]
        maximum_busy_inter_satellite_link = max(link_capacities)

        for (
            inter_satellite_link
        ) in self.simulation_manager.get_inter_satellites_links():

            self.append_next(
                self.cesium_format.create_inter_satellite_link_flow(
                    inter_satellite_link, maximum_busy_inter_satellite_link
                )
            )
        return self

    def add_flows(self) -> "CesiumRenderer":
        """
        Add network traffic to the render. This will render independent traffic without links.
        :return:
        """

    def render(self):
        """
        Create the final render
        :return:
        """
        pass


class CesiumHtmlRenderer(CesiumRenderer):

    def __init__(
        self,
        simulation_manager: SimulationManager,
        cesium_renderer_property: CesiumProperty = None,
    ):
        if cesium_renderer_property is None:
            cesium_renderer_property = CesiumProperty()

        super().__init__(simulation_manager, cesium_renderer_property)
        self.cesium_format = CesiumJavaScriptFormat(cesium_renderer_property)

    def render(self) -> str:
        html_code = get_full_html(
            self.cesium_token, "\n".join(self.elements_to_display)
        )
        return html_code


class CesiumCZMLRenderer(CesiumRenderer):

    def render(self) -> list[Any]:
        return self.elements_to_display

    def __init__(
        self,
        simulation_manager: SimulationManager,
        cesium_renderer_property: CesiumProperty = None,
    ):
        if cesium_renderer_property is None:
            cesium_renderer_property = CesiumProperty()

        super().__init__(simulation_manager, cesium_renderer_property)
        self.cesium_format = CesiumCZMLFormat(cesium_renderer_property)
