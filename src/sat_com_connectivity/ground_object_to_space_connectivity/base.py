from __future__ import annotations

import warnings
from abc import ABC
from typing import TYPE_CHECKING

from sat_com_connectivity.ground_object_to_space_connectivity.models import (
    ComputedGroundObjectConnectionsResult,
)
from sat_com_model.models import GroundObject, Satellite

if TYPE_CHECKING:
    from sat_com_connectivity.satellite_state_cache import SatelliteStateCache


class GroundToSpaceConnectionStrategy(ABC):

    strategy_name: str = "base_strategy"
    description: str = "Base strategy - should be overridden"

    """
    Simulation-wide satellite state cache (see satellite_state_cache.py).
    Set by the SimulationManager, so every ground object reuses the satellite
    positions computed for the current time step. None: no caching.
    """
    state_cache: SatelliteStateCache | None = None

    """
    Set on obsolete strategies: why, and what to use instead. A FutureWarning
    is emitted the first time the strategy is used.
    """
    deprecation_message: str | None = None

    """
    True when the strategy decides visibility from the elevation angle: the
    SimulationManager then estimates the duration of its new links (time until
    the satellite drops below the minimum elevation).
    """
    estimates_link_duration: bool = True
    _deprecation_warning_emitted: bool = False

    def __init__(self, **kwargs):
        """`distance_model`: the simulation distance model, if the strategy needs one."""
        self.distance_model = kwargs.get("distance_model")

    def _warn_if_deprecated(self) -> None:
        if self.deprecation_message is None or self._deprecation_warning_emitted:
            return
        self._deprecation_warning_emitted = True
        warnings.warn(
            f"Ground-to-space connection strategy '{self.strategy_name}' is "
            f"deprecated: {self.deprecation_message}",
            FutureWarning,
            stacklevel=3,
        )

    def compute_ground_object_connection_strategy(
        self,
        ground_object: "GroundObject",
        satellites: list["Satellite"],
    ) -> ComputedGroundObjectConnectionsResult:
        raise NotImplementedError(
            "compute_ground_object_connection_strategy must be implemented in the subclass"
        )
