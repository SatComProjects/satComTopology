from src.sat_com_model.exception import (
    GroundStationConnectionError,
    InterSatelliteConnectionError,
    UserTerminalConnectionError,
    ConnectionBetweenSameSatelliteForbiddenError,
)
from src.sat_com_model.model import (
    GroundStation,
    Satellite,
    GroundStationLink,
    UserTerminal,
    InterSatelliteLink,
    UserTerminalLink,
    Link,
    TopologyObject,
)
import pytest


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
    return Satellite()


@pytest.fixture
def ground_station() -> GroundStation:
    return GroundStation()


@pytest.fixture
def user_terminal() -> UserTerminal:
    return UserTerminal()


@pytest.fixture
def gsl_link() -> GroundStationLink:
    return GroundStationLink()


@pytest.fixture
def isl_link() -> InterSatelliteLink:
    return InterSatelliteLink()


@pytest.fixture
def user_link() -> UserTerminalLink:
    return UserTerminalLink()


class TestLinks:
    def test_cant_establish_connection_between_same_object(self):
        single_topology_object = TopologyObject()
        link = Link()
        assert_cant_establish_connection(
            link,
            ConnectionBetweenSameSatelliteForbiddenError,
            single_topology_object,
            single_topology_object,
        )

    def test_bi_directional_connection_between_satellite_and_ground_station_using_gsl(
        self, gsl_link: GroundStationLink, ground_station, satellite
    ):
        assert_can_establish_connection(gsl_link, ground_station, satellite)
        assert_can_establish_connection(gsl_link, satellite, ground_station)

    def test_impossible_connection_between_satellites_using_gsl(
        self, gsl_link: GroundStationLink, satellite
    ):
        second_satellite = Satellite()
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
        other_satellite = Satellite()

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
        other_satellite = Satellite()
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
