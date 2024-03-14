from sat_com_model.models import (
    Satellite,
    TopologyObject,
    Link,
    InterSatelliteLink,
    GroundStation,
    UserTerminal,
    GroundStationLink,
    UserTerminalLink,
)


class HtmlFormatter:
    """
    Html formatter
    """

    def format_to_html(self) -> str:
        pass


class TopologyObjectFormatter(HtmlFormatter):
    """
    Tool that format any sat_com_topology_object in Html.
    useful for the Cesium infobox.
    """

    topology_object: TopologyObject

    def __init__(self, topology_object: TopologyObject):
        self.topology_object = topology_object

    def format_to_html(self) -> str:
        coordinates = self.topology_object.get_coordinates()
        html = (
            (
                f"<h2>Object information</h2><br>"
                + f"{self.topology_object.get_type()} id:  {self.topology_object.object_id}<br>"
                + f"Topology object id:  {self.topology_object.topology_uniq_id}<br>"
            )
            + f"<h2>Position</h2><br>longitude: {coordinates.longitude}<br>latitude: {coordinates.latitude}<br>altitude: {coordinates.altitude} km<br>"
        )
        return html


class SatelliteHtmlFormatter(TopologyObjectFormatter):
    """
    Tool that format any satellite object in Html.
    useful for the Cesium infobox.
    """

    satellite: Satellite

    def __init__(self, satellite: Satellite):
        super().__init__(satellite)
        self.satellite = satellite

    def format_to_html(self) -> str:
        ascending_string = (
            "ascending" if self.satellite.is_ascending() else "descending"
        )
        html = super().format_to_html()
        html += "<h2>Satellite information</h2><br>"
        html += f"Orbital phase: {ascending_string}<br>"

        return html


class GroundStationHtmlFormatter(TopologyObjectFormatter):
    """
    Tool that format any ground_station in Html.
    useful for the Cesium infobox.
    """

    ground_station: GroundStation

    def __init__(self, ground_station: GroundStation):
        super().__init__(ground_station)
        self.ground_station = ground_station

    def format_to_html(self) -> str:
        html = super().format_to_html()
        html += "<h2>Ground Station Information</h2><br>"
        html += f"City: {self.ground_station.city}<br>"

        return html


class UserTerminalHtmlFormatter(TopologyObjectFormatter):
    """
    Tool that format any user terminal in Html.
    useful for the Cesium infobox.
    """

    user_terminal: UserTerminal

    def __init__(self, user_terminal: UserTerminal):
        super().__init__(user_terminal)
        self.user_terminal = user_terminal

    def format_to_html(self) -> str:
        html = super().format_to_html()
        html += "<h2>User Terminal Information</h2><br>"
        html += f"Username: {self.user_terminal.user_name}<br>"

        return html


class LinkHtmlFormatter(HtmlFormatter):
    """
    Tool that format any link in Html.
    useful for the Cesium infobox.
    """

    link: Link

    def __init__(self, link: Link):
        self.link = link

    def format_to_html(self) -> str:
        source = self.link.source
        destination = self.link.destination
        html = f"<h2>Link information</h2><br>"
        html += f"Source*: {source.topology_uniq_id}<br> Destination*: {destination.object_id}<br>"
        html += f"Link type: {self.link.type}<br>"
        html += f"<h2>Boundaries Information</h2><br>"
        html += f"Source: {source.type} {source.object_id} <br>"
        html += f"Destination: {destination.type} {destination.object_id} <br>"
        html += f"<b>* Source and destination are not relevant, the links are bidirectional</b><br>"

        return html


class InterSatelliteLinkHtmlFormatter(LinkHtmlFormatter):
    """
    Tool that format any Inter Satellite Link in Html.
    useful for the Cesium infobox.
    """

    inter_satellite_link: InterSatelliteLink

    def __init__(self, inter_satellite_link: InterSatelliteLink):
        super().__init__(inter_satellite_link)
        self.inter_satellite_link = inter_satellite_link

    def format_to_html(self) -> str:
        html = super().format_to_html()
        html += "<h2> Inter Satellite link Information</h2><br>"
        html += f"ISL direction: {self.inter_satellite_link.inter_satellite_direction.name}<br>"

        return html


class GroundStationLinkHtmlFormatter(LinkHtmlFormatter):
    """
    Tool that format any Ground Station Link in Html.
    useful for the Cesium infobox.
    """

    ground_station_link: GroundStationLink

    def __init__(self, ground_station_link: GroundStationLink):
        super().__init__(ground_station_link)
        self.ground_station_link = ground_station_link

    def format_to_html(self) -> str:
        html = super().format_to_html()
        return html


class UserTerminalLinkHtmlFormatter(LinkHtmlFormatter):
    """
    Tool that format any User Terminal Link in Html.
    useful for the Cesium infobox.
    """

    user_terminal_link: UserTerminalLink

    def __init__(self, user_terminal_link: UserTerminalLink):
        super().__init__(user_terminal_link)
        self.user_terminal_link = user_terminal_link

    def format_to_html(self) -> str:
        html = super().format_to_html()
        return html
