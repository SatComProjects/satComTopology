from sat_com_connectivity.ground_object_to_space_connectivity.base import (
    GroundToSpaceConnectionStrategy,
)
from sat_com_connectivity.ground_object_to_space_connectivity.ground_connection_strategy_registry import (
    GROUND_TO_SPACE_CONNECTION_STRATEGY_REGISTRY,
    register_ground_to_space_connectivity_strategy,
    resolve_strategy,
)

strategy_name = "dummy-test-strategy"


def test_register_ground_to_space_connectivity_strategy_and_resolve():
    GROUND_TO_SPACE_CONNECTION_STRATEGY_REGISTRY.pop(strategy_name, None)

    @register_ground_to_space_connectivity_strategy
    class DummyTestStrategy(GroundToSpaceConnectionStrategy):
        strategy_name = strategy_name

        def compute_ground_object_connection_strategy(self, ground_object, satellites):
            pass  # irrelevant for this test

    # Ensure the strategy is in the registry
    assert strategy_name in GROUND_TO_SPACE_CONNECTION_STRATEGY_REGISTRY
    assert (
        GROUND_TO_SPACE_CONNECTION_STRATEGY_REGISTRY[strategy_name] is DummyTestStrategy
    )

    # Try resolving it
    resolved = resolve_strategy(strategy_name)
    assert isinstance(resolved, DummyTestStrategy)

    # Clean up to avoid polluting global registry (optional)
    GROUND_TO_SPACE_CONNECTION_STRATEGY_REGISTRY.pop(strategy_name, None)
