import json
from pathlib import Path

import pytest

from sat_com_builder.models import OrbitalConnectivityProperty, SimulationProperty

EXAMPLES = Path(__file__).parents[2] / "src" / "sat_com_builder" / "examples"


@pytest.mark.parametrize(
    "file_name",
    [
        "single_shell_configuration_example.json",
        "multi_shell_configuration_example.json",
    ],
)
def test_json_example_is_a_valid_configuration(file_name):
    configuration = json.loads((EXAMPLES / file_name).read_text())

    simulation_property = SimulationProperty(**configuration)

    assert simulation_property.walker_shells


def test_removed_static_ground_station_link_mode_is_ignored_with_a_warning():
    with pytest.warns(FutureWarning, match="static_ground_station_link_mode"):
        simulation_property = SimulationProperty(static_ground_station_link_mode=True)

    assert not hasattr(simulation_property, "static_ground_station_link_mode")


@pytest.mark.parametrize(
    "parameter",
    [
        "maximum_inter_satellite_count",
        "maximum_inter_satellite_range_distance",
        "maximum_ground_station_range",
        "maximum_user_terminal_range",
    ],
)
def test_unused_orbital_parameter_is_ignored_with_a_warning(parameter):
    with pytest.warns(
        FutureWarning, match=f"Parameter `{parameter}` .* was never used"
    ):
        orbital_property = OrbitalConnectivityProperty(
            adjacent_inter_satellite_shifting=1, **{parameter: 1000}
        )

    assert orbital_property.adjacent_inter_satellite_shifting == 1
    assert parameter not in orbital_property.model_dump()
