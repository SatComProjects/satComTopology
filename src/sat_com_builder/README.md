from sat_com_application.simulation_manager import SimulationManager

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

yaml_configuration_manager = YamlConfigurationManager("examples/configuration_example.yaml")

simulation_manager = yaml_configuration_manager.load_simulation()
```

### From object dictionary
from sat_com_builder.configuration_manager import YamlConfigurationManager
```python
from sat_com_builder.configuration_manager import ObjectBaseConfigurationManager

object_configuration_manager = ObjectBaseConfigurationManager(
    {
        "simulation_name": "Example",
        "constellation_file": "link_to_constellation",
        ...
    }
)

simulation_manager = object_configuration_manager.load_simulation()
```

### Create an Empty Simulation
```python
from sat_com_builder.configuration_manager import  EmptyConfigurationManager

empty_configuration_manager = EmptyConfigurationManager()

simulation_manager = empty_configuration_manager.load_simulation()
```

## Create your own configuration manager
```python
from  sat_com_builder.configuration_manager import  ConfigurationManager

class JsonConfigurationManager(ConfigurationManager):
    def load_simulation(self) -> SimulationManager:
         """Todo: Implement your code"""
         return SimulationManager()

```