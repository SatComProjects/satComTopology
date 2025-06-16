import pytest
from joblib.testing import fixture

from sat_com_model.exceptions import (
    GroundStationConnectionError,
    InterSatelliteConnectionError,
    UserTerminalConnectionError,
    ConnectionBetweenSameSatelliteForbiddenError,
    GroundObjectLinkConnectionError,
)
from sat_com_model.models import (
    GroundStation,
    Satellite,
    GroundStationLink,
    UserTerminal,
    InterSatelliteLink,
    UserTerminalLink,
    Link,
    TopologyObject,
    PointOfPresence,
    GroundObjectLink,
)


def assert_can_establish_connection(
    link: Link,
    object_source: TopologyObject,
    object_destination: TopologyObject,
):
    link.connect(object_source, object_destination)
    assert link.source == object_source and link.destination == object_destination


def assert_cant_establish_connection(
    link: Link,
    expected_type_exception,
    object_source: TopologyObject,
    object_destination: TopologyObject,
):
    with pytest.raises(expected_type_exception):
        link.connect(object_source, object_destination)

    assert link.source is None and link.destination is None


@pytest.fixture
def satellite() -> Satellite:
    satellite = Satellite(object_id=0, satellite_name="Test Satellite")
    satellite.topology_uniq_id = 105
    return satellite


@pytest.fixture
def ground_station() -> GroundStation:
    groud_station = GroundStation()
    groud_station.topology_uniq_id = 0
    return groud_station


@pytest.fixture
def user_terminal() -> UserTerminal:
    user_terminal = UserTerminal()
    user_terminal.topology_uniq_id = 1
    return user_terminal


@pytest.fixture
def gsl_link() -> GroundStationLink:
    groud_statio_link = GroundStationLink()
    return groud_statio_link


@pytest.fixture
def isl_link() -> InterSatelliteLink:
    isl_link = InterSatelliteLink()
    return isl_link


@pytest.fixture
def user_link() -> UserTerminalLink:
    user_terminal_link = UserTerminalLink()
    return user_terminal_link


@fixture
def point_of_presence() -> PointOfPresence:
    point_of_presence = PointOfPresence()
    point_of_presence.topology_uniq_id = 5
    return point_of_presence


@fixture
def point_of_presence_2() -> PointOfPresence:
    point_of_presence = PointOfPresence()
    point_of_presence.topology_uniq_id = 6
    return point_of_presence


@pytest.fixture
def static_ground_object_link_1() -> GroundObjectLink:
    static_ground_object_link_1 = GroundObjectLink()
    return static_ground_object_link_1


@pytest.fixture
def ground_station_2() -> GroundStation:
    ground_station = GroundStation()
    ground_station.topology_uniq_id = 8
    return ground_station


@pytest.fixture
def satellite_2() -> Satellite:
    satellite = Satellite(object_id=0, satellite_name="Test Satellite 2")
    satellite.topology_uniq_id = 9
    return satellite


