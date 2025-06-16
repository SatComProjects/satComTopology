from typing import List

from sat_com_connectivity.ground_object_to_space_connectivity.base import (
    GroundToSpaceConnectionStrategy,
)
from sat_com_connectivity.ground_object_to_space_connectivity.models import (
    ComputedGroundObjectConnectionsResult,
    GroundToSpaceConnection,
)
from sat_com_connectivity.ground_object_to_space_connectivity.range_distance_utils import (
    check_and_update_distance_if_satellite_is_in_range,
)
from sat_com_model.models import Satellite, GroundObject, GroundToSpaceLink
from sat_com_connectivity.ground_object_to_space_connectivity.visibility_angle_utils import (
    get_visible_satellites,
    check_and_update_elevation_if_satellite_is_visible,
    get_best_satellites_among_visible_satellites,
)


class ConnectToBestAngleUntilDisconnectionStrategy(GroundToSpaceConnectionStrategy):

    strategy_name = "best-angle-until-disconnection"

    def compute_ground_object_connection_strategy(
        self,
        ground_object: GroundObject,
        satellites: List[Satellite],
    ) -> ComputedGroundObjectConnectionsResult:

        computed_ground_object_connections_result = (
            ComputedGroundObjectConnectionsResult()
        )
        # Check existing links (loop through existing links if there are multiple links)

        amount_of_ground_space_link = 0
        for link in ground_object.links:
            if isinstance(link, GroundToSpaceLink):
                amount_of_ground_space_link += 1

                if check_and_update_elevation_if_satellite_is_visible(
                    link=link,
                ):
                    return computed_ground_object_connections_result
                else:
                    computed_ground_object_connections_result.obsolete_links.append(
                        link
                    )
                    amount_of_ground_space_link -= 1

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


class ConnectToEverythingVisibleStrategy(GroundToSpaceConnectionStrategy):
    strategy_name = "everything-visible"

    def compute_ground_object_connection_strategy(
        self,
        ground_object: GroundObject,
        satellites: List[Satellite],
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
                        "elevation_above_horizon": visible_satellite.elevation_above_horizon
                    },
                )
            )

        return computed_ground_object_connections_result


class ConnectToEverythingInRangeStrategy(GroundToSpaceConnectionStrategy):
    strategy_name = "everything-in-range"

    def __init__(self, **kwargs):
        super().__init__()
        try:
            self.distance_model = kwargs["distance_model"]
        except KeyError:
            raise ValueError("Missing required parameter: distance_model")

    def compute_ground_object_connection_strategy(
        self,
        ground_object: GroundObject,
        satellites: List[Satellite],
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

        visible_satellites = self.distance_model.spatial_position_in_range(
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

    def __init__(self, **kwargs):
        super().__init__()
        try:
            self.distance_model = kwargs["distance_model"]
        except KeyError:
            raise ValueError("Missing required parameter: distance_model")

    def compute_ground_object_connection_strategy(
        self,
        ground_object: GroundObject,
        satellites: List[Satellite],
    ) -> ComputedGroundObjectConnectionsResult:

        computed_ground_object_connections_result = (
            ComputedGroundObjectConnectionsResult()
        )

        # Check existing links (loop through existing links if there are multiple links)
        amount_of_ground_space_link = 0
        for link in ground_object.links:
            if isinstance(link, GroundToSpaceLink):
                amount_of_ground_space_link += 1

                if check_and_update_distance_if_satellite_is_in_range(
                    link=link,
                    distance_model=self.distance_model,
                ):
                    computed_ground_object_connections_result.new_ground_object_connections.append(
                        GroundToSpaceConnection(
                            ground_object=ground_object,
                            satellite=(
                                link.destination
                                if isinstance(link.destination, Satellite)
                                else link.source
                            ),
                            connection_info={},
                        )
                    )
                    return computed_ground_object_connections_result

                else:
                    computed_ground_object_connections_result.obsolete_links.append(
                        link
                    )
                    amount_of_ground_space_link -= 1

        if amount_of_ground_space_link > 0:
            return computed_ground_object_connections_result

        visible_satellites = self.distance_model.spatial_position_in_range(
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
