import copy

import pytest
import yaml
from pydantic import ValidationError

from sat_com_builder.configuration_manager import YamlConfigurationManager
from sat_com_builder.models import GroundObjectProperty
from tests.sat_com_builder_tests.test_yaml_configuration_manager import (
    MINIMAL_YAML_CONFIG,
)

INLINE_GROUND_OBJECTS = [
    {"id": 10, "label": "Paris", "latitude": 48.85, "longitude": 2.35, "altitude": 0.0},
    {
        "id": 11,
        "label": "Toulouse",
        "latitude": 43.60,
        "longitude": 1.44,
        "altitude": 0.1,
    },
]


def _load(tmp_path, ground_objects_properties):
    config = copy.deepcopy(MINIMAL_YAML_CONFIG)
    config["ground_objects_properties"] = ground_objects_properties
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(config))
    return YamlConfigurationManager(str(config_path)).load_simulation()


def _ground_object_property(kind, **source):
    return {
        "identifier": f"{kind}_domain",
        "type": kind,
        "connectivity_properties": {
            "ground_to_space_connections_strategy": "best-angle-until-disconnection"
        },
        **source,
    }


@pytest.mark.parametrize(
    "kind, getter",
    [
        ("ground_station", "get_ground_stations"),
        ("user_terminal", "get_user_terminals"),
        ("point_of_presence", "get_point_of_presences"),
    ],
)
def test_inline_ground_objects_are_loaded(tmp_path, kind, getter):
    simulation_manager = _load(
        tmp_path,
        [_ground_object_property(kind, ground_objects=INLINE_GROUND_OBJECTS)],
    )

    ground_objects = getattr(simulation_manager, getter)()

    assert [g.object_id for g in ground_objects] == [10, 11]
    assert ground_objects[0].label == "Paris"
    assert ground_objects[0].domain == f"{kind}_domain"
    assert ground_objects[1].get_coordinates().to_longitude_latitude_altitude() == (
        1.44,
        43.60,
        0.1,
    )


def test_file_and_inline_ground_objects_are_merged(tmp_path):
    data_file = tmp_path / "ground_stations.txt"
    data_file.write_text("0,Madrid,40.42,-3.70,0.6\n")

    simulation_manager = _load(
        tmp_path,
        [
            _ground_object_property(
                "ground_station",
                data_file=str(data_file),
                ground_objects=INLINE_GROUND_OBJECTS,
            )
        ],
    )

    labels = [gs.label for gs in simulation_manager.get_ground_stations()]
    assert labels == ["Madrid", "Paris", "Toulouse"]


def test_ground_object_property_requires_a_source():
    with pytest.raises(ValidationError, match="data_file"):
        GroundObjectProperty(**_ground_object_property("ground_station"))
