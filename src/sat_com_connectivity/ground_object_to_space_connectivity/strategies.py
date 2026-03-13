from datetime import datetime

import numpy as np

from sat_com_connectivity.ground_object_to_space_connectivity.base import (
    GroundToSpaceConnectionStrategy,
)
from sat_com_connectivity.ground_object_to_space_connectivity.connection_duration_utils import (
    estimate_time_until_disconnection,
)
from sat_com_connectivity.ground_object_to_space_connectivity.models import (
    ComputedGroundObjectConnectionsResult,
    GroundToSpaceConnection,
)
from sat_com_connectivity.ground_object_to_space_connectivity.range_distance_utils import (
    check_and_update_distance_if_satellite_is_in_range,
)
from sat_com_connectivity.ground_object_to_space_connectivity.utils import (
    get_best_visible_satellite_with_biggest_shell,
    get_best_visible_satellite_with_lowest_shell,
)
from sat_com_connectivity.ground_object_to_space_connectivity.visibility_angle_utils import (
    get_visible_satellites,
    check_and_update_elevation_if_satellite_is_visible,
    get_best_satellites_among_visible_satellites,
)
from sat_com_model.models import Satellite, GroundObject, GroundToSpaceLink


class ConnectToBestAngleUntilDisconnectionStrategy(GroundToSpaceConnectionStrategy):

    strategy_name = "best-angle-until-disconnection"
    description = "Connect to the satellite with the best elevation angle. Maintain the connection until the satellite is no longer visible."

    def compute_ground_object_connection_strategy(
        self,
        ground_object: GroundObject,
        satellites: list[Satellite],
    ) -> ComputedGroundObjectConnectionsResult:

        computed_ground_object_connections_result = (
            ComputedGroundObjectConnectionsResult()
        )
        # Check existing links (loop through existing links if there are multiple links)

        amount_of_ground_space_link = 0

        self.valid_links = []

        for link in ground_object.links:
            if isinstance(link, GroundToSpaceLink):
                amount_of_ground_space_link += 1

                if check_and_update_elevation_if_satellite_is_visible(
                    link=link,
                ):
                    self.valid_links.append(link)
                else:
                    computed_ground_object_connections_result.obsolete_links.append(
                        link
                    )
                    amount_of_ground_space_link -= 1

        good_satellite_is_still_visible = amount_of_ground_space_link == 1

        if good_satellite_is_still_visible:
            return computed_ground_object_connections_result

        strategy_has_been_changed = amount_of_ground_space_link > 1

        if strategy_has_been_changed:
            computed_ground_object_connections_result.obsolete_links.extend(
                self.valid_links
            )
            self.valid_links.clear()

        best_visible_satellite = get_best_satellites_among_visible_satellites(
            ground_object, satellites
        )

        if best_visible_satellite is None:
            return computed_ground_object_connections_result

        computed_ground_object_connections_result.new_ground_object_connections.append(
            GroundToSpaceConnection(
                ground_object=ground_object,
                satellite=best_visible_satellite.satellite,
                connection_info={
                    "elevation_above_horizon": best_visible_satellite.elevation_above_horizon,
                    "estimated_link_duration": estimate_time_until_disconnection(
                        ground_object=ground_object,
                        satellite=best_visible_satellite.satellite,
                        minimum_elevation=ground_object.ground_object_domain.elevation_above_horizon,
                        tol=0.100,
                    ),
                },
            )
        )

        return computed_ground_object_connections_result


class ConnectToEverythingVisibleStrategy(GroundToSpaceConnectionStrategy):
    strategy_name = "everything-visible"
    description = "Connect to all visible satellites. Do not maintain connectivity, recomputed each timestep."

    def compute_ground_object_connection_strategy(
        self,
        ground_object: GroundObject,
        satellites: list[Satellite],
    ):
        computed_ground_object_connections_result = (
            ComputedGroundObjectConnectionsResult()
        )

        # Remove all existing links, we will compute them all anyway
        computed_ground_object_connections_result.obsolete_links.extend(
            [
                link
                for link in ground_object.links
                if isinstance(link, GroundToSpaceLink)
            ]
        )

        visible_satellites = get_visible_satellites(
            satellites=satellites, ground_object=ground_object
        )

        for visible_satellite in visible_satellites:
            computed_ground_object_connections_result.new_ground_object_connections.append(
                GroundToSpaceConnection(
                    ground_object=ground_object,
                    satellite=visible_satellite.satellite,
                    connection_info={
                        "elevation_above_horizon": visible_satellite.elevation_above_horizon,
                        "estimated_link_duration": estimate_time_until_disconnection(
                            ground_object=ground_object,
                            satellite=visible_satellite.satellite,
                            minimum_elevation=ground_object.ground_object_domain.elevation_above_horizon,
                            tol=0.100,
                        ),
                    },
                )
            )

        return computed_ground_object_connections_result


