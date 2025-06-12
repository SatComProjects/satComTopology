from typing import List


from telecom_lib.utils import get_elevation_angle

from sat_com_connectivity.ground_object_connectivity.base import (
    GroundToSpaceConnectionStrategy,
)
from sat_com_connectivity.ground_object_connectivity.models import (
    ComputedGroundObjectConnectionsResult,
)
from sat_com_model.models import Satellite, GroundObject, GroundToSpaceLink
from sat_com_connectivity.ground_object_connectivity.visibility_angle import (
    get_visible_satellites,
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

                elevation_angle = get_elevation_angle(
                    ground_object.spatial_position.to_latitude_longitude_altitude(),
                    link.target.spatial_position.to_latitude_longitude_altitude(),
                )
                elevation_angle_is_still_valid = (
                    elevation_angle
                    >= ground_object.ground_object_domain.elevation_above_horizon
                )
                if elevation_angle_is_still_valid:
                    link.elevation_above_horizon_angle = elevation_angle

                    return computed_ground_object_connections_result
                else:
                    computed_ground_object_connections_result.obsolete_links.append(
                        link
                    )
                    amount_of_ground_space_link -= 1

        visible_satellites = get_visible_satellites(
            satellites=satellites, ground_object=ground_object
        )

        if len(visible_satellites) == 0:
            return computed_ground_object_connections_result

        best_elevation = -1
        best_satellite = None
        for visible_satellite in visible_satellites:
            if visible_satellite.elevation > best_elevation:
                best_elevation = visible_satellite.elevation
                best_satellite = visible_satellite.satellite

        computed_ground_object_connections_result.new_ground_object_connections.append(
            (
                ground_object,
                best_satellite,
                {"elevation_above_horizon": best_elevation},
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
            computed_ground_object_connections_result.to_add_ground_station_connections.append(
                (
                    ground_object,
                    visible_satellite.satellite,
                    {"elevation_above_horizon": visible_satellite.elevation},
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
                (ground_object, visible_satellite.satellite, {})
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

                distance_between_two_object = self.distance_model.get_distance_km(
                    link.source.spatial_position, link.target.spatial_position
                )

                link_is_still_valid = (
                    distance_between_two_object
                    >= ground_object.ground_object_domain.maximum_satellite_range_distance
                )

                if link_is_still_valid:
                    computed_ground_object_connections_result.new_ground_object_connections.append(
                        (ground_object, link.target, {})
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
                (ground_object, closest_satellite, {})
            )
            return computed_ground_object_connections_result
        else:
            raise TypeError(
                f"Expected Satellite, got {type(closest_satellite).__name__}"
            )
