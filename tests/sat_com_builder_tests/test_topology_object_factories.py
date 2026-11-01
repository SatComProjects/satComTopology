import copy
import warnings

import yaml

from sat_com_builder.configuration_manager import YamlConfigurationManager
from sat_com_builder.factories import (
    DefaultGroundStationFactory,
    DefaultPointOfPresenceFactory,
    DefaultSatelliteFactory,
    DefaultUserTerminalFactory,
    TopologyObjectFactories,
)
from sat_com_model.factories import (
    AbstractGroundStationFactory,
    AbstractPointOfPresenceFactory,
    AbstractSatelliteFactory,
    AbstractUserTerminalFactory,
)
from sat_com_model.models import (
    GroundStation,
    PointOfPresence,
    Satellite,
    UserTerminal,
)
from tests.sat_com_builder_tests.test_yaml_configuration_manager import (
    MINIMAL_YAML_CONFIG,
)


# User defined subclasses, with an extra field each.
class MySatellite(Satellite):
    payload: str = "default"


class MyGroundStation(GroundStation):
    antenna_count: int = 1


class MyUserTerminal(UserTerminal):
    subscription: str = "basic"


class MyPointOfPresence(PointOfPresence):
    peering: bool = False


class MySatelliteFactory(AbstractSatelliteFactory):
    def create_satellite(
        self, satellite_name, object_id, shell, movement_model, domain="public"
    ):
        return MySatellite(
            satellite_name=satellite_name,
            object_id=object_id,
            shell=shell,
            movement_model=movement_model,
            domain=domain,
            payload="camera",
        )


class MyGroundStationFactory(AbstractGroundStationFactory):
    def create_ground_station(
        self,
        object_id,
        label="unknown",
        longitude=0.0,
        latitude=0.0,
        altitude=0.0,
        ground_object_domain=None,
    ):
        ground_station = MyGroundStation(object_id=object_id, antenna_count=4)
        return self._configure_ground_object(
            ground_station, label, longitude, latitude, altitude, ground_object_domain
        )


class MyUserTerminalFactory(AbstractUserTerminalFactory):
    def create_user_terminal(
        self,
        object_id,
        label="unknown",
        longitude=0.0,
        latitude=0.0,
        altitude=0.0,
        ground_object_domain=None,
    ):
        user_terminal = MyUserTerminal(object_id=object_id, subscription="premium")
        return self._configure_ground_object(
            user_terminal, label, longitude, latitude, altitude, ground_object_domain
        )


class MyPointOfPresenceFactory(AbstractPointOfPresenceFactory):
    def create_point_of_presence(
        self,
        object_id,
        label="unknown",
        longitude=0.0,
        latitude=0.0,
        altitude=0.0,
        ground_object_domain=None,
    ):
        point_of_presence = MyPointOfPresence(object_id=object_id, peering=True)
        return self._configure_ground_object(
            point_of_presence,
            label,
            longitude,
            latitude,
            altitude,
            ground_object_domain,
        )


def _write_config(tmp_path):
    data_file = tmp_path / "ground_objects.txt"
    data_file.write_text("0,Paris,48.85,2.35,0.0\n1,Toulouse,43.60,1.44,0.1\n")

    config = copy.deepcopy(MINIMAL_YAML_CONFIG)
    config["ground_objects_properties"] = [
        {
            "identifier": f"{kind}_domain",
            "type": kind,
            "data_file": str(data_file),
            "connectivity_properties": {
                "ground_to_space_connections_strategy": "best-angle-until-disconnection"
            },
        }
        for kind in ("ground_station", "user_terminal", "point_of_presence")
    ]
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(config))
    return str(config_path)


def test_default_factories_are_used_when_nothing_is_injected():
    factories = TopologyObjectFactories()

    assert isinstance(factories.satellite_factory, DefaultSatelliteFactory)
    assert isinstance(factories.ground_station_factory, DefaultGroundStationFactory)
    assert isinstance(factories.user_terminal_factory, DefaultUserTerminalFactory)
    assert isinstance(
        factories.point_of_presence_factory, DefaultPointOfPresenceFactory
    )


def test_default_ground_station_factory_sets_every_field():
    ground_station = DefaultGroundStationFactory().create_ground_station(
        object_id=7, label="Paris", longitude=2.35, latitude=48.85, altitude=0.1
    )

    assert type(ground_station) is GroundStation
    assert ground_station.object_id == 7
    assert ground_station.label == "Paris"
    assert ground_station.domain == "public"
    assert ground_station.get_coordinates().to_longitude_latitude_altitude() == (
        2.35,
        48.85,
        0.1,
    )


def test_default_load_does_not_use_deprecated_factories(tmp_path):
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        simulation_manager = YamlConfigurationManager(
            _write_config(tmp_path)
        ).load_simulation()

    assert type(simulation_manager.get_satellites()[0]) is Satellite
    assert type(simulation_manager.get_ground_stations()[0]) is GroundStation


def test_injected_factories_build_user_subclasses(tmp_path):
    factories = TopologyObjectFactories(
        satellite_factory=MySatelliteFactory(),
        ground_station_factory=MyGroundStationFactory(),
        user_terminal_factory=MyUserTerminalFactory(),
        point_of_presence_factory=MyPointOfPresenceFactory(),
    )

    simulation_manager = YamlConfigurationManager(
        _write_config(tmp_path), topology_object_factories=factories
    ).load_simulation()

    satellites = simulation_manager.get_satellites()
    ground_stations = simulation_manager.get_ground_stations()
    user_terminals = simulation_manager.get_user_terminals()
    point_of_presences = simulation_manager.get_point_of_presences()

    assert len(satellites) == 9
    assert all(isinstance(s, MySatellite) and s.payload == "camera" for s in satellites)

    assert len(ground_stations) == 2
    assert all(gs.antenna_count == 4 for gs in ground_stations)
    assert ground_stations[0].label == "Paris"
    assert ground_stations[0].ground_object_domain.identifier == "ground_station_domain"

    assert len(user_terminals) == 2
    assert all(ut.subscription == "premium" for ut in user_terminals)

    assert len(point_of_presences) == 2
    assert all(pop.peering for pop in point_of_presences)