class ConnectToEverythingInRangeStrategy(GroundToSpaceConnectionStrategy):
    strategy_name = "everything-in-range"
    description = "Connect to all satellites in range. Do not maintain connectivity, recomputed each timestep."

    def __init__(self, **kwargs):
        super().__init__()
        try:
            self.distance_model = kwargs["distance_model"]
        except KeyError:
            raise ValueError("Missing required parameter: distance_model")

    def compute_ground_object_connection_strategy(
        self,
        ground_object: GroundObject,
        satellites: list[Satellite],
    ) -> ComputedGroundObjectConnectionsResult:
        computed_ground_object_connections_result = (
            ComputedGroundObjectConnectionsResult()
        )

        # Remove all existing links, we will compute them all anyway
        computed_ground_object_connections_result.obsolete_links.extend(
            [
                link
                for link in ground_object.links
                if isinstance(link, GroundToSpaceLink)
            ]
        )

        visible_satellites = self.distance_model.spatial_position_on_ground_in_range(
            reference_point=ground_object,
            target_points=satellites,
            range_in_km=int(
                ground_object.ground_object_domain.maximum_satellite_range_distance
            ),
        )

        for visible_satellite in visible_satellites:
            computed_ground_object_connections_result.new_ground_object_connections.append(
                GroundToSpaceConnection(
                    ground_object=ground_object,
                    satellite=visible_satellite.satellite,
                    connection_info={},
                )
            )

        return computed_ground_object_connections_result


class ConnectToBestRangeUntilDisconnectionStrategy(GroundToSpaceConnectionStrategy):
    strategy_name = "best-range-until-disconnection"
    description = "Connect to the closest satellite. Maintain the connection until the satellite is no longer in range."

    def __init__(self, **kwargs):
        super().__init__()
        try:
            self.distance_model = kwargs["distance_model"]
        except KeyError:
            raise ValueError("Missing required parameter: distance_model")

    def compute_ground_object_connection_strategy(
        self,
        ground_object: GroundObject,
        satellites: list[Satellite],
    ) -> ComputedGroundObjectConnectionsResult:
        """
        :param ground_object:
        :param satellites:
        :return:
        """

        computed_ground_object_connections_result = (
            ComputedGroundObjectConnectionsResult()
        )

        # Check existing links (loop through existing links if there are multiple links)
        amount_of_ground_space_link = 0

        self.valid_links = []

        for link in ground_object.links:
            if isinstance(link, GroundToSpaceLink):
                amount_of_ground_space_link += 1

                if check_and_update_distance_if_satellite_is_in_range(
                    link=link,
                    distance_model=self.distance_model,
                ):
                    self.valid_links.append(link)

                else:
                    computed_ground_object_connections_result.obsolete_links.append(
                        link
                    )
                    amount_of_ground_space_link -= 1

        good_satellite_is_still_visible = amount_of_ground_space_link == 1

        if good_satellite_is_still_visible:
            return computed_ground_object_connections_result

        too_many_ground_space_links_which_mean_that_strategy_may_have_been_changed = (
            amount_of_ground_space_link > 1
        )

        if too_many_ground_space_links_which_mean_that_strategy_may_have_been_changed:
            # Too many ground space links, we remove them all and recompute
            computed_ground_object_connections_result.obsolete_links.extend(
                self.valid_links
            )
            self.valid_links.clear()

        visible_satellites = self.distance_model.spatial_position_on_ground_in_range(
            reference_point=ground_object,
            target_points=satellites,
        )

        if len(visible_satellites) == 0:
            return computed_ground_object_connections_result

        closest_satellites = self.distance_model.k_closest(
            ground_object, visible_satellites, k=1
        )

        closest_satellite = closest_satellites[0]

        if isinstance(closest_satellite, Satellite):
            computed_ground_object_connections_result.new_ground_object_connections.append(
                GroundToSpaceConnection(
                    ground_object=ground_object,
                    satellite=closest_satellite,
                    connection_info={},
                )
            )
            return computed_ground_object_connections_result
        else:
            raise TypeError(
                f"Expected Satellite, got {type(closest_satellite).__name__}"
            )


