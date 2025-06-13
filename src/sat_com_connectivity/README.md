# sat_com_connectivity Package
This package is used to manage the connectivity of the simulation.
It features:
- Ground Object To space Connectivity management

Todo:
- Satellite Object Connectivity management
- Ground to ground connectivity management

## Ground Object To Space Connectivity
This package is used to manage the connectivity of the simulation between ground objects and space objects.
It implements strategies, used by a ground object to establish a connection with a space object.
We base our limits on the ground side.

### GroundToSpaceConnectivityStrategy

To implement a new GroundToSpaceConnectivityStrategy, you must implement the `compute_connectivity` method.
It has the following signature:
```python
    def compute_ground_object_connection_strategy(
        self,
        ground_object: "GroundObject",
        satellites: List["Satellite"],
    ) -> ComputedGroundObjectConnectionsResult:
        raise NotImplementedError(
            "compute_ground_object_connection_strategy must be implemented in the subclass"
        )
```

This class does not modify the simulation, it only compute the connectivity. and returns the result.
```python
class ComputedGroundObjectConnectionsResult(BaseModel):
    new_ground_object_connections: List[GroundToSpaceConnection] = Field(
        default_factory=list
    )
    obsolete_links: List[GroundToSpaceLink] = Field(default_factory=list)

```
Then, when the simulation manager calls the strategy, it will use the result of the computation to modify the simulation. Breaking this rule
will end up in circular dependencies and potential bugs.

### Registry (new)
We use a registry to register the strategies. This allows us to easily add new strategies without modifying the code.
Registry is automatically checked by the sat_com_builder package when loading a simulation.
You can manually register a strategy by using the `register_ground_to_space_connectivity_strategy` decorator or manually
register it using the dictionary `GROUND_TO_SPACE_CONNECTIVITY_STRATEGIES`.
```python
from sat_com_connectivity import register_ground_to_space_connectivity_strategy

@register_ground_to_space_connectivity_strategy
class DummyTestStrategy(GroundToSpaceConnectionStrategy):
    strategy_name = "dummy_test_strategy"

    def compute_ground_object_connection_strategy(self, ground_object, satellites):
        pass  # your implementation here
```

