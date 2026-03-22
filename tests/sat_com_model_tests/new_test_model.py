import pytest

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
    OpticalLinkTerminal,
    InterSatelliteLinkDirection,
    OpticalConstraint,
    SatelliteConfiguration,
    OpticalTerminalInstallationConfiguration,
    InterSatelliteLinkOrientation,
    OpticalTerminalConfiguration,
)

# ===========================================================================
# Helpers
# ===========================================================================


def assert_can_establish_connection(
    link: Link,
    source: TopologyObject,
    destination: TopologyObject,
):
    link.connect(source, destination)
    assert link.source == source
    assert link.destination == destination


def assert_cant_establish_connection(
    link: Link,
    expected_exception,
    source: TopologyObject,
    destination: TopologyObject,
):
    with pytest.raises(expected_exception):
        link.connect(source, destination)
    assert link.source is None
    assert link.destination is None


def make_optical_constraint() -> OpticalConstraint:
    return OpticalConstraint(
        azimuth_angle_degree=0.0,
        elevation_angle_degree=5.0,
        range_distance_km=500.0,
        angular_velocity_rate_degree_per_second=0.1,
    )


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture
def satellite() -> Satellite:
    """Satellite with default 4 optical terminals (created automatically by __init__)."""
    sat = Satellite(object_id=0, satellite_name="Test Satellite A")
    sat.topology_uniq_id = 1
    return sat


@pytest.fixture
def satellite_2() -> Satellite:
    sat = Satellite(object_id=1, satellite_name="Test Satellite B")
    sat.topology_uniq_id = 2
    return sat


@pytest.fixture
def satellite_3() -> Satellite:
    sat = Satellite(object_id=2, satellite_name="Test Satellite C")
    sat.topology_uniq_id = 3
    return sat


@pytest.fixture
def ground_station() -> GroundStation:
    gs = GroundStation()
    gs.topology_uniq_id = 10
    return gs


@pytest.fixture
def ground_station_2() -> GroundStation:
    gs = GroundStation()
    gs.topology_uniq_id = 11
    return gs


@pytest.fixture
def user_terminal() -> UserTerminal:
    ut = UserTerminal()
    ut.topology_uniq_id = 20
    return ut


@pytest.fixture
def point_of_presence() -> PointOfPresence:
    pop = PointOfPresence()
    pop.topology_uniq_id = 30
    return pop


@pytest.fixture
def point_of_presence_2() -> PointOfPresence:
    pop = PointOfPresence()
    pop.topology_uniq_id = 31
    return pop


@pytest.fixture
def isl_link() -> InterSatelliteLink:
    return InterSatelliteLink()


@pytest.fixture
def gsl_link() -> GroundStationLink:
    return GroundStationLink()


@pytest.fixture
def utl_link() -> UserTerminalLink:
    return UserTerminalLink()


@pytest.fixture
def ground_object_link() -> GroundObjectLink:
    return GroundObjectLink()


# ===========================================================================
# Satellite — optical terminal initialisation
# ===========================================================================