class ConnectToTheBestAngleStrategy(GroundToSpaceConnectionStrategy):
    strategy_name = "best-angle"
    description = "Connect to the satellite with the best elevation angle. Do not maintain connectivity, recomputed each timestep."

    def compute_ground_object_connection_strategy(
        self,
        ground_object: GroundObject,
        satellites: list[Satellite],
    ) -> ComputedGroundObjectConnectionsResult:

        computed_ground_object_connections_result = (
            ComputedGroundObjectConnectionsResult()
        )

        # Remove all existing links, we will compute them all anyway
        computed_ground_object_connections_result.obsolete_links.extend(
            [
                link
                for link in ground_object.links
                if isinstance(link, GroundToSpaceLink)
            ]
        )

        best_visible_satellite = get_best_satellites_among_visible_satellites(
            ground_object, satellites
        )

        if best_visible_satellite is None:
            return computed_ground_object_connections_result

        computed_ground_object_connections_result.new_ground_object_connections.append(
            GroundToSpaceConnection(
                ground_object=ground_object,
                satellite=best_visible_satellite.satellite,
                connection_info={
                    "elevation_above_horizon": best_visible_satellite.elevation_above_horizon
                },
            )
        )

        return computed_ground_object_connections_result


class ConnectToBestAngleUntilDisconnectionPreferBiggerShellStrategy(
    GroundToSpaceConnectionStrategy
):
    strategy_name = "best-angle-until-disconnection-prefer-bigger-shell"
    description = (
        "Connect to the satellite with the best elevation angle, preferring satellites in larger shells."
        "Maintain the connection until the satellite is no longer visible."
    )

    def compute_ground_object_connection_strategy(
        self, ground_object: GroundObject, satellites: list[Satellite]
    ):
        """
                amount_of_orbit_plane: int
        amount_of_satellite_per_orbit_plane: int
            :param ground_object:
            :param satellites:
            :return:
        """

        computed_ground_object_connections_result = (
            ComputedGroundObjectConnectionsResult()
        )
        # Check existing links (loop through existing links if there are multiple links)

        amount_of_ground_space_link = 0

        self.valid_links = []

        for link in ground_object.links:
            if isinstance(link, GroundToSpaceLink):
                amount_of_ground_space_link += 1

                if check_and_update_elevation_if_satellite_is_visible(
                    link=link,
                ):
                    self.valid_links.append(link)
                else:
                    computed_ground_object_connections_result.obsolete_links.append(
                        link
                    )
                    amount_of_ground_space_link -= 1

        good_satellite_is_still_visible = amount_of_ground_space_link == 1

        if good_satellite_is_still_visible:
            return computed_ground_object_connections_result

        strategy_has_been_changed = amount_of_ground_space_link > 1

        if strategy_has_been_changed:
            computed_ground_object_connections_result.obsolete_links.extend(
                self.valid_links
            )
            self.valid_links.clear()

        visible_satellites = get_visible_satellites(
            satellites=satellites, ground_object=ground_object
        )
        best_visible_satellite_with_best_shell = (
            get_best_visible_satellite_with_biggest_shell(visible_satellites)
        )

        if not best_visible_satellite_with_best_shell:
            return computed_ground_object_connections_result

        computed_ground_object_connections_result.new_ground_object_connections.append(
            GroundToSpaceConnection(
                ground_object=ground_object,
                satellite=best_visible_satellite_with_best_shell.satellite,
                connection_info={
                    "elevation_above_horizon": best_visible_satellite_with_best_shell.elevation_above_horizon
                },
            )
        )

        return computed_ground_object_connections_result


class ConnectToBestAngleUntilDisconnectionPreferLowerShellStrategy(
    GroundToSpaceConnectionStrategy
):
    strategy_name = "best-angle-until-disconnection-prefer-lower-shell"

    description = (
        "Connect to the satellite with the best elevation angle, preferring satellites in lower shells."
        "Maintain the connection until the satellite is no longer visible."
    )

    def compute_ground_object_connection_strategy(
        self, ground_object: GroundObject, satellites: list[Satellite]
    ):
        """Same as the function above but call get_best_visible_satellite_with_lowest_shell"""

        computed_ground_object_connections_result = (
            ComputedGroundObjectConnectionsResult()
        )
        # Check existing links (loop through existing links if there are multiple links)

        amount_of_ground_space_link = 0

        self.valid_links = []

        for link in ground_object.links:
            if isinstance(link, GroundToSpaceLink):
                amount_of_ground_space_link += 1

                if check_and_update_elevation_if_satellite_is_visible(
                    link=link,
                ):
                    self.valid_links.append(link)
                else:
                    computed_ground_object_connections_result.obsolete_links.append(
                        link
                    )
                    amount_of_ground_space_link -= 1

        good_satellite_is_still_visible = amount_of_ground_space_link == 1

        if good_satellite_is_still_visible:
            return computed_ground_object_connections_result

        strategy_has_been_changed = amount_of_ground_space_link > 1

        if strategy_has_been_changed:
            computed_ground_object_connections_result.obsolete_links.extend(
                self.valid_links
            )
            self.valid_links.clear()

        visible_satellites = get_visible_satellites(
            satellites=satellites, ground_object=ground_object
        )
        best_visible_satellite_with_lowest_shell = (
            get_best_visible_satellite_with_lowest_shell(visible_satellites)
        )

        if not best_visible_satellite_with_lowest_shell:
            return computed_ground_object_connections_result

        computed_ground_object_connections_result.new_ground_object_connections.append(
            GroundToSpaceConnection(
                ground_object=ground_object,
                satellite=best_visible_satellite_with_lowest_shell.satellite,
                connection_info={
                    "elevation_above_horizon": best_visible_satellite_with_lowest_shell.elevation_above_horizon
                },
            )
        )

        return computed_ground_object_connections_result


