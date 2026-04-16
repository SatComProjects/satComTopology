from sat_com_connectivity.ground_object_to_space_connectivity.base import (
    GroundToSpaceConnectionStrategy,
)
from sat_com_connectivity.ground_object_to_space_connectivity.connection_duration_utils import (
    estimate_time_until_disconnection,
)
from sat_com_connectivity.ground_object_to_space_connectivity.models import (
    ComputedGroundObjectConnectionsResult,
    GroundToSpaceConnection,
    GroundToSpaceUpdate,
    GroundToSpaceConstraints,
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
from sat_com_model.models import (
    Satellite,
    GroundObject,
    GroundToSpaceLink,
)
from sat_com_trajectopy.angle_utils import get_elevation_angle
from sat_com_trajectopy.distance_models import SkLearningDistanceModel


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
                ground_to_space_constraints=GroundToSpaceConstraints(
                    distance_km=SkLearningDistanceModel().get_3d_distance_meters(
                        spatial_position_1=ground_object.get_coordinates(),
                        spatial_position_2=best_visible_satellite.satellite.get_coordinates(),
                    ),
                    estimated_connection_time=estimate_time_until_disconnection(
                        ground_object=ground_object,
                        satellite=best_visible_satellite.satellite,
                        tol=0.100,
                    ),
                    elevation_angle_above_horizon=best_visible_satellite.elevation_above_horizon,
                ),
            )
        )

        return computed_ground_object_connections_result


class ConnectToEverythingVisibleStrategy(GroundToSpaceConnectionStrategy):
    strategy_name = "everything-visible"
    description = "Connect to all visible satellites. Do not maintain connectivity, recomputed each timestep."

    def __init__(self, **kwargs):
        super().__init__()
        try:
            self.distance_model = kwargs.get("distance_model", None)
            if self.distance_model is None:
                self.distance_model = SkLearningDistanceModel()
        except KeyError:
            raise ValueError("Missing required parameter: distance_model")

    def compute_ground_object_connection_strategy(
        self,
        ground_object: GroundObject,
        satellites: list[Satellite],
    ):
        computed_ground_object_connections_result = (
            ComputedGroundObjectConnectionsResult()
        )

        visible_satellites = get_visible_satellites(
            satellites=satellites, ground_object=ground_object
        )

        visible_satellite_map = {
            vs.satellite.topology_uniq_id: vs for vs in visible_satellites
        }

        existing_links = [
            link for link in ground_object.links if isinstance(link, GroundToSpaceLink)
        ]

        # Track satellite IDs as we iterate to avoid a second pass through existing_links
        existing_satellite_ids = set()

        for link in existing_links:
            if (
                (satellite := link.get_space_object())
                and satellite.topology_uniq_id in visible_satellite_map
                and isinstance(satellite, Satellite)
            ):
                vs = visible_satellite_map[satellite.topology_uniq_id]
                # Calculate duration once and reuse it
                duration = estimate_time_until_disconnection(
                    ground_object=link.get_ground_object(),
                    satellite=satellite,
                )
                link.estimated_link_duration = duration
                link.elevation_above_horizon_angle = vs.elevation_above_horizon

                computed_ground_object_connections_result.updated_links.append(
                    GroundToSpaceUpdate(
                        ground_to_space_constraints=GroundToSpaceConstraints(
                            distance_km=self.distance_model.get_3d_distance_meters(
                                spatial_position_1=ground_object.get_coordinates(),
                                spatial_position_2=vs.satellite.get_coordinates(),
                            ),
                            elevation_angle_above_horizon=vs.elevation_above_horizon,
                            estimated_connection_time=duration,
                        ),
                        ground_to_space_link=link,
                    )
                )
                # Track satellite ID during first iteration instead of second pass
                existing_satellite_ids.add(satellite.topology_uniq_id)
            else:
                computed_ground_object_connections_result.obsolete_links.append(link)

        for vs in visible_satellites:
            if vs.satellite.topology_uniq_id not in existing_satellite_ids:
                computed_ground_object_connections_result.new_ground_object_connections.append(
                    GroundToSpaceConnection(
                        ground_object=ground_object,
                        satellite=vs.satellite,
                        ground_to_space_constraints=GroundToSpaceConstraints(
                            distance_km=self.distance_model.get_3d_distance_meters(
                                spatial_position_1=ground_object.get_coordinates(),
                                spatial_position_2=vs.satellite.get_coordinates(),
                            ),
                            elevation_angle_above_horizon=vs.elevation_above_horizon,
                            estimated_connection_time=estimate_time_until_disconnection(
                                ground_object=ground_object,
                                satellite=vs.satellite,
                                tol=0.100,
                            ),
                        ),
                    )
                )

        return computed_ground_object_connections_result


