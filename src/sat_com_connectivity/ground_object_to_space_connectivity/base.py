from abc import ABC

from sat_com_connectivity.ground_object_to_space_connectivity.models import (
    ComputedGroundObjectConnectionsResult,
)
from sat_com_model.models import GroundObject, Satellite


class GroundToSpaceConnectionStrategy(ABC):

    strategy_name: str = "base_strategy"
    description: str = "Base strategy - should be overridden"

    def __init__(self, **kwargs):
        pass

    def compute_ground_object_connection_strategy(
        self,
        ground_object: "GroundObject",
        satellites: list["Satellite"],
    ) -> ComputedGroundObjectConnectionsResult:
        raise NotImplementedError(
            "compute_ground_object_connection_strategy must be implemented in the subclass"
        )
