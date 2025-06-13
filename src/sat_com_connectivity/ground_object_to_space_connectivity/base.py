from abc import ABC
from typing import Dict, List

from sat_com_connectivity.ground_object_to_space_connectivity.models import (
    ComputedGroundObjectConnectionsResult,
)
from sat_com_model.models import GroundObject, Satellite, GroundToSpaceLink


class GroundToSpaceConnectionStrategy(ABC):

    def __init__(self, **kwargs):
        pass

    def compute_ground_object_connection_strategy(
        self,
        ground_object: "GroundObject",
        satellites: List["Satellite"],
    ) -> ComputedGroundObjectConnectionsResult:
        raise NotImplementedError(
            "compute_ground_object_connection_strategy must be implemented in the subclass"
        )