class TestLinks:
    def test_cant_establish_connection_between_same_object(self):
        single_topology_object = TopologyObject()
        single_topology_object.topology_uniq_id = 0
        link = Link()
        assert_cant_establish_connection(
            link,
            ConnectionBetweenSameSatelliteForbiddenError,
            single_topology_object,
            single_topology_object,
        )

    def test_bi_directional_connection_between_satellite_and_ground_station_using_gsl(
        self,
        gsl_link: GroundStationLink,
        ground_station: GroundStation,
        satellite: Satellite,
    ):
        assert_can_establish_connection(gsl_link, ground_station, satellite)
        assert_can_establish_connection(gsl_link, satellite, ground_station)

    def test_impossible_connection_between_satellites_using_gsl(
        self, gsl_link: GroundStationLink, satellite
    ):
        second_satellite = Satellite(satellite_name="Test Satellite 1", object_id=1)
        assert_cant_establish_connection(
            gsl_link,
            GroundStationConnectionError,
            satellite,
            second_satellite,
        )

    def test_impossible_connection_between_satellite_and_user_using_gsl(
        self,
        gsl_link: GroundStationLink,
        satellite: Satellite,
        user_terminal: UserTerminal,
    ):
        assert_cant_establish_connection(
            gsl_link,
            GroundStationConnectionError,
            satellite,
            user_terminal,
        )
        assert_cant_establish_connection(
            gsl_link,
            GroundStationConnectionError,
            user_terminal,
            satellite,
        )

    def test_satellites_cannot_connect_using_gsl_link(
        self, gsl_link: GroundStationLink, satellite: Satellite
    ):
        other_satellite = Satellite(satellite_name="Test Satellite 2", object_id=2)

        assert_cant_establish_connection(
            gsl_link, GroundStationConnectionError, satellite, other_satellite
        )

    def test_user_and_satellite_cannot_connect_using_gsl_link(
        self,
        gsl_link: GroundStationLink,
        satellite: Satellite,
        user_terminal: UserTerminal,
    ):
        assert_cant_establish_connection(
            gsl_link,
            GroundStationConnectionError,
            satellite,
            user_terminal,
        )
        assert_cant_establish_connection(
            gsl_link,
            GroundStationConnectionError,
            user_terminal,
            satellite,
        )

    def test_satellite_can_connect_to_satellite_using_isl(
        self, isl_link: InterSatelliteLink, satellite: Satellite
    ):
        other_satellite = Satellite(object_id=1, satellite_name="Test Satellite 1")
        other_satellite.topology_uniq_id = 9684
        assert_can_establish_connection(isl_link, satellite, other_satellite)

    def test_satellite_cant_connect_to_gs_with_isl(
        self,
        isl_link: InterSatelliteLink,
        satellite: Satellite,
        ground_station: GroundStation,
    ):
        assert_cant_establish_connection(
            isl_link,
            InterSatelliteConnectionError,
            satellite,
            ground_station,
        )
        assert_cant_establish_connection(
            isl_link,
            InterSatelliteConnectionError,
            ground_station,
            satellite,
        )

    def test_satellite_cant_connect_to_user_with_isl(
        self,
        isl_link: InterSatelliteLink,
        satellite: Satellite,
        user_terminal: UserTerminal,
    ):
        assert_cant_establish_connection(
            isl_link,
            InterSatelliteConnectionError,
            satellite,
            user_terminal,
        )
        assert_cant_establish_connection(
            isl_link,
            InterSatelliteConnectionError,
            satellite,
            user_terminal,
        )

    def test_user_connect_with_satellite_using_utl(
        self,
        user_link: UserTerminalLink,
        user_terminal: UserTerminal,
        satellite: Satellite,
    ):
        assert_can_establish_connection(user_link, user_terminal, satellite)
        assert_can_establish_connection(user_link, satellite, user_terminal)

    def test_gs_cant_connect_with_satellite_utl(
        self,
        user_link: UserTerminalLink,
        ground_station: GroundStation,
        satellite: Satellite,
    ):
        assert_cant_establish_connection(
            user_link,
            UserTerminalConnectionError,
            ground_station,
            satellite,
        )
        assert_cant_establish_connection(
            user_link,
            UserTerminalConnectionError,
            satellite,
            ground_station,
        )

    def test_ground_object_can_establish_static_ground_connection(
        self,
        static_ground_object_link_1: GroundObjectLink,
        ground_station: GroundStation,
        ground_station_2: GroundStation,
        point_of_presence: PointOfPresence,
        point_of_presence_2: PointOfPresence,
    ):
        assert_can_establish_connection(
            static_ground_object_link_1,
            ground_station,
            point_of_presence,
        )

        assert_can_establish_connection(
            static_ground_object_link_1,
            point_of_presence_2,
            point_of_presence,
        )
        assert_can_establish_connection(
            static_ground_object_link_1,
            ground_station,
            ground_station_2,
        )

    def test_static_ground_object_link_cant_connect_with_satellite(
        self,
        static_ground_object_link_1: GroundObjectLink,
        satellite: Satellite,
        satellite_2: Satellite,
        ground_station: GroundStation,
        user_terminal: UserTerminal,
    ):
        assert_cant_establish_connection(
            static_ground_object_link_1,
            GroundObjectLinkConnectionError,
            satellite,
            satellite_2,
        )
        assert_cant_establish_connection(
            static_ground_object_link_1,
            GroundObjectLinkConnectionError,
            ground_station,
            satellite,
        )
