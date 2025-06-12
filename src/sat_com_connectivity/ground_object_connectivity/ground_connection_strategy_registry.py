import inspect

from sat_com_connectivity.ground_object_connectivity import strategies as strategies

from sat_com_connectivity.ground_object_connectivity.base import (
    GroundToSpaceConnectionStrategy,
)


ground_to_space_connection_strategies_dict = {
    cls.strategy_name: cls
    for name, cls in inspect.getmembers(strategies, inspect.isclass)
    if issubclass(cls, GroundToSpaceConnectionStrategy)
    and cls is not GroundToSpaceConnectionStrategy
    and hasattr(cls, "strategy_name")
}


def resolve_strategy(name: str, **kwargs):
    try:
        strategy_cls = ground_to_space_connection_strategies_dict[name]
    except KeyError:
        raise ValueError(f"Unknown strategy: {name}")
    return strategy_cls(**kwargs)


def create_strategy(strategy_name: str, **kwargs):
    strategy_cls = ground_to_space_connection_strategies_dict.get(strategy_name)
    if not strategy_cls:
        raise ValueError(
            f"Unknown strategy '{strategy_name}'. Available: {list(ground_to_space_connection_strategies_dict.keys())}"
        )
    return strategy_cls(**kwargs)
