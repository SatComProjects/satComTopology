# sat_com_builder Package
## Description
This package is used the build a simulation based on the sat_com_model.
It features:
- Yaml based configuration file
- Object dictionary based configuration
- ground station generation
- satellite generation
- user terminal generation (but not from a configuration)
- links generation
- movement model parameters

## Example
These examples show how to load a simulation.

### From YAML

```python
from sat_com_builder.configuration_manager import YamlConfigurationManager

yaml_configuration_manager = YamlConfigurationManager("examples/old_configuration_example.yaml")

simulation_manager = yaml_configuration_manager.load_simulation()
```

### From object dictionary or Simulation Property
You can find the example of a SimulationProperty [](examples/multi_shell_configuration_example.json)
Or you can directly initialise a dictionary as long it respects SimulationProperty typing rues.
```python
from sat_com_builder.configuration_manager import BaseConfigurationManager
from sat_com_builder.models import SimulationProperty

object_configuration_manager = BaseConfigurationManager(SimulationProperty())

simulation_manager = object_configuration_manager.load_simulation()
```

### Inter-satellite link options
Two `SimulationProperty` fields select how inter-satellite links are computed:

| Field | Values | Default |
|---|---|---|
| `inter_satellite_link_connection_strategy` | `intra-shell-static-connectivity`, `inter-shell-sso-priority` | `intra-shell-static-connectivity` |
| `optical_inter_satellite_link_model` | `basic`, `advanced` | `basic` |

- `basic`: links follow each shell addressing plan, no optical metric is computed
  and links are never dropped for geometry. Only the distance is computed.
- `advanced`: every link is checked against its optical terminals configuration
  (elevation, azimuth, range, angular velocity, line of sight) and carries its
  optical constraints.

With `inter-shell-sso-priority`, the inter-shell links are always computed with the
optical metrics; the model only applies to the intra-shell links. See
[sat_com_connectivity](../sat_com_connectivity/README.md#inter-satellite-link-connectivity).

```yaml
simulation_property:
  inter_satellite_link_connection_strategy: "inter-shell-sso-priority"
  optical_inter_satellite_link_model: "advanced"
```

### Create an Empty Simulation
```python
from sat_com_builder.configuration_manager import  EmptyConfigurationManager

empty_configuration_manager = EmptyConfigurationManager()

simulation_manager = empty_configuration_manager.load_simulation()
```

## Create your own configuration manager

```python
from sat_com_builder.configuration_manager import BaseConfigurationManager
from sat_com_application.simulation_manager import SimulationManager

class JsonConfigurationManager(BaseConfigurationManager):
    def load_simulation(self) -> SimulationManager:
        """Todo: Implement your code"""
        return SimulationManager(
            
        )

```