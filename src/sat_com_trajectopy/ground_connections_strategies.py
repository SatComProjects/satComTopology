from typing import List, Dict

from pydantic import BaseModel, Field
from telecom_lib.utils import get_elevation_angle

from sat_com_application.simulation_manager import SimulationManager
from sat_com_model.models import (
    Satellite,
    GroundObject,
    TopologyObject,
    UserTerminal,
    GroundStation,
    Link,
    GroundStationLink,
    UserTerminalLink,
)


def get_visible_ground_object(
    satellites: List[Satellite], ground_objects: List[GroundObject]
) -> dict[Satellite, list[tuple[GroundObject, float]]]:
    visible = {}
    for satellite in satellites:
        visible[satellite] = []
        for ground_object in ground_objects:
            elev = get_elevation_angle(
                satellite.get_coordinates().to_latitude_longitude_altitude(),
                ground_object.get_coordinates().to_latitude_longitude_altitude(),
            )
            if elev >= ground_object.ground_object_domain.elevation_above_horizon:
                visible[satellite].append((ground_object, elev))
    return visible


class LinkSortResponse(BaseModel):
    ground_object: TopologyObject = Field(default=None)
    link: Link = Field(default=None)
    is_valid: bool = Field(default=None)


def sort_link_by_validity(links: List[UserTerminalLink | GroundStationLink]):
    link_sort_responses = []

    for link in links:
        satellite = (
            link.source if isinstance(link.source, Satellite) else link.destination
        )
        ground_object = (
            link.destination if isinstance(link.source, Satellite) else link.source
        )

        elevation_angle = get_elevation_angle(
            satellite.get_coordinates().to_latitude_longitude_altitude(),
            ground_object.get_coordinates().to_latitude_longitude_altitude(),
        )
        link.elevation_above_horizon_angle = elevation_angle
        response = LinkSortResponse(
            ground_object=ground_object,
            is_valid=elevation_angle >= 15,
            link=link,
        )
        link_sort_responses.append(response)

    return link_sort_responses


def remove_obsolete_user_terminal_link_and_get_orphan_user_terminal(
    simulation_manager: SimulationManager,
):
    responses = sort_link_by_validity(simulation_manager.get_user_terminal_links())

    user_terminals_that_need_new_satellite = (
        simulation_manager.get_user_terminals().copy()
    )

    for response in responses:
        if not response.is_valid:
            simulation_manager.remove_inter_satellite_link(response.link)
        else:
            if response.ground_object in user_terminals_that_need_new_satellite:
                user_terminals_that_need_new_satellite.remove(response.ground_object)

    return user_terminals_that_need_new_satellite


def get_best_elevation_angle_satellite_for_each_user_terminal(
    visible_ground_objects: Dict[Satellite, (UserTerminal, float)],
):
    best_elevation_angle_satellite_for_each_user_terminal: Dict[
        UserTerminal, (Satellite, float)
    ] = {}

    for satellite, ground_objects in visible_ground_objects.items():
        for ground_object, elevation in ground_objects:
            if isinstance(ground_object, UserTerminal):
                if (
                    ground_object
                    not in best_elevation_angle_satellite_for_each_user_terminal
                ):
                    best_elevation_angle_satellite_for_each_user_terminal[
                        ground_object
                    ] = (
                        satellite,
                        elevation,
                    )
                else:
                    if (
                        elevation
                        > best_elevation_angle_satellite_for_each_user_terminal[
                            ground_object
                        ][1]
                    ):
                        best_elevation_angle_satellite_for_each_user_terminal[
                            ground_object
                        ] = (
                            satellite,
                            elevation,
                        )
    return best_elevation_angle_satellite_for_each_user_terminal


class GroundToSpaceConnectionStrategy(BaseModel):
    def connect_ground_stations(self, simulation_manager: SimulationManager):
        """
        Connect ground stations to satellites based on your defined strategy.
        """
        raise NotImplementedError("This method should be implemented by subclasses.")

    def connect_user_terminals(self, simulation_manager: SimulationManager):
        """
        Connect user terminals to satellites based on your defined strategy.
        """
        raise NotImplementedError("This method should be implemented by subclasses.")


class LineOfSightStrategy(GroundToSpaceConnectionStrategy):
    def connect_ground_stations(self, simulation_manager: SimulationManager):
        simulation_manager.simulation.ground_station_links.clear()
        ground_stations = simulation_manager.get_ground_stations()
        satellites = simulation_manager.get_satellites()

        visible_ground_objects = get_visible_ground_object(
            satellites=satellites, ground_objects=ground_stations
        )

        for satellite, visible_ground_objects in visible_ground_objects.items():
            for ground_object, elevation_above_horizon in visible_ground_objects:
                if isinstance(ground_object, GroundStation):
                    simulation_manager.create_and_add_ground_station_link_connection(
                        satellite, ground_object
                    )

    def connect_user_terminals(self, simulation_manager: SimulationManager):
        user_terminals_that_need_new_satellite = (
            remove_obsolete_user_terminal_link_and_get_orphan_user_terminal(
                simulation_manager
            )
        )
        satellites = simulation_manager.get_satellites()

        visible_ground_objects = get_visible_ground_object(
            satellites=satellites,
            ground_objects=user_terminals_that_need_new_satellite,
        )

        best_elevation_angle_satellite_for_each_user_terminal = (
            get_best_elevation_angle_satellite_for_each_user_terminal(
                visible_ground_objects
            )
        )

        for (
            ground_object,
            satellite_and_elevation,
        ) in best_elevation_angle_satellite_for_each_user_terminal.items():
            simulation_manager.create_and_add_user_terminal_link_connection(
                satellite_and_elevation[0], ground_object
            )


class SimpleConnectionStrategy(GroundToSpaceConnectionStrategy):
    def connect_ground_stations(self, simulation_manager: SimulationManager):
        """
        Connect ground stations to satellites based on a simple connection strategy.
        """
        simulation_manager.simulation.user_terminal_links.clear()
        for user_terminal in simulation_manager.get_user_terminals():
            simulation_domain = simulation_manager.get_ground_object_domain(
                user_terminal.domain
            )

            simulation_manager.connect_user_terminal_to_satellites(
                user_terminal, simulation_domain.maximum_satellite_range_distance
            )

    def connect_user_terminals(self, simulation_manager: SimulationManager):
        """
        Connect user terminals to satellites based on a simple connection strategy.
        """
        simulation_manager.simulation.ground_station_links.clear()

        for ground_station in simulation_manager.get_ground_stations():
            simulation_domain = simulation_manager.get_ground_object_domain(
                ground_station.domain
            )

            simulation_manager.connect_ground_station_to_satellites(
                ground_station, simulation_domain.maximum_satellite_range_distance
            )


ground_connections_strategies_dict = {
    "simple": SimpleConnectionStrategy,
    "line-of-sight": LineOfSightStrategy,
}
ground_connections_strategies = ground_connections_strategies_dict.keys()