class TestSatelliteOpticalTerminals:

    def test_satellite_without_shell_gets_default_4_terminals(self, satellite):
        assert len(satellite.optical_link_terminals) == 4

    def test_all_terminals_have_host_satellite_set(self, satellite):
        for terminal in satellite.optical_link_terminals:
            assert terminal.host_satellite is satellite

    def test_default_terminal_descriptors(self, satellite):
        descriptors = [t.descriptor for t in satellite.optical_link_terminals]
        assert InterSatelliteLinkOrientation.INTRA_PLANE_FORWARD in descriptors
        assert InterSatelliteLinkOrientation.INTRA_PLANE_BACKWARD in descriptors
        assert InterSatelliteLinkOrientation.INTER_PLANE_LEFT in descriptors
        assert InterSatelliteLinkOrientation.INTER_PLANE_RIGHT in descriptors

    def test_terminals_have_unique_ids(self, satellite):
        ids = [t.terminal_id for t in satellite.optical_link_terminals]
        assert len(ids) == len(set(ids))

    def test_terminal_initial_link_is_none(self, satellite):
        for terminal in satellite.optical_link_terminals:
            assert terminal.link is None

    def test_terminal_initial_peer_is_none(self, satellite):
        for terminal in satellite.optical_link_terminals:
            assert terminal.target_optical_link_terminal is None

    def test_satellite_with_custom_configuration(self):
        cfg = SatelliteConfiguration(
            optical_inter_satellite_link_installations=[
                OpticalTerminalInstallationConfiguration(
                    azimuth_angle_configuration=0.0,
                    elevation_angle_configuration=-180.0,
                    descriptor=InterSatelliteLinkOrientation.INTRA_PLANE_FORWARD,
                    orientation_possibilities=[
                        InterSatelliteLinkOrientation.INTRA_PLANE_FORWARD
                    ],
                    optical_terminal_property=OpticalTerminalConfiguration(),
                )
            ]
        )
        sat = Satellite(object_id=99, satellite_name="Custom", shell=None)
        sat.reconfigure_satellite(cfg)
        # 4 defaults from __init__ + 1 from reconfigure
        assert len(sat.optical_link_terminals) == 5

    def test_terminals_from_different_satellites_are_not_equal(
        self, satellite, satellite_2
    ):
        for t1 in satellite.optical_link_terminals:
            for t2 in satellite_2.optical_link_terminals:
                assert t1 != t2


# ===========================================================================
# OpticalLinkTerminal — hash and equality
# ===========================================================================


class TestOpticalLinkTerminalIdentity:

    def test_terminal_equals_itself(self, satellite):
        t = satellite.optical_link_terminals[0]
        assert t == t

    def test_terminal_hashable(self, satellite):
        t = satellite.optical_link_terminals[0]
        s = {t}
        assert t in s

    def test_terminals_usable_as_dict_keys(self, satellite):
        t = satellite.optical_link_terminals[0]
        d = {t: "value"}
        assert d[t] == "value"

    def test_terminal_not_equal_to_different_terminal(self, satellite):
        t1 = satellite.optical_link_terminals[0]
        t2 = satellite.optical_link_terminals[1]
        assert t1 != t2

    def test_terminal_not_equal_to_non_terminal(self, satellite):
        t = satellite.optical_link_terminals[0]
        assert t != "not a terminal"
        assert t != 42


# ===========================================================================
# InterSatelliteLink — bind / unbind terminals
# ===========================================================================