class LongestConnectionTimeStrategy(GroundToSpaceConnectionStrategy):
    """
    Connection strategy that connects ground objects to the furthest away satellites that are getting closer.
    It sorts the visible satellites by their elevation above horizon and then checks which of them is getting closer to the ground object.
    If a satellite is getting closer, it is added to the list of considered satellites. The strategy then connects the ground object to the best considered satellite.
    If no satellites are getting closer, it connects the ground object to the best visible satellite.
    If the ground object already has a connection to a satellite, it will keep that connection as long as it is still visible.
    Minimizes number of handover
    """

    strategy_name = "longest-connection-time-strategy"

    def compute_ground_object_connection_strategy(
        self,
        ground_object: GroundObject,
        satellites: list[Satellite],
    ):

        maximum_number_of_links = (
            ground_object.ground_object_domain.maximum_connected_satellites
        )

        computed_ground_object_connections_result = (
            ComputedGroundObjectConnectionsResult()
        )

        # Remove all existing links, we will compute them all anyway
        computed_ground_object_connections_result.obsolete_links.extend(
            [
                link
                for link in ground_object.links
                if isinstance(link, GroundToSpaceLink)
            ]
        )

        visible_satellites = get_visible_satellites(
            satellites=satellites, ground_object=ground_object
        )

        # There is a linear relationship between distance and elevation so lets sort by elevation
        visible_satellites.sort(key=lambda x: x.elevation_above_horizon, reverse=True)

        ############## First check: Keep existing connections if they are still valid ##############

        for visible_satellite in visible_satellites:

            if (
                visible_satellite.satellite
                in [
                    link.source
                    for link in ground_object.links
                    if isinstance(
                        link, GroundToSpaceLink
                    )  # This checks if satellite is already connected
                ]
                and len(
                    computed_ground_object_connections_result.new_ground_object_connections
                )
                < maximum_number_of_links
            ):  # This checks if the maximum number of links is not exceeded
                new_link = GroundToSpaceConnection(
                    ground_object=ground_object,
                    satellite=visible_satellite.satellite,
                    connection_info={
                        "elevation_above_horizon": visible_satellite.elevation_above_horizon
                    },
                )

                # Keep the connection if it already exists
                computed_ground_object_connections_result.new_ground_object_connections.append(
                    new_link
                )

        if (
            len(computed_ground_object_connections_result.new_ground_object_connections)
            >= maximum_number_of_links
        ):
            # If we already have enough connections, we can stop here

            return computed_ground_object_connections_result

        list_of_satellites = []
        for visible_satellite in visible_satellites:
            time_until_disconnection = self.estimate_time_until_disconnection(
                ground_object=ground_object,
                satellite=visible_satellite.satellite,
                minimum_elevation=ground_object.ground_object_domain.elevation_above_horizon,
            )

            list_of_satellites.append((visible_satellite, time_until_disconnection))

        # Sort the visible satellites by time until disconnection
        list_of_satellites.sort(key=lambda x: x[1], reverse=True)

        for visible_satellite, time_until_disconnection in list_of_satellites:
            if (
                len(
                    computed_ground_object_connections_result.new_ground_object_connections
                )
                >= maximum_number_of_links
            ):
                # If we already have enough connections, we can stop here
                break
            new_link = GroundToSpaceConnection(
                ground_object=ground_object,
                satellite=visible_satellite.satellite,
                connection_info={
                    "elevation_above_horizon": visible_satellite.elevation_above_horizon
                },
            )
            computed_ground_object_connections_result.new_ground_object_connections.append(
                new_link
            )

        return computed_ground_object_connections_result
