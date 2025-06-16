import inspect

from sat_com_connectivity.ground_object_to_space_connectivity import (
    strategies as strategies,
)

from sat_com_connectivity.ground_object_to_space_connectivity.base import (
    GroundToSpaceConnectionStrategy,
)


GROUND_TO_SPACE_CONNECTION_STRATEGY_REGISTRY = {
    cls.strategy_name: cls
    for name, cls in inspect.getmembers(strategies, inspect.isclass)
    if issubclass(cls, GroundToSpaceConnectionStrategy)
    and cls is not GroundToSpaceConnectionStrategy
    and hasattr(cls, "strategy_name")
}


def resolve_strategy(name: str, **kwargs):
    try:
        strategy_cls = GROUND_TO_SPACE_CONNECTION_STRATEGY_REGISTRY[name]
    except KeyError:
        raise ValueError(f"Unknown strategy: {name}")
    return strategy_cls(**kwargs)


def create_strategy(strategy_name: str, **kwargs):
    strategy_cls = GROUND_TO_SPACE_CONNECTION_STRATEGY_REGISTRY.get(strategy_name)
    if not strategy_cls:
        raise ValueError(
            f"Unknown strategy '{strategy_name}'. Available: {list(GROUND_TO_SPACE_CONNECTION_STRATEGY_REGISTRY.keys())}"
        )
    return strategy_cls(**kwargs)


def register_ground_to_space_connectivity_strategy(cls):
    GROUND_TO_SPACE_CONNECTION_STRATEGY_REGISTRY[cls.strategy_name] = cls
    return cls