class TestISLBindTerminals:

    def test_bind_sets_all_back_references(self, satellite, satellite_2, isl_link):
        isl_link.connect(satellite, satellite_2)
        t_a = satellite.optical_link_terminals[0]
        t_b = satellite_2.optical_link_terminals[3]

        isl_link.bind_terminals(
            source_terminal=t_a,
            destination_terminal=t_b,
            source_constraint=make_optical_constraint(),
            destination_constraint=make_optical_constraint(),
        )

        assert isl_link.source_optical_terminal is t_a
        assert isl_link.destination_optical_terminal is t_b
        assert t_a.link is isl_link
        assert t_b.link is isl_link
        assert t_a.target_optical_link_terminal is t_b
        assert t_b.target_optical_link_terminal is t_a

    def test_bind_sets_constraints(self, satellite, satellite_2, isl_link):
        isl_link.connect(satellite, satellite_2)
        constraint_a = make_optical_constraint()
        constraint_b = make_optical_constraint()
        t_a = satellite.optical_link_terminals[0]
        t_b = satellite_2.optical_link_terminals[3]

        isl_link.bind_terminals(t_a, t_b, constraint_a, constraint_b)

        assert isl_link.source_constraint == constraint_a
        assert isl_link.destination_constraint == constraint_b

    def test_bind_raises_if_terminal_already_bound_to_different_link(
        self, satellite, satellite_2, satellite_3
    ):
        link_1 = InterSatelliteLink()
        link_2 = InterSatelliteLink()
        link_1.connect(satellite, satellite_2)
        link_2.connect(satellite, satellite_3)

        t_a = satellite.optical_link_terminals[0]
        t_b = satellite_2.optical_link_terminals[3]

        link_1.bind_terminals(t_a, t_b, None, None)

        # t_a is now bound to link_1 — binding to link_2 must raise
        t_c = satellite_3.optical_link_terminals[3]
        with pytest.raises(ValueError):
            link_2.bind_terminals(t_a, t_c, None, None)

    def test_bind_same_link_twice_is_allowed(self, satellite, satellite_2, isl_link):
        """Re-binding the same terminal to the same link must not raise."""
        isl_link.connect(satellite, satellite_2)
        t_a = satellite.optical_link_terminals[0]
        t_b = satellite_2.optical_link_terminals[3]

        isl_link.bind_terminals(t_a, t_b, None, None)
        isl_link.bind_terminals(t_a, t_b, None, None)  # should not raise

    def test_unbind_clears_all_back_references(self, satellite, satellite_2, isl_link):
        isl_link.connect(satellite, satellite_2)
        t_a = satellite.optical_link_terminals[0]
        t_b = satellite_2.optical_link_terminals[3]
        isl_link.bind_terminals(t_a, t_b, None, None)

        isl_link.unbind_terminals()

        assert isl_link.source_optical_terminal is None
        assert isl_link.destination_optical_terminal is None
        assert t_a.link is None
        assert t_b.link is None
        assert t_a.target_optical_link_terminal is None
        assert t_b.target_optical_link_terminal is None

    def test_unbind_clears_constraints(self, satellite, satellite_2, isl_link):
        isl_link.connect(satellite, satellite_2)
        t_a = satellite.optical_link_terminals[0]
        t_b = satellite_2.optical_link_terminals[3]
        isl_link.bind_terminals(
            t_a, t_b, make_optical_constraint(), make_optical_constraint()
        )

        isl_link.unbind_terminals()

        assert isl_link.source_constraint is None
        assert isl_link.destination_constraint is None

    def test_unbind_on_unbound_link_does_not_raise(self, isl_link):
        isl_link.unbind_terminals()  # nothing bound — must not raise

    def test_same_terminal_cannot_be_source_and_destination(
        self, satellite, satellite_2
    ):
        link = InterSatelliteLink()
        t = satellite.optical_link_terminals[0]
        with pytest.raises(InterSatelliteConnectionError):
            link.connect(
                satellite,
                satellite_2,
                source_optical_terminal=t,
                destination_optical_terminal=t,
            )


# ===========================================================================
# InterSatelliteLink — navigation helpers
# ===========================================================================


class TestISLNavigationHelpers:

    @pytest.fixture
    def bound_link(self, satellite, satellite_2):
        link = InterSatelliteLink()
        link.connect(satellite, satellite_2)
        t_a = satellite.optical_link_terminals[0]
        t_b = satellite_2.optical_link_terminals[3]
        link.bind_terminals(t_a, t_b, None, None)
        return link, satellite, satellite_2, t_a, t_b

    def test_get_satellite_source(self, bound_link):
        link, sat_a, sat_b, *_ = bound_link
        assert link.get_satellite_source() is sat_a

    def test_get_satellite_destination(self, bound_link):
        link, sat_a, sat_b, *_ = bound_link
        assert link.get_satellite_destination() is sat_b

    def test_get_peer_satellite_from_source(self, bound_link):
        link, sat_a, sat_b, *_ = bound_link
        assert link.get_peer_satellite(sat_a) is sat_b

    def test_get_peer_satellite_from_destination(self, bound_link):
        link, sat_a, sat_b, *_ = bound_link
        assert link.get_peer_satellite(sat_b) is sat_a

    def test_get_peer_satellite_raises_for_unknown(self, bound_link, satellite_3):
        link, *_ = bound_link
        with pytest.raises(ValueError):
            link.get_peer_satellite(satellite_3)

    def test_get_terminal_for_satellite_source(self, bound_link):
        link, sat_a, sat_b, t_a, t_b = bound_link
        assert link.get_terminal_for_satellite(sat_a) is t_a

    def test_get_terminal_for_satellite_destination(self, bound_link):
        link, sat_a, sat_b, t_a, t_b = bound_link
        assert link.get_terminal_for_satellite(sat_b) is t_b

    def test_get_terminal_for_satellite_raises_for_unknown(
        self, bound_link, satellite_3
    ):
        link, *_ = bound_link
        with pytest.raises(ValueError):
            link.get_terminal_for_satellite(satellite_3)

    def test_get_peer_terminal(self, bound_link):
        link, sat_a, sat_b, t_a, t_b = bound_link
        assert link.get_peer_terminal(t_a) is t_b
        assert link.get_peer_terminal(t_b) is t_a

    def test_get_peer_terminal_raises_for_unbound(self, bound_link, satellite_3):
        link, *_ = bound_link
        unrelated = satellite_3.optical_link_terminals[0]
        with pytest.raises(ValueError):
            link.get_peer_terminal(unrelated)


