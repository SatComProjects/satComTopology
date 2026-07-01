import asyncio
import datetime
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from sat_com_application.event_bus.events import (
    ISLCreatedEvent,
    GSLCreatedEvent,
    UTLCreatedEvent,
    ISLRemovedEvent,
    GSLRemovedEvent,
    UTLRemovedEvent,
    GSLUpdatedEvent,
    UTLUpdatedEvent,
    ISLUpdatedEvent,
)
from sat_com_application.simulation_manager import SimulationManager
from sat_com_connectivity.inter_satellite_link_connectivity.models import (
    LinkAssociation,
    InterSatelliteConnectivityResult,
    OpticISLVisibilityConstraintResult,
)
from sat_com_connectivity.ground_object_to_space_connectivity.models import (
    GroundToSpaceConstraints,
)
from sat_com_model.models import (
    Satellite,
    GroundStation,
    UserTerminal,
    InterSatelliteLink,
    GroundStationLink,
    UserTerminalLink,
    Simulation,
    OpticalConstraint,
    InterSatelliteLinkDirection,
)
from tests.sat_com_connectivity_tests.test_addressing_plans import make_terminal


def make_simulation_manager(with_event_bus=True, with_time_manager=True):
    simulation = MagicMock(spec=Simulation)
    simulation.inter_satellite_links = []
    simulation.ground_station_links = []
    simulation.user_terminal_links = []
    simulation.ground_object_links = []
    simulation.satellites = []
    simulation.ground_stations = []
    simulation.user_terminals = []
    simulation.ground_object_domains = []
    simulation.walker_shells = []
    simulation.request_an_id.return_value = 1
    simulation.distance_model = MagicMock()

    event_bus = None
    if with_event_bus:
        event_bus = MagicMock()
        event_bus.publish = AsyncMock()

    manager = SimulationManager(simulation=simulation, event_bus=event_bus)

    if with_time_manager:
        time_manager = MagicMock()
        time_manager.current_time = datetime.datetime(2024, 1, 1, 12, 0, 0)
        manager.time_manager = time_manager

    return manager


def make_satellite(topology_uniq_id=1) -> Satellite:
    sat = MagicMock(spec=Satellite)
    sat.topology_uniq_id = topology_uniq_id
    sat.links = []
    return sat


def make_ground_station(topology_uniq_id=10) -> GroundStation:
    gs = MagicMock(spec=GroundStation)
    gs.topology_uniq_id = topology_uniq_id
    gs.links = []
    return gs


def make_user_terminal(topology_uniq_id=20) -> UserTerminal:
    ut = MagicMock(spec=UserTerminal)
    ut.topology_uniq_id = topology_uniq_id
    ut.links = []
    return ut


def make_isl(sat_a, sat_b) -> InterSatelliteLink:
    link = InterSatelliteLink()
    link.connect(sat_a, sat_b)
    return link


def make_gsl(satellite, ground_station) -> GroundStationLink:
    link = GroundStationLink()
    link.connect(satellite, ground_station)
    return link


def make_utl(satellite, user_terminal) -> UserTerminalLink:
    link = UserTerminalLink()
    link.connect(satellite, user_terminal)
    return link


def get_published_event(manager) -> object:
    """Return the single event published to the event bus."""
    assert manager.event_bus.publish.call_count == 1
    args, _ = manager.event_bus.publish.call_args
    return args[0]


def get_all_published_events(manager) -> list:
    return [call_args[0][0] for call_args in manager.event_bus.publish.call_args_list]


def run_async(coro):
    """Run a coroutine in a fresh event loop for testing."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# ISL — Created
# ---------------------------------------------------------------------------


class TestISLCreatedEvent:

    def test_isl_created_event_is_published(self):
        manager = make_simulation_manager()
        sat_a = make_satellite(topology_uniq_id=1)
        sat_b = make_satellite(topology_uniq_id=2)

        with patch("asyncio.run") as mock_run:
            manager.create_and_add_inter_satellite_link_connection(sat_a, sat_b)
            assert mock_run.called

    def test_isl_created_event_type(self):
        manager = make_simulation_manager()
        sat_a = make_satellite(topology_uniq_id=1)
        sat_b = make_satellite(topology_uniq_id=2)

        def capture_run(coro):
            run_async(coro)

        with patch("asyncio.run", side_effect=capture_run):
            manager.create_and_add_inter_satellite_link_connection(sat_a, sat_b)

        manager.event_bus.publish.assert_called_once()
        event = manager.event_bus.publish.call_args[0][0]
        assert isinstance(event, ISLCreatedEvent)

    def test_isl_created_event_contains_correct_satellite_ids(self):
        manager = make_simulation_manager()
        sat_a = make_satellite(topology_uniq_id=1)
        sat_b = make_satellite(topology_uniq_id=2)

        def capture_run(coro):
            run_async(coro)

        with patch("asyncio.run", side_effect=capture_run):
            manager.create_and_add_inter_satellite_link_connection(sat_a, sat_b)

        event = manager.event_bus.publish.call_args[0][0]
        assert event.satellite_a_id == 1
        assert event.satellite_b_id == 2

    def test_isl_created_event_has_sim_time(self):
        manager = make_simulation_manager()
        sat_a = make_satellite(topology_uniq_id=1)
        sat_b = make_satellite(topology_uniq_id=2)

        def capture_run(coro):
            run_async(coro)

        with patch("asyncio.run", side_effect=capture_run):
            manager.create_and_add_inter_satellite_link_connection(sat_a, sat_b)

        event = manager.event_bus.publish.call_args[0][0]
        assert event.sim_time == datetime.datetime(2024, 1, 1, 12, 0, 0)

    def test_no_event_published_without_event_bus(self):
        manager = make_simulation_manager(with_event_bus=False)
        sat_a = make_satellite(topology_uniq_id=1)
        sat_b = make_satellite(topology_uniq_id=2)

        with patch("asyncio.run") as mock_run:
            manager.create_and_add_inter_satellite_link_connection(sat_a, sat_b)
            mock_run.assert_not_called()


# ---------------------------------------------------------------------------
# GSL — Created
# ---------------------------------------------------------------------------


class TestGSLCreatedEvent:

    def _create_gsl(self, manager, sat, gs, elevation=30.0, duration=300.0):
        def capture_run(coro):
            run_async(coro)

        with patch("asyncio.run", side_effect=capture_run):
            return manager.create_and_add_ground_station_link_connection(
                satellite=sat,
                ground_station=gs,
                elevation_above_horizon_angle=elevation,
                estimated_link_duration=duration,
            )

    def test_gsl_created_event_type(self):
        manager = make_simulation_manager()
        sat = make_satellite(topology_uniq_id=1)
        gs = make_ground_station(topology_uniq_id=10)
        self._create_gsl(manager, sat, gs)

        event = manager.event_bus.publish.call_args[0][0]
        assert isinstance(event, GSLCreatedEvent)

    def test_gsl_created_event_satellite_id(self):
        manager = make_simulation_manager()
        sat = make_satellite(topology_uniq_id=5)
        gs = make_ground_station(topology_uniq_id=10)
        self._create_gsl(manager, sat, gs)

        event = manager.event_bus.publish.call_args[0][0]
        assert event.satellite_id == 5

    def test_gsl_created_event_ground_station_id(self):
        manager = make_simulation_manager()
        sat = make_satellite(topology_uniq_id=5)
        gs = make_ground_station(topology_uniq_id=10)
        self._create_gsl(manager, sat, gs)

        event = manager.event_bus.publish.call_args[0][0]
        assert event.ground_station_id == 10

    def test_gsl_created_event_elevation_angle(self):
        manager = make_simulation_manager()
        sat = make_satellite(topology_uniq_id=1)
        gs = make_ground_station(topology_uniq_id=10)
        self._create_gsl(manager, sat, gs, elevation=45.0)

        event = manager.event_bus.publish.call_args[0][0]
        assert event.elevation_angle == 45.0

    def test_gsl_created_event_estimated_duration(self):
        manager = make_simulation_manager()
        sat = make_satellite(topology_uniq_id=1)
        gs = make_ground_station(topology_uniq_id=10)
        self._create_gsl(manager, sat, gs, duration=600.0)

        event = manager.event_bus.publish.call_args[0][0]
        assert event.estimated_duration == 600.0

    def test_gsl_created_event_has_sim_time(self):
        manager = make_simulation_manager()
        sat = make_satellite(topology_uniq_id=1)
        gs = make_ground_station(topology_uniq_id=10)
        self._create_gsl(manager, sat, gs)

        event = manager.event_bus.publish.call_args[0][0]
        assert event.sim_time == datetime.datetime(2024, 1, 1, 12, 0, 0)


# ---------------------------------------------------------------------------
# UTL — Created
# ---------------------------------------------------------------------------


class TestUTLCreatedEvent:

    def _create_utl(self, manager, sat, ut, elevation=25.0, duration=200.0):
        def capture_run(coro):
            run_async(coro)

        with patch("asyncio.run", side_effect=capture_run):
            return manager.create_and_add_user_terminal_link_connection(
                satellite=sat,
                user_terminal=ut,
                elevation_above_horizon_angle=elevation,
                estimated_link_duration=duration,
            )

    def test_utl_created_event_type(self):
        manager = make_simulation_manager()
        sat = make_satellite(topology_uniq_id=1)
        ut = make_user_terminal(topology_uniq_id=20)
        self._create_utl(manager, sat, ut)

        event = manager.event_bus.publish.call_args[0][0]
        assert isinstance(event, UTLCreatedEvent)

    def test_utl_created_event_satellite_id(self):
        manager = make_simulation_manager()
        sat = make_satellite(topology_uniq_id=3)
        ut = make_user_terminal(topology_uniq_id=20)
        self._create_utl(manager, sat, ut)

        event = manager.event_bus.publish.call_args[0][0]
        assert event.satellite_id == 3

    def test_utl_created_event_user_terminal_id(self):
        manager = make_simulation_manager()
        sat = make_satellite(topology_uniq_id=1)
        ut = make_user_terminal(topology_uniq_id=99)
        self._create_utl(manager, sat, ut)

        event = manager.event_bus.publish.call_args[0][0]
        assert event.user_terminal_id == 99

    def test_utl_created_event_elevation_angle(self):
        manager = make_simulation_manager()
        sat = make_satellite(topology_uniq_id=1)
        ut = make_user_terminal(topology_uniq_id=20)
        self._create_utl(manager, sat, ut, elevation=15.0)

        event = manager.event_bus.publish.call_args[0][0]
        assert event.elevation_above_horizon_angle == 15.0

    def test_utl_created_event_estimated_duration(self):
        manager = make_simulation_manager()
        sat = make_satellite(topology_uniq_id=1)
        ut = make_user_terminal(topology_uniq_id=20)
        self._create_utl(manager, sat, ut, duration=120.0)

        event = manager.event_bus.publish.call_args[0][0]
        assert event.estimated_link_duration == 120.0


# ---------------------------------------------------------------------------
# ISL — Removed
# ---------------------------------------------------------------------------


class TestISLRemovedEvent:

    def test_isl_removed_event_type(self):
        manager = make_simulation_manager()
        sat_a = make_satellite(topology_uniq_id=1)
        sat_b = make_satellite(topology_uniq_id=2)
        link = make_isl(sat_a, sat_b)
        sat_a.links.append(link)
        sat_b.links.append(link)
        manager.simulation.inter_satellite_links.append(link)

        def capture_run(coro):
            run_async(coro)

        with patch("asyncio.run", side_effect=capture_run):
            manager.remove_link(link)

        event = manager.event_bus.publish.call_args[0][0]
        assert isinstance(event, ISLRemovedEvent)

    def test_isl_removed_event_satellite_ids(self):
        manager = make_simulation_manager()
        sat_a = make_satellite(topology_uniq_id=1)
        sat_b = make_satellite(topology_uniq_id=2)
        link = make_isl(sat_a, sat_b)
        sat_a.links.append(link)
        sat_b.links.append(link)
        manager.simulation.inter_satellite_links.append(link)

        def capture_run(coro):
            run_async(coro)

        with patch("asyncio.run", side_effect=capture_run):
            manager.remove_link(link)

        event = manager.event_bus.publish.call_args[0][0]
        assert event.satellite_a_id == 1
        assert event.satellite_b_id == 2


# ---------------------------------------------------------------------------
# GSL — Removed
# ---------------------------------------------------------------------------


class TestGSLRemovedEvent:

    def test_gsl_removed_event_type(self):
        manager = make_simulation_manager()
        sat = make_satellite(topology_uniq_id=1)
        gs = make_ground_station(topology_uniq_id=10)
        link = make_gsl(sat, gs)
        sat.links.append(link)
        gs.links.append(link)
        manager.simulation.ground_station_links.append(link)

        def capture_run(coro):
            run_async(coro)

        with patch("asyncio.run", side_effect=capture_run):
            manager.remove_link(link)

        event = manager.event_bus.publish.call_args[0][0]
        assert isinstance(event, GSLRemovedEvent)

    def test_gsl_removed_event_ids(self):
        manager = make_simulation_manager()
        sat = make_satellite(topology_uniq_id=5)
        gs = make_ground_station(topology_uniq_id=15)
        link = make_gsl(sat, gs)
        sat.links.append(link)
        gs.links.append(link)
        manager.simulation.ground_station_links.append(link)

        def capture_run(coro):
            run_async(coro)

        with patch("asyncio.run", side_effect=capture_run):
            manager.remove_link(link)

        event = manager.event_bus.publish.call_args[0][0]
        assert event.satellite_id == 5
        assert event.ground_station_id == 15


# ---------------------------------------------------------------------------
# UTL — Removed
# ---------------------------------------------------------------------------


class TestUTLRemovedEvent:

    def test_utl_removed_event_type(self):
        manager = make_simulation_manager()
        sat = make_satellite(topology_uniq_id=1)
        ut = make_user_terminal(topology_uniq_id=20)
        link = make_utl(sat, ut)
        sat.links.append(link)
        ut.links.append(link)
        manager.simulation.user_terminal_links.append(link)

        def capture_run(coro):
            run_async(coro)

        with patch("asyncio.run", side_effect=capture_run):
            manager.remove_link(link)

        event = manager.event_bus.publish.call_args[0][0]
        assert isinstance(event, UTLRemovedEvent)

    def test_utl_removed_event_ids(self):
        manager = make_simulation_manager()
        sat = make_satellite(topology_uniq_id=3)
        ut = make_user_terminal(topology_uniq_id=25)
        link = make_utl(sat, ut)
        sat.links.append(link)
        ut.links.append(link)
        manager.simulation.user_terminal_links.append(link)

        def capture_run(coro):
            run_async(coro)

        with patch("asyncio.run", side_effect=capture_run):
            manager.remove_link(link)

        event = manager.event_bus.publish.call_args[0][0]
        assert event.satellite_id == 3
        assert event.user_terminal_id == 25


# ---------------------------------------------------------------------------
# GSL — Updated
# ---------------------------------------------------------------------------


class TestGSLUpdatedEvent:

    def _make_gsl_link(self, sat_id=1, gs_id=10):
        sat = make_satellite(topology_uniq_id=sat_id)
        gs = make_ground_station(topology_uniq_id=gs_id)
        link = make_gsl(sat, gs)
        return link

    def test_gsl_updated_event_type(self):
        manager = make_simulation_manager()
        link = self._make_gsl_link()

        def capture_run(coro):
            run_async(coro)

        with patch("asyncio.run", side_effect=capture_run):
            manager.update_ground_station_link(
                ground_to_space_link=link,
                ground_to_space_constraints=GroundToSpaceConstraints(
                    elevation_angle_above_horizon=40.0,
                    estimated_connection_time=500.0,
                    distance_km=800.0,
                ),
            )

        event = manager.event_bus.publish.call_args[0][0]
        assert isinstance(event, GSLUpdatedEvent)

    def test_gsl_updated_event_elevation(self):
        manager = make_simulation_manager()
        link = self._make_gsl_link(sat_id=2, gs_id=11)

        def capture_run(coro):
            run_async(coro)

        with patch("asyncio.run", side_effect=capture_run):
            manager.update_ground_station_link(
                ground_to_space_link=link,
                ground_to_space_constraints=GroundToSpaceConstraints(
                    elevation_angle_above_horizon=55.0
                ),
            )

        event = manager.event_bus.publish.call_args[0][0]
        assert event.elevation_above_horizon_angle == 55.0

    def test_gsl_updated_event_distance(self):
        manager = make_simulation_manager()
        link = self._make_gsl_link()

        def capture_run(coro):
            run_async(coro)

        with patch("asyncio.run", side_effect=capture_run):
            manager.update_ground_station_link(
                ground_to_space_link=link,
                ground_to_space_constraints=GroundToSpaceConstraints(
                    distance_km=1200.0
                ),
            )

        event = manager.event_bus.publish.call_args[0][0]
        assert event.distance_km == 1200.0

    def test_gsl_updated_event_estimated_duration(self):
        manager = make_simulation_manager()
        link = self._make_gsl_link()

        def capture_run(coro):
            run_async(coro)

        with patch("asyncio.run", side_effect=capture_run):
            manager.update_ground_station_link(
                ground_to_space_link=link,
                ground_to_space_constraints=GroundToSpaceConstraints(
                    estimated_connection_time=250.0
                ),
            )

        event = manager.event_bus.publish.call_args[0][0]
        assert event.estimated_link_duration == 250.0

    def test_gsl_updated_missing_fields_default_to_minus_one(self):
        manager = make_simulation_manager()
        link = self._make_gsl_link()

        def capture_run(coro):
            run_async(coro)

        with patch("asyncio.run", side_effect=capture_run):
            manager.update_ground_station_link(
                ground_to_space_link=link,
                ground_to_space_constraints=GroundToSpaceConstraints(),
            )

        event = manager.event_bus.publish.call_args[0][0]
        assert event.elevation_above_horizon_angle == -1
        assert event.distance_km == -1
        assert event.estimated_link_duration == -1

    def test_gsl_updated_event_satellite_and_ground_station_ids(self):
        manager = make_simulation_manager()
        link = self._make_gsl_link(sat_id=7, gs_id=42)

        def capture_run(coro):
            run_async(coro)

        with patch("asyncio.run", side_effect=capture_run):
            manager.update_ground_station_link(
                ground_to_space_link=link,
                ground_to_space_constraints=GroundToSpaceConstraints(),
            )

        event = manager.event_bus.publish.call_args[0][0]
        assert event.satellite_id == 7
        assert event.ground_station_id == 42


# ---------------------------------------------------------------------------
# UTL — Updated
# ---------------------------------------------------------------------------


class TestUTLUpdatedEvent:

    def _make_utl_link(self, sat_id=1, ut_id=20):
        sat = make_satellite(topology_uniq_id=sat_id)
        ut = make_user_terminal(topology_uniq_id=ut_id)
        link = make_utl(sat, ut)
        return link

    def test_utl_updated_event_type(self):
        manager = make_simulation_manager()
        link = self._make_utl_link()

        def capture_run(coro):
            run_async(coro)

        with patch("asyncio.run", side_effect=capture_run):
            manager.update_user_terminal_link(
                user_terminal_link=link,
                ground_to_space_constraints=GroundToSpaceConstraints(
                    elevation_angle_above_horizon=30.0,
                    estimated_connection_time=400.0,
                    distance_km=600.0,
                ),
            )

        event = manager.event_bus.publish.call_args[0][0]
        assert isinstance(event, UTLUpdatedEvent)

    def test_utl_updated_event_ids(self):
        manager = make_simulation_manager()
        link = self._make_utl_link(sat_id=8, ut_id=33)

        def capture_run(coro):
            run_async(coro)

        with patch("asyncio.run", side_effect=capture_run):
            manager.update_user_terminal_link(
                user_terminal_link=link,
                ground_to_space_constraints=GroundToSpaceConstraints(),
            )

        event = manager.event_bus.publish.call_args[0][0]
        assert event.satellite_id == 8
        assert event.user_terminal_id == 33

    def test_utl_updated_missing_fields_default_to_minus_one(self):
        manager = make_simulation_manager()
        link = self._make_utl_link()

        def capture_run(coro):
            run_async(coro)

        with patch("asyncio.run", side_effect=capture_run):
            manager.update_user_terminal_link(
                user_terminal_link=link,
                ground_to_space_constraints=GroundToSpaceConstraints(),
            )

        event = manager.event_bus.publish.call_args[0][0]
        assert event.elevation_above_horizon_angle == -1
        assert event.distance_km == -1
        assert event.estimated_link_duration == -1


# ---------------------------------------------------------------------------
# ISL — Updated
# ---------------------------------------------------------------------------
def make_constraint() -> OpticalConstraint:
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
        range_rate=5,
        los_clear=True,
        los_min_altitude_km=90,
        relative_azimuth_angle_degree=0.0,
    )


def make_link_association(sat_a, sat_b, link, terminal_a=None, terminal_b=None):
    return LinkAssociation(
        satellite_a=sat_a,
        terminal_a=terminal_a or make_terminal(),
        satellite_b=sat_b,
        terminal_b=terminal_b or make_terminal(),
        direction=InterSatelliteLinkDirection.ORBITAL,
        link=link,
        constraint_a_to_b=make_visibility_constraint(),
        constraint_b_to_a=make_visibility_constraint(),
    )


class TestISLUpdatedEvent:

    def _make_strategy_mock(self, updated=None, new=None, obsolete=None):
        result = InterSatelliteConnectivityResult(
            updated_links=updated or [],
            new_links=new or [],
            obsolete_links=obsolete or [],
        )
        strategy = MagicMock()
        strategy.compute_strategy.return_value = result
        return strategy

    def test_isl_updated_event_type(self):
        manager = make_simulation_manager()
        sat_a = make_satellite(topology_uniq_id=1)
        sat_b = make_satellite(topology_uniq_id=2)
        link = make_isl(sat_a, sat_b)

        manager.inter_satellite_link_connection_strategy = self._make_strategy_mock(
            updated=[make_link_association(sat_a, sat_b, link)]
        )
        manager.simulation.inter_satellite_links.append(link)

        manager.update_inter_satellite_links()

        event = manager.event_bus.publish.call_args[0][0]
        assert isinstance(event, ISLUpdatedEvent)

    def test_isl_updated_event_ids(self):
        manager = make_simulation_manager()
        sat_a = make_satellite(topology_uniq_id=4)
        sat_b = make_satellite(topology_uniq_id=7)
        link = make_isl(sat_a, sat_b)

        manager.inter_satellite_link_connection_strategy = self._make_strategy_mock(
            updated=[make_link_association(sat_a, sat_b, link)]
        )
        manager.simulation.inter_satellite_links.append(link)

        manager.update_inter_satellite_links()

        event = manager.event_bus.publish.call_args[0][0]
        assert event.satellite_a_id == 4
        assert event.satellite_b_id == 7

    def test_isl_updated_event_constraints_are_applied(self):
        """Optical constraints from the association are set on the link."""
        manager = make_simulation_manager()
        sat_a = make_satellite(topology_uniq_id=1)
        sat_b = make_satellite(topology_uniq_id=2)
        link = make_isl(sat_a, sat_b)

        manager.inter_satellite_link_connection_strategy = self._make_strategy_mock(
            updated=[make_link_association(sat_a, sat_b, link)]
        )
        manager.simulation.inter_satellite_links.append(link)

        manager.update_inter_satellite_links()

        assert link.source_constraint is not None
        assert link.source_constraint.range_distance_km == pytest.approx(500.0)


# ---------------------------------------------------------------------------
# No event bus — no crash
# ---------------------------------------------------------------------------


class TestNoEventBus:

    def test_create_isl_without_event_bus_does_not_raise(self):
        manager = make_simulation_manager(with_event_bus=False)
        sat_a = make_satellite(1)
        sat_b = make_satellite(2)
        manager.create_and_add_inter_satellite_link_connection(sat_a, sat_b)

    def test_create_gsl_without_event_bus_does_not_raise(self):
        manager = make_simulation_manager(with_event_bus=False)
        sat = make_satellite(1)
        gs = make_ground_station(10)
        manager.create_and_add_ground_station_link_connection(sat, gs)

    def test_remove_link_without_event_bus_does_not_raise(self):
        manager = make_simulation_manager(with_event_bus=False)
        sat_a = make_satellite(1)
        sat_b = make_satellite(2)
        link = make_isl(sat_a, sat_b)
        sat_a.links.append(link)
        sat_b.links.append(link)
        manager.simulation.inter_satellite_links.append(link)
        manager.remove_link(link)


# ---------------------------------------------------------------------------
# sim_time stamping
# ---------------------------------------------------------------------------


class TestSimTimeStamping:

    def test_event_has_no_sim_time_without_time_manager(self):
        manager = make_simulation_manager(with_time_manager=False)
        sat_a = make_satellite(1)
        sat_b = make_satellite(2)

        def capture_run(coro):
            run_async(coro)

        with patch("asyncio.run", side_effect=capture_run):
            manager.create_and_add_inter_satellite_link_connection(sat_a, sat_b)

        event = manager.event_bus.publish.call_args[0][0]
        assert not hasattr(event, "sim_time") or event.sim_time is None

    def test_event_sim_time_matches_current_time(self):
        manager = make_simulation_manager()
        expected_time = datetime.datetime(2024, 6, 15, 8, 0, 0)
        manager.time_manager.current_time = expected_time

        sat_a = make_satellite(1)
        sat_b = make_satellite(2)

        def capture_run(coro):
            run_async(coro)

        with patch("asyncio.run", side_effect=capture_run):
            manager.create_and_add_inter_satellite_link_connection(sat_a, sat_b)

        event = manager.event_bus.publish.call_args[0][0]
        assert event.sim_time == expected_time