class ConnectToEverythingInRangeStrategy(GroundToSpaceConnectionStrategy):
    strategy_name = "everything-in-range"
    description = "Connect to all satellites in range. Do not maintain connectivity, recomputed each timestep."

    def __init__(self, **kwargs):
        super().__init__()
        try:
            self.distance_model = kwargs.get("distance_model", None)
            if self.distance_model is None:
                self.distance_model = SkLearningDistanceModel()
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

        satellites_in_range = self.distance_model.spatial_position_on_ground_in_range(
            reference_point=ground_object,
            target_points=satellites,
            range_in_km=int(
                ground_object.ground_object_domain.maximum_satellite_range_distance
            ),
        )

        satellites_in_range_map = {
            vs.satellite.topology_uniq_id: vs for vs in satellites_in_range
        }

        existing_links = [
            link for link in ground_object.links if isinstance(link, GroundToSpaceLink)
        ]

        # Track satellite IDs as we iterate to avoid a second pass through existing_links
        existing_satellite_ids = set()

        for link in existing_links:
            if (
                (satellite := link.get_space_object())
                and isinstance(satellite, Satellite)
                and satellite.topology_uniq_id in satellites_in_range_map
            ):
                vs = satellites_in_range_map[satellite.topology_uniq_id]
                computed_ground_object_connections_result.updated_links.append(
                    GroundToSpaceUpdate(
                        ground_to_space_constraints=GroundToSpaceConstraints(
                            distance_km=self.distance_model.get_3d_distance_meters(
                                spatial_position_1=ground_object.get_coordinates(),
                                spatial_position_2=vs.satellite.get_coordinates(),
                            ),
                            elevation_angle_above_horizon=get_elevation_angle(
                                sat_coordinates=vs.satellite.get_coordinates().to_latitude_longitude_altitude(),
                                gnd_coordinates=ground_object.get_coordinates().to_latitude_longitude_altitude(),
                            ),
                            estimated_connection_time=estimate_time_until_disconnection(
                                ground_object=ground_object,
                                satellite=vs.satellite,
                            ),
                        ),
                        ground_to_space_link=link,
                    )
                )
                # Track satellite ID during first iteration instead of second pass
                existing_satellite_ids.add(satellite.topology_uniq_id)
            else:
                computed_ground_object_connections_result.obsolete_links.append(link)

        for vs in satellites_in_range:
            if vs.satellite.topology_uniq_id not in existing_satellite_ids:
                computed_ground_object_connections_result.new_ground_object_connections.append(
                    GroundToSpaceConnection(
                        ground_object=ground_object,
                        satellite=vs.satellite,
                        ground_to_space_constraints=GroundToSpaceConstraints(
                            distance_km=self.distance_model.get_3d_distance_meters(
                                spatial_position_1=ground_object.get_coordinates(),
                                spatial_position_2=vs.satellite.get_coordinates(),
                            ),
                            elevation_angle_above_horizon=get_elevation_angle(
                                sat_coordinates=vs.satellite.get_coordinates().to_latitude_longitude_altitude(),
                                gnd_coordinates=ground_object.get_coordinates().to_latitude_longitude_altitude(),
                            ),
                            estimated_connection_time=estimate_time_until_disconnection(
                                ground_object=ground_object,
                                satellite=vs.satellite,
                            ),
                        ),
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
                    ground_to_space_constraints=GroundToSpaceConstraints(
                        distance_km=self.distance_model.get_3d_distance_meters(
                            spatial_position_1=ground_object.get_coordinates().to_latitude_longitude_altitude(),
                            spatial_position_2=ground_object.get_coordinates().to_latitude_longitude_altitude(),
                        )
                        / 1000,
                        elevation_angle_above_horizon=get_elevation_angle(
                            sat_coordinates=closest_satellite.get_coordinates().to_latitude_longitude_altitude(),
                            gnd_coordinates=ground_object.get_coordinates().to_latitude_longitude_altitude(),
                        ),
                        estimated_connection_time=estimate_time_until_disconnection(
                            ground_object=ground_object,
                            satellite=closest_satellite,
                        ),
                    ),
                )
            )
            return computed_ground_object_connections_result
        else:
            raise TypeError(
                f"Expected Satellite, got {type(closest_satellite).__name__}"
            )