# ===========================================================================
# Link — hash and equality
# ===========================================================================


class TestLinkIdentity:

    def test_link_equals_itself(self):
        link = Link()
        assert link == link

    def test_two_different_links_are_not_equal(self):
        assert Link() != Link()

    def test_link_hashable(self):
        link = Link()
        s = {link}
        assert link in s

    def test_link_usable_as_dict_key(self):
        link = Link()
        d = {link: "value"}
        assert d[link] == "value"

    def test_isl_link_equality_uses_link_id(self, satellite, satellite_2):
        link = InterSatelliteLink()
        link.connect(satellite, satellite_2)
        assert link == link
        assert link != InterSatelliteLink()


# ===========================================================================
# Link connection rules
# ===========================================================================


class TestLinkConnectionRules:

    def test_cannot_connect_same_object_to_itself(self):
        obj = TopologyObject()
        obj.topology_uniq_id = 0
        link = Link()
        assert_cant_establish_connection(
            link, ConnectionBetweenSameSatelliteForbiddenError, obj, obj
        )

    # GSL
    def test_gsl_satellite_to_ground_station(self, gsl_link, satellite, ground_station):
        assert_can_establish_connection(gsl_link, satellite, ground_station)

    def test_gsl_ground_station_to_satellite(self, gsl_link, satellite, ground_station):
        assert_can_establish_connection(gsl_link, ground_station, satellite)

    def test_gsl_rejects_satellite_to_satellite(self, gsl_link, satellite, satellite_2):
        assert_cant_establish_connection(
            gsl_link, GroundStationConnectionError, satellite, satellite_2
        )

    def test_gsl_rejects_satellite_to_user_terminal(
        self, gsl_link, satellite, user_terminal
    ):
        assert_cant_establish_connection(
            gsl_link, GroundStationConnectionError, satellite, user_terminal
        )
        assert_cant_establish_connection(
            gsl_link, GroundStationConnectionError, user_terminal, satellite
        )

    # ISL
    def test_isl_satellite_to_satellite(self, isl_link, satellite, satellite_2):
        assert_can_establish_connection(isl_link, satellite, satellite_2)

    def test_isl_rejects_satellite_to_ground_station(
        self, isl_link, satellite, ground_station
    ):
        assert_cant_establish_connection(
            isl_link, InterSatelliteConnectionError, satellite, ground_station
        )
        assert_cant_establish_connection(
            isl_link, InterSatelliteConnectionError, ground_station, satellite
        )

    def test_isl_rejects_satellite_to_user_terminal(
        self, isl_link, satellite, user_terminal
    ):
        assert_cant_establish_connection(
            isl_link, InterSatelliteConnectionError, satellite, user_terminal
        )

    # UTL
    def test_utl_user_terminal_to_satellite(self, utl_link, satellite, user_terminal):
        assert_can_establish_connection(utl_link, user_terminal, satellite)

    def test_utl_satellite_to_user_terminal(self, utl_link, satellite, user_terminal):
        assert_can_establish_connection(utl_link, satellite, user_terminal)

    def test_utl_rejects_ground_station_to_satellite(
        self, utl_link, ground_station, satellite
    ):
        assert_cant_establish_connection(
            utl_link, UserTerminalConnectionError, ground_station, satellite
        )
        assert_cant_establish_connection(
            utl_link, UserTerminalConnectionError, satellite, ground_station
        )

    # GroundObjectLink
    def test_ground_object_link_gs_to_pop(
        self, ground_object_link, ground_station, point_of_presence
    ):
        assert_can_establish_connection(
            ground_object_link, ground_station, point_of_presence
        )

    def test_ground_object_link_pop_to_pop(
        self, ground_object_link, point_of_presence, point_of_presence_2
    ):
        assert_can_establish_connection(
            ground_object_link, point_of_presence, point_of_presence_2
        )

    def test_ground_object_link_gs_to_gs(
        self, ground_object_link, ground_station, ground_station_2
    ):
        assert_can_establish_connection(
            ground_object_link, ground_station, ground_station_2
        )

    def test_ground_object_link_rejects_satellite(
        self, ground_object_link, satellite, satellite_2, ground_station
    ):
        assert_cant_establish_connection(
            ground_object_link,
            GroundObjectLinkConnectionError,
            satellite,
            satellite_2,
        )
        assert_cant_establish_connection(
            ground_object_link,
            GroundObjectLinkConnectionError,
            ground_station,
            satellite,
        )


