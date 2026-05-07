from sat_com_connectivity.ground_object_to_space_connectivity.base import (
    GroundToSpaceConnectionStrategy,
)
from sat_com_connectivity.ground_object_to_space_connectivity.models import (
    ComputedGroundObjectConnectionsResult,
)
from sat_com_model.models import GroundObject, Satellite


class FakeGroundToSpaceConnectionStrategy(GroundToSpaceConnectionStrategy):
    def compute_ground_object_connection_strategy(
        self,
        ground_object: GroundObject,
        satellites: list[Satellite],
    ) -> ComputedGroundObjectConnectionsResult:
        """
        Fake implementation of the compute_ground_object_connection_strategy method.
        This method is used to test the base configuration manager without actual connectivity logic.

        :param ground_object: The ground object for which connections are computed.
        :param satellites: List of satellites to connect to.

        :return: ComputedGroundObjectConnectionsResult with empty lists.
        """
        return ComputedGroundObjectConnectionsResult(
            new_ground_object_connections=[], obsolete_links=[]
        )