class ConnectToTheBestAngleStrategy(GroundToSpaceConnectionStrategy):
    strategy_name = "best-angle"
    description = (
        "Connect to the satellite with the best elevation angle. "
        "Do not maintain connectivity, recomputed each timestep."
    )

    def __init__(self, **kwargs):
        super().__init__()
        self.distance_model = kwargs.get("distance_model", None)

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
                ground_to_space_constraints=GroundToSpaceConstraints(
                    distance_km=(
                        self.distance_model.get_3d_distance_meters(
                            spatial_position_1=ground_object.get_coordinates().to_latitude_longitude_altitude(),
                            spatial_position_2=ground_object.get_coordinates().to_latitude_longitude_altitude(),
                        )
                        / 1000
                        if self.distance_model
                        else None
                    ),
                    elevation_angle_above_horizon=best_visible_satellite.elevation_above_horizon,
                    estimated_connection_time=estimate_time_until_disconnection(
                        ground_object=ground_object,
                        satellite=best_visible_satellite.satellite,
                    ),
                ),
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

    def __init__(self, **kwargs):
        super().__init__()
        self.distance_model = kwargs.get("distance_model", None)

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
                ground_to_space_constraints=GroundToSpaceConstraints(
                    distance_km=(
                        self.distance_model.get_3d_distance_meters(
                            spatial_position_1=ground_object.get_coordinates().to_latitude_longitude_altitude(),
                            spatial_position_2=ground_object.get_coordinates().to_latitude_longitude_altitude(),
                        )
                        / 1000
                        if self.distance_model
                        else None
                    ),
                    elevation_angle_above_horizon=best_visible_satellite_with_best_shell.elevation_above_horizon,
                    estimated_connection_time=estimate_time_until_disconnection(
                        ground_object=ground_object,
                        satellite=best_visible_satellite_with_best_shell.satellite,
                    ),
                ),
            )
        )

        return computed_ground_object_connections_result


class ConnectToBestAngleUntilDisconnectionPreferLowerShellStrategy(
    GroundToSpaceConnectionStrategy
):

    def __init__(self, **kwargs):
        super().__init__()
        self.distance_model = kwargs.get("distance_model", None)

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
                ground_to_space_constraints=GroundToSpaceConstraints(
                    distance_km=(
                        self.distance_model.get_3d_distance_meters(
                            spatial_position_1=ground_object.get_coordinates().to_latitude_longitude_altitude(),
                            spatial_position_2=ground_object.get_coordinates().to_latitude_longitude_altitude(),
                        )
                        / 1000
                        if self.distance_model
                        else None
                    ),
                    elevation_angle_above_horizon=best_visible_satellite_with_lowest_shell.elevation_above_horizon,
                    estimated_connection_time=estimate_time_until_disconnection(
                        ground_object=ground_object,
                        satellite=best_visible_satellite_with_lowest_shell.satellite,
                    ),
                ),
            )
        )

        return computed_ground_object_connections_result