# ===========================================================================
# ISL direction
# ===========================================================================


class TestISLDirection:

    def test_default_direction_is_undefined(self, satellite, satellite_2):
        link = InterSatelliteLink()
        link.connect(satellite, satellite_2)
        assert link.inter_satellite_direction == InterSatelliteLinkDirection.UNDEFINED

    def test_orbital_direction_stored(self, satellite, satellite_2):
        link = InterSatelliteLink()
        link.connect(
            satellite,
            satellite_2,
            inter_satellite_direction=InterSatelliteLinkDirection.ORBITAL,
        )
        assert link.inter_satellite_direction == InterSatelliteLinkDirection.ORBITAL

    def test_adjacent_direction_stored(self, satellite, satellite_2):
        link = InterSatelliteLink()
        link.connect(
            satellite,
            satellite_2,
            inter_satellite_direction=InterSatelliteLinkDirection.ADJACENT,
        )
        assert link.inter_satellite_direction == InterSatelliteLinkDirection.ADJACENT

    def test_inter_shell_direction_stored(self, satellite, satellite_2):
        link = InterSatelliteLink()
        link.connect(
            satellite,
            satellite_2,
            inter_satellite_direction=InterSatelliteLinkDirection.INTER_SHELL,
        )
        assert link.inter_satellite_direction == InterSatelliteLinkDirection.INTER_SHELL


# ===========================================================================
# ISL repr
# ===========================================================================


class TestISLRepr:

    def test_repr_shows_topology_ids(self, satellite, satellite_2):
        link = InterSatelliteLink()
        link.connect(satellite, satellite_2)
        r = repr(link)
        assert str(satellite.topology_uniq_id) in r
        assert str(satellite_2.topology_uniq_id) in r

    def test_repr_does_not_recurse(self, satellite, satellite_2, isl_link):
        """Repr must not trigger RecursionError even with terminal back-references."""
        isl_link.connect(satellite, satellite_2)
        t_a = satellite.optical_link_terminals[0]
        t_b = satellite_2.optical_link_terminals[3]
        isl_link.bind_terminals(t_a, t_b, None, None)

        try:
            repr(isl_link)
        except RecursionError:
            pytest.fail("repr(InterSatelliteLink) triggered RecursionError")
