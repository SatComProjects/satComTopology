import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from sat_com_application.simulation_manager import SimulationManager
from sat_com_application.event_bus.events import (
    ISLCreatedEvent,
    ISLRemovedEvent,
    ISLUpdatedEvent,
    GSLCreatedEvent,
    GSLRemovedEvent,
    GSLUpdatedEvent,
    UTLCreatedEvent,
    UTLRemovedEvent,
    UTLUpdatedEvent,
)
from sat_com_model.exceptions import (
    TopologyObjectNotFoundError,
    TopologyIdentifierNotDefinedError,
    LinkNotFoundError,
    OpticalLinkTerminalNotFoundError,
)
from sat_com_model.models import (
    Simulation,
    InterSatelliteLink,
    OpticalConstraint,
    InterSatelliteLinkDirection,
    OpticalLinkTerminal,
)
from sat_com_connectivity.inter_satellite_link_connectivity.models import (
    InterSatelliteConnectivityResult,
    LinkAssociation,
    OpticISLVisibilityConstraintResult,
)
from tests.sat_com_model_tests.model_helper import (
    create_fake_satellite_with_object_id,
    create_fake_ground_station_with_object_id,
    create_fake_user_terminal_with_object_id,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_optical_constraint() -> OpticalConstraint:
    return OpticalConstraint(
        azimuth_angle_degree=0.0,
        elevation_angle_degree=5.0,
        range_distance_km=500.0,
        angular_velocity_rate_degree_per_second=0.1,
    )


def make_visibility_constraint() -> OpticISLVisibilityConstraintResult:
    return OpticISLVisibilityConstraintResult(
        elevation_angle_degree=5.0,
        azimuth_angle_degree=0.0,
        range_distance_km=500.0,
        angular_velocity_rate_degree_per_second=0.1,
        flag_elevation=True,
        flag_azimuth=True,
        flag_range=True,
        flag_angular_velocity=True,
        flag_overall=True,
        flag_bidirectional=True,
    )


def make_link_association(sat_a, sat_b, link=None, terminal_a=None, terminal_b=None):
    return LinkAssociation(
        satellite_a=sat_a,
        terminal_a=terminal_a or MagicMock(spec=OpticalLinkTerminal),
        satellite_b=sat_b,
        terminal_b=terminal_b or MagicMock(spec=OpticalLinkTerminal),
        direction=InterSatelliteLinkDirection.ORBITAL,
        link=link,
        constraint_a_to_b=make_visibility_constraint(),
        constraint_b_to_a=make_visibility_constraint(),
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def simulation():
    return Simulation()


@pytest.fixture
def manager(simulation):
    return SimulationManager(simulation)


@pytest.fixture
def manager_with_event_bus(simulation):
    bus = MagicMock()
    bus.publish = AsyncMock()
    return SimulationManager(simulation, event_bus=bus)


# ===========================================================================
# Topology object management
# ===========================================================================


class TestTopologyObjectManagement:

    def test_add_satellite_assigns_topology_id(self, manager):
        expected_id = manager.simulation.object_uuid_index
        sat = create_fake_satellite_with_object_id(1)
        with pytest.raises(TopologyIdentifierNotDefinedError):
            sat.get_topology_uniq_id()
        manager.add_satellite(sat)
        assert sat.get_topology_uniq_id() == expected_id

    def test_add_ground_station_assigns_topology_id(self, manager):
        expected_id = manager.simulation.object_uuid_index
        gs = create_fake_ground_station_with_object_id(1)
        with pytest.raises(TopologyIdentifierNotDefinedError):
            gs.get_topology_uniq_id()
        manager.add_ground_station(gs)
        assert gs.get_topology_uniq_id() == expected_id

    def test_add_user_terminal_assigns_topology_id(self, manager):
        expected_id = manager.simulation.object_uuid_index
        ut = create_fake_user_terminal_with_object_id(1)
        with pytest.raises(TopologyIdentifierNotDefinedError):
            ut.get_topology_uniq_id()
        manager.add_user_terminals(ut)
        assert ut.get_topology_uniq_id() == expected_id

    def test_get_satellite_by_object_id(self, manager):
        sat1 = create_fake_satellite_with_object_id(1)
        sat2 = create_fake_satellite_with_object_id(2)
        manager.add_satellite(sat1)
        manager.add_satellite(sat2)
        assert manager.get_satellite_by_object_id(1) == sat1
        with pytest.raises(TopologyObjectNotFoundError):
            manager.get_satellite_by_object_id(99)

    def test_get_ground_station_by_object_id(self, manager):
        gs1 = create_fake_ground_station_with_object_id(1)
        gs2 = create_fake_ground_station_with_object_id(2)
        manager.add_ground_station(gs1)
        manager.add_ground_station(gs2)
        assert manager.get_ground_station_by_object_id(1) == gs1
        with pytest.raises(TopologyObjectNotFoundError):
            manager.get_ground_station_by_object_id(99)

    def test_get_user_terminal_by_object_id(self, manager):
        ut1 = create_fake_user_terminal_with_object_id(1)
        ut2 = create_fake_user_terminal_with_object_id(2)
        manager.add_user_terminals(ut1)
        manager.add_user_terminals(ut2)
        assert manager.get_user_terminal_by_object_id(1) == ut1
        with pytest.raises(TopologyObjectNotFoundError):
            manager.get_user_terminal_by_object_id(99)

    def test_get_all_topology_objects(self, manager):
        assert len(manager.get_all_topology_objects()) == 0
        manager.add_satellite(create_fake_satellite_with_object_id(1))
        manager.add_ground_station(create_fake_ground_station_with_object_id(1))
        manager.add_user_terminals(create_fake_user_terminal_with_object_id(1))
        assert len(manager.get_all_topology_objects()) == 3


# ===========================================================================
# ISL creation
# ===========================================================================


class TestISLCreation:

    def test_create_isl_adds_to_simulation(self, manager):
        sat1 = create_fake_satellite_with_object_id(1)
        sat2 = create_fake_satellite_with_object_id(2)
        manager.add_satellite(sat1)
        manager.add_satellite(sat2)

        link = manager.create_and_add_inter_satellite_link_connection(sat1, sat2)

        assert link in manager.simulation.inter_satellite_links
        assert link in sat1.links
        assert link in sat2.links
        assert link.source.topology_uniq_id == sat1.topology_uniq_id
        assert link.destination.topology_uniq_id == sat2.topology_uniq_id

    def test_create_isl_with_terminals_binds_them(self, manager):
        sat1 = create_fake_satellite_with_object_id(1)
        sat2 = create_fake_satellite_with_object_id(2)
        manager.add_satellite(sat1)
        manager.add_satellite(sat2)

        terminal_a = sat1.optical_link_terminals[0]
        terminal_b = sat2.optical_link_terminals[0]

        link = manager.create_and_add_inter_satellite_link_connection(
            sat1,
            sat2,
            terminal_a=terminal_a,
            terminal_b=terminal_b,
        )

        assert link.source_optical_terminal is not None
        assert link.destination_optical_terminal is not None

    def test_create_isl_publishes_created_event(self, manager_with_event_bus):
        bus = manager_with_event_bus.event_bus
        sat1 = create_fake_satellite_with_object_id(1)
        sat2 = create_fake_satellite_with_object_id(2)
        manager_with_event_bus.add_satellite(sat1)
        manager_with_event_bus.add_satellite(sat2)

        manager_with_event_bus.create_and_add_inter_satellite_link_connection(
            sat1, sat2
        )

        event = bus.publish.call_args[0][0]
        assert isinstance(event, ISLCreatedEvent)
        assert event.satellite_a_id == sat1.topology_uniq_id
        assert event.satellite_b_id == sat2.topology_uniq_id

    def test_create_isl_with_direction(self, manager):
        sat1 = create_fake_satellite_with_object_id(1)
        sat2 = create_fake_satellite_with_object_id(2)
        manager.add_satellite(sat1)
        manager.add_satellite(sat2)

        link = manager.create_and_add_inter_satellite_link_connection(
            sat1,
            sat2,
            inter_satellite_link_direction=InterSatelliteLinkDirection.ORBITAL,
        )

        assert link.inter_satellite_direction == InterSatelliteLinkDirection.ORBITAL


# ===========================================================================
# ISL removal
# ===========================================================================


class TestISLRemoval:

    def test_remove_isl_removes_from_simulation(self, manager):
        sat1 = create_fake_satellite_with_object_id(1)
        sat2 = create_fake_satellite_with_object_id(2)
        manager.add_satellite(sat1)
        manager.add_satellite(sat2)
        link = manager.create_and_add_inter_satellite_link_connection(sat1, sat2)

        manager.remove_inter_satellite_link(link)

        assert link not in manager.simulation.inter_satellite_links
        assert link not in sat1.links
        assert link not in sat2.links

    def test_remove_isl_unbinds_terminals(self, manager):
        sat1 = create_fake_satellite_with_object_id(1)
        sat2 = create_fake_satellite_with_object_id(2)
        manager.add_satellite(sat1)
        manager.add_satellite(sat2)

        terminal_a = sat1.optical_link_terminals[0]
        terminal_b = sat2.optical_link_terminals[0]

        link = manager.create_and_add_inter_satellite_link_connection(
            sat1,
            sat2,
            terminal_a=terminal_a,
            terminal_b=terminal_b,
        )
        assert terminal_a.link is link

        manager.remove_inter_satellite_link(link)

        assert terminal_a.link is None
        assert terminal_b.link is None
        assert terminal_a.target_optical_link_terminal is None
        assert terminal_b.target_optical_link_terminal is None

    def test_remove_isl_clears_flows(self, manager):
        sat1 = create_fake_satellite_with_object_id(1)
        sat2 = create_fake_satellite_with_object_id(2)
        manager.add_satellite(sat1)
        manager.add_satellite(sat2)
        link = manager.create_and_add_inter_satellite_link_connection(sat1, sat2)
        link.flows.append(MagicMock())

        manager.remove_inter_satellite_link(link)

        assert len(link.flows) == 0

    def test_remove_isl_publishes_removed_event(self, manager_with_event_bus):
        bus = manager_with_event_bus.event_bus
        sat1 = create_fake_satellite_with_object_id(1)
        sat2 = create_fake_satellite_with_object_id(2)
        manager_with_event_bus.add_satellite(sat1)
        manager_with_event_bus.add_satellite(sat2)
        link = manager_with_event_bus.create_and_add_inter_satellite_link_connection(
            sat1, sat2
        )
        bus.publish.reset_mock()

        manager_with_event_bus.remove_inter_satellite_link(link)

        event = bus.publish.call_args[0][0]
        assert isinstance(event, ISLRemovedEvent)

    def test_remove_isl_guards_against_missing_link(self, manager):
        """Defensive guards must not raise if link is already absent from a list."""
        sat1 = create_fake_satellite_with_object_id(1)
        sat2 = create_fake_satellite_with_object_id(2)
        manager.add_satellite(sat1)
        manager.add_satellite(sat2)
        link = manager.create_and_add_inter_satellite_link_connection(sat1, sat2)

        manager.remove_inter_satellite_link(link)
        # Second remove must not raise — lists have guards
        manager.remove_inter_satellite_link(link)


# ===========================================================================
# ISL update
# ===========================================================================


class TestISLUpdate:

    def test_update_isl_sets_constraints(self, manager):
        sat1 = create_fake_satellite_with_object_id(1)
        sat2 = create_fake_satellite_with_object_id(2)
        manager.add_satellite(sat1)
        manager.add_satellite(sat2)
        link = manager.create_and_add_inter_satellite_link_connection(sat1, sat2)

        constraint_a = make_optical_constraint()
        constraint_b = make_optical_constraint()

        manager.update_inter_satellite_link(link, constraint_a, constraint_b)

        assert link.source_constraint == constraint_a
        assert link.destination_constraint == constraint_b

    def test_update_isl_publishes_updated_event(self, manager_with_event_bus):
        bus = manager_with_event_bus.event_bus
        sat1 = create_fake_satellite_with_object_id(1)
        sat2 = create_fake_satellite_with_object_id(2)
        manager_with_event_bus.add_satellite(sat1)
        manager_with_event_bus.add_satellite(sat2)
        link = manager_with_event_bus.create_and_add_inter_satellite_link_connection(
            sat1, sat2
        )
        bus.publish.reset_mock()

        manager_with_event_bus.update_inter_satellite_link(
            link, make_optical_constraint(), make_optical_constraint()
        )

        event = bus.publish.call_args[0][0]
        assert isinstance(event, ISLUpdatedEvent)
        assert event.satellite_a_id == sat1.topology_uniq_id
        assert event.satellite_b_id == sat2.topology_uniq_id


# ===========================================================================
# bind_optical_inter_satellite_links
# ===========================================================================


class TestBindOpticalISL:

    def test_bind_sets_terminal_link_references(self, manager):
        sat1 = create_fake_satellite_with_object_id(1)
        sat2 = create_fake_satellite_with_object_id(2)
        manager.add_satellite(sat1)
        manager.add_satellite(sat2)
        link = manager.create_and_add_inter_satellite_link_connection(sat1, sat2)

        terminal_a = sat1.optical_link_terminals[0]
        terminal_b = sat2.optical_link_terminals[0]

        manager.bind_optical_inter_satellite_links(
            sat1, sat2, terminal_a, terminal_b, link
        )

        assert terminal_a.link is link
        assert terminal_b.link is link

    def test_bind_raises_when_link_not_in_simulation(self, manager):
        sat1 = create_fake_satellite_with_object_id(1)
        sat2 = create_fake_satellite_with_object_id(2)
        manager.add_satellite(sat1)
        manager.add_satellite(sat2)
        link = InterSatelliteLink()  # not added to simulation

        with pytest.raises(LinkNotFoundError):
            manager.bind_optical_inter_satellite_links(
                sat1,
                sat2,
                sat1.optical_link_terminals[0],
                sat2.optical_link_terminals[0],
                link,
            )

    def test_bind_raises_when_terminal_not_on_satellite(self, manager):
        sat1 = create_fake_satellite_with_object_id(1)
        sat2 = create_fake_satellite_with_object_id(2)
        sat3 = create_fake_satellite_with_object_id(3)
        manager.add_satellite(sat1)
        manager.add_satellite(sat2)
        manager.add_satellite(sat3)
        link = manager.create_and_add_inter_satellite_link_connection(sat1, sat2)

        wrong_terminal = sat3.optical_link_terminals[0]

        with pytest.raises(OpticalLinkTerminalNotFoundError):
            manager.bind_optical_inter_satellite_links(
                sat1,
                sat2,
                wrong_terminal,
                sat2.optical_link_terminals[0],
                link,
            )


# ===========================================================================
# GSL creation / removal
# ===========================================================================


class TestGSLManagement:

    def test_create_gsl_adds_to_simulation(self, manager):
        sat = create_fake_satellite_with_object_id(1)
        gs = create_fake_ground_station_with_object_id(1)
        manager.add_satellite(sat)
        manager.add_ground_station(gs)

        link = manager.create_and_add_ground_station_link_connection(sat, gs)

        assert link in manager.simulation.ground_station_links
        assert link in sat.links
        assert link in gs.links

    def test_create_gsl_publishes_created_event(self, manager_with_event_bus):
        bus = manager_with_event_bus.event_bus
        sat = create_fake_satellite_with_object_id(1)
        gs = create_fake_ground_station_with_object_id(1)
        manager_with_event_bus.add_satellite(sat)
        manager_with_event_bus.add_ground_station(gs)

        manager_with_event_bus.create_and_add_ground_station_link_connection(sat, gs)

        assert isinstance(bus.publish.call_args[0][0], GSLCreatedEvent)

    def test_remove_gsl_removes_from_simulation(self, manager):
        sat = create_fake_satellite_with_object_id(1)
        gs = create_fake_ground_station_with_object_id(1)
        manager.add_satellite(sat)
        manager.add_ground_station(gs)
        link = manager.create_and_add_ground_station_link_connection(sat, gs)

        manager.remove_ground_station_link(link)

        assert link not in manager.simulation.ground_station_links
        assert link not in sat.links
        assert link not in gs.links

    def test_remove_gsl_publishes_removed_event(self, manager_with_event_bus):
        bus = manager_with_event_bus.event_bus
        sat = create_fake_satellite_with_object_id(1)
        gs = create_fake_ground_station_with_object_id(1)
        manager_with_event_bus.add_satellite(sat)
        manager_with_event_bus.add_ground_station(gs)
        link = manager_with_event_bus.create_and_add_ground_station_link_connection(
            sat, gs
        )
        bus.publish.reset_mock()

        manager_with_event_bus.remove_ground_station_link(link)

        assert isinstance(bus.publish.call_args[0][0], GSLRemovedEvent)


# ===========================================================================
# UTL creation / removal
# ===========================================================================


class TestUTLManagement:

    def test_create_utl_adds_to_simulation(self, manager):
        sat = create_fake_satellite_with_object_id(1)
        ut = create_fake_user_terminal_with_object_id(1)
        manager.add_satellite(sat)
        manager.add_user_terminals(ut)

        link = manager.create_and_add_user_terminal_link_connection(sat, ut)

        assert link in manager.simulation.user_terminal_links
        assert link in sat.links
        assert link in ut.links

    def test_create_utl_publishes_created_event(self, manager_with_event_bus):
        bus = manager_with_event_bus.event_bus
        sat = create_fake_satellite_with_object_id(1)
        ut = create_fake_user_terminal_with_object_id(1)
        manager_with_event_bus.add_satellite(sat)
        manager_with_event_bus.add_user_terminals(ut)

        manager_with_event_bus.create_and_add_user_terminal_link_connection(sat, ut)

        assert isinstance(bus.publish.call_args[0][0], UTLCreatedEvent)

    def test_remove_utl_removes_from_simulation(self, manager):
        sat = create_fake_satellite_with_object_id(1)
        ut = create_fake_user_terminal_with_object_id(1)
        manager.add_satellite(sat)
        manager.add_user_terminals(ut)
        link = manager.create_and_add_user_terminal_link_connection(sat, ut)

        manager.remove_user_terminal_link(link)

        assert link not in manager.simulation.user_terminal_links
        assert link not in sat.links
        assert link not in ut.links

    def test_remove_utl_publishes_removed_event(self, manager_with_event_bus):
        bus = manager_with_event_bus.event_bus
        sat = create_fake_satellite_with_object_id(1)
        ut = create_fake_user_terminal_with_object_id(1)
        manager_with_event_bus.add_satellite(sat)
        manager_with_event_bus.add_user_terminals(ut)
        link = manager_with_event_bus.create_and_add_user_terminal_link_connection(
            sat, ut
        )
        bus.publish.reset_mock()

        manager_with_event_bus.remove_user_terminal_link(link)

        assert isinstance(bus.publish.call_args[0][0], UTLRemovedEvent)


# ===========================================================================
# get_all_links
# ===========================================================================


class TestGetAllLinks:

    def test_get_all_links_aggregates_all_types(self, manager):
        assert len(manager.get_all_links()) == 0

        sat1 = create_fake_satellite_with_object_id(1)
        sat2 = create_fake_satellite_with_object_id(2)
        gs = create_fake_ground_station_with_object_id(1)
        ut = create_fake_user_terminal_with_object_id(1)
        manager.add_satellite(sat1)
        manager.add_satellite(sat2)
        manager.add_ground_station(gs)
        manager.add_user_terminals(ut)

        manager.create_and_add_inter_satellite_link_connection(sat1, sat2)
        manager.create_and_add_ground_station_link_connection(sat1, gs)
        manager.create_and_add_user_terminal_link_connection(sat2, ut)

        assert len(manager.get_all_links()) == 3


# ===========================================================================
# update_inter_satellite_links — strategy integration
# ===========================================================================


class TestUpdateInterSatelliteLinks:

    def _make_strategy(self, result: InterSatelliteConnectivityResult):
        strategy = MagicMock()
        strategy.compute_strategy.return_value = result
        return strategy

    def test_raises_when_no_strategy_set(self, manager):
        with pytest.raises(ValueError):
            manager.update_inter_satellite_links()

    def test_obsolete_links_are_removed(self, manager):
        sat1 = create_fake_satellite_with_object_id(1)
        sat2 = create_fake_satellite_with_object_id(2)
        manager.add_satellite(sat1)
        manager.add_satellite(sat2)
        link = manager.create_and_add_inter_satellite_link_connection(sat1, sat2)

        result = InterSatelliteConnectivityResult(
            obsolete_links=[make_link_association(sat1, sat2, link=link)],
            new_links=[],
            updated_links=[],
        )
        manager.inter_satellite_link_connection_strategy = self._make_strategy(result)
        manager.update_inter_satellite_links()

        assert link not in manager.simulation.inter_satellite_links

    def test_new_links_are_created(self, manager):
        sat1 = create_fake_satellite_with_object_id(1)
        sat2 = create_fake_satellite_with_object_id(2)
        manager.add_satellite(sat1)
        manager.add_satellite(sat2)

        terminal_a = sat1.optical_link_terminals[0]
        terminal_b = sat2.optical_link_terminals[0]

        result = InterSatelliteConnectivityResult(
            new_links=[
                make_link_association(
                    sat1, sat2, terminal_a=terminal_a, terminal_b=terminal_b
                )
            ],
            obsolete_links=[],
            updated_links=[],
        )
        manager.inter_satellite_link_connection_strategy = self._make_strategy(result)
        manager.update_inter_satellite_links()

        assert len(manager.simulation.inter_satellite_links) == 1
        assert manager.simulation.inter_satellite_links[0].source == sat1

    def test_updated_links_refresh_constraints(self, manager):
        sat1 = create_fake_satellite_with_object_id(1)
        sat2 = create_fake_satellite_with_object_id(2)
        manager.add_satellite(sat1)
        manager.add_satellite(sat2)
        link = manager.create_and_add_inter_satellite_link_connection(sat1, sat2)

        result = InterSatelliteConnectivityResult(
            updated_links=[make_link_association(sat1, sat2, link=link)],
            new_links=[],
            obsolete_links=[],
        )
        manager.inter_satellite_link_connection_strategy = self._make_strategy(result)
        manager.update_inter_satellite_links()

        assert link.source_constraint is not None
        assert link.destination_constraint is not None

    def test_updated_link_publishes_isl_updated_event(self, manager_with_event_bus):
        bus = manager_with_event_bus.event_bus
        sat1 = create_fake_satellite_with_object_id(1)
        sat2 = create_fake_satellite_with_object_id(2)
        manager_with_event_bus.add_satellite(sat1)
        manager_with_event_bus.add_satellite(sat2)
        link = manager_with_event_bus.create_and_add_inter_satellite_link_connection(
            sat1, sat2
        )
        bus.publish.reset_mock()

        result = InterSatelliteConnectivityResult(
            updated_links=[make_link_association(sat1, sat2, link=link)],
            new_links=[],
            obsolete_links=[],
        )
        manager_with_event_bus.inter_satellite_link_connection_strategy = (
            self._make_strategy(result)
        )
        manager_with_event_bus.update_inter_satellite_links()

        events = [call[0][0] for call in bus.publish.call_args_list]
        assert any(isinstance(e, ISLUpdatedEvent) for e in events)

    def test_obsolete_then_new_does_not_raise(self, manager):
        """
        Regression: a link obsoleted in one tick and a new one created for the
        same pair must not cause list.remove errors.
        """
        sat1 = create_fake_satellite_with_object_id(1)
        sat2 = create_fake_satellite_with_object_id(2)
        manager.add_satellite(sat1)
        manager.add_satellite(sat2)
        link = manager.create_and_add_inter_satellite_link_connection(sat1, sat2)

        terminal_a = sat1.optical_link_terminals[0]
        terminal_b = sat2.optical_link_terminals[0]

        result = InterSatelliteConnectivityResult(
            obsolete_links=[make_link_association(sat1, sat2, link=link)],
            new_links=[
                make_link_association(
                    sat1, sat2, terminal_a=terminal_a, terminal_b=terminal_b
                )
            ],
            updated_links=[],
        )
        manager.inter_satellite_link_connection_strategy = self._make_strategy(result)
        manager.update_inter_satellite_links()

        assert len(manager.simulation.inter_satellite_links) == 1


class TestCascadeRemoval:

    def test_remove_satellite_cascade_removes_isl(self, manager):
        sat1 = create_fake_satellite_with_object_id(1)
        sat2 = create_fake_satellite_with_object_id(2)
        manager.add_satellite(sat1)
        manager.add_satellite(sat2)
        link = manager.create_and_add_inter_satellite_link_connection(sat1, sat2)

        manager.remove_cascade_topology_object(sat1)

        assert link not in manager.simulation.inter_satellite_links
        assert sat1 not in manager.simulation.satellites
        assert link not in sat2.links

    def test_remove_satellite_cascade_removes_gsl(self, manager):
        sat = create_fake_satellite_with_object_id(1)
        gs = create_fake_ground_station_with_object_id(1)
        manager.add_satellite(sat)
        manager.add_ground_station(gs)
        link = manager.create_and_add_ground_station_link_connection(sat, gs)

        manager.remove_cascade_topology_object(sat)

        assert link not in manager.simulation.ground_station_links
        assert sat not in manager.simulation.satellites
        assert link not in gs.links

    def test_remove_satellite_cascade_removes_utl(self, manager):
        sat = create_fake_satellite_with_object_id(1)
        ut = create_fake_user_terminal_with_object_id(1)
        manager.add_satellite(sat)
        manager.add_user_terminals(ut)
        link = manager.create_and_add_user_terminal_link_connection(sat, ut)

        manager.remove_cascade_topology_object(sat)

        assert link not in manager.simulation.user_terminal_links
        assert sat not in manager.simulation.satellites
        assert link not in ut.links

    def test_remove_satellite_cascade_removes_multiple_links(self, manager):
        sat1 = create_fake_satellite_with_object_id(1)
        sat2 = create_fake_satellite_with_object_id(2)
        sat3 = create_fake_satellite_with_object_id(3)
        gs = create_fake_ground_station_with_object_id(1)
        manager.add_satellite(sat1)
        manager.add_satellite(sat2)
        manager.add_satellite(sat3)
        manager.add_ground_station(gs)

        isl_12 = manager.create_and_add_inter_satellite_link_connection(sat1, sat2)
        isl_13 = manager.create_and_add_inter_satellite_link_connection(sat1, sat3)
        gsl = manager.create_and_add_ground_station_link_connection(sat1, gs)

        manager.remove_cascade_topology_object(sat1)

        assert isl_12 not in manager.simulation.inter_satellite_links
        assert isl_13 not in manager.simulation.inter_satellite_links
        assert gsl not in manager.simulation.ground_station_links
        assert sat1 not in manager.simulation.satellites

        # Peer objects must also have had the links removed from their lists
        assert isl_12 not in sat2.links
        assert isl_13 not in sat3.links
        assert gsl not in gs.links

    def test_remove_satellite_cascade_unbinds_terminals(self, manager):
        sat1 = create_fake_satellite_with_object_id(1)
        sat2 = create_fake_satellite_with_object_id(2)
        manager.add_satellite(sat1)
        manager.add_satellite(sat2)

        terminal_a = sat1.optical_link_terminals[0]
        terminal_b = sat2.optical_link_terminals[0]

        manager.create_and_add_inter_satellite_link_connection(
            sat1,
            sat2,
            terminal_a=terminal_a,
            terminal_b=terminal_b,
        )

        manager.remove_cascade_topology_object(sat1)

        assert terminal_a.link is None
        assert terminal_b.link is None

    def test_remove_ground_station_cascade_removes_gsl(self, manager):
        sat = create_fake_satellite_with_object_id(1)
        gs = create_fake_ground_station_with_object_id(1)
        manager.add_satellite(sat)
        manager.add_ground_station(gs)
        link = manager.create_and_add_ground_station_link_connection(sat, gs)

        manager.remove_cascade_topology_object(gs)

        assert link not in manager.simulation.ground_station_links
        assert gs not in manager.simulation.ground_stations
        assert link not in sat.links

    def test_remove_user_terminal_cascade_removes_utl(self, manager):
        sat = create_fake_satellite_with_object_id(1)
        ut = create_fake_user_terminal_with_object_id(1)
        manager.add_satellite(sat)
        manager.add_user_terminals(ut)
        link = manager.create_and_add_user_terminal_link_connection(sat, ut)

        manager.remove_cascade_topology_object(ut)

        assert link not in manager.simulation.user_terminal_links
        assert ut not in manager.simulation.user_terminals
        assert link not in sat.links

    def test_remove_cascade_by_id_removes_satellite_and_links(self, manager):
        sat1 = create_fake_satellite_with_object_id(1)
        sat2 = create_fake_satellite_with_object_id(2)
        manager.add_satellite(sat1)
        manager.add_satellite(sat2)
        link = manager.create_and_add_inter_satellite_link_connection(sat1, sat2)

        removed = manager.remove_cascade_topology_object_by_id(sat1.topology_uniq_id)

        assert sat1 not in manager.simulation.satellites
        assert link not in manager.simulation.inter_satellite_links
        assert sat1 in removed
        assert link in removed

    def test_remove_cascade_by_id_raises_for_unknown_id(self, manager):
        with pytest.raises(TopologyObjectNotFoundError):
            manager.remove_cascade_topology_object_by_id(99999)

    def test_remove_satellite_cascade_leaves_unrelated_links_intact(self, manager):
        """Removing sat1 must not affect the link between sat2 and sat3."""
        sat1 = create_fake_satellite_with_object_id(1)
        sat2 = create_fake_satellite_with_object_id(2)
        sat3 = create_fake_satellite_with_object_id(3)
        manager.add_satellite(sat1)
        manager.add_satellite(sat2)
        manager.add_satellite(sat3)

        manager.create_and_add_inter_satellite_link_connection(sat1, sat2)
        unrelated = manager.create_and_add_inter_satellite_link_connection(sat2, sat3)

        manager.remove_cascade_topology_object(sat1)

        assert unrelated in manager.simulation.inter_satellite_links
        assert unrelated in sat2.links
        assert unrelated in sat3.links
