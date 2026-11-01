"""
BASIC (default) vs ADVANCED optical inter-satellite link model.

BASIC: links follow the addressing plan, terminals are connection slots chosen
from their orientations only, no optical metric is computed, the distance is
the real straight-line distance. ADVANCED: links carry their constraints.
"""

from collections import Counter
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from sat_com_application.event_bus.factories import DefaultISLEventFactory
from sat_com_builder.configuration_manager import BaseConfigurationManager
from sat_com_builder.models import OpticalTerminalProperty, SimulationProperty
from sat_com_connectivity.inter_satellite_link_connectivity.models import (
    LinkAssociation,
)
from sat_com_connectivity.inter_satellite_link_connectivity.strategies import (
    InterShellSSOPriorityConnectivity,
    IntraShellStaticConnectivity,
)
from sat_com_model.models import (
    InterSatelliteLinkDirection,
    OpticalInterSatelliteLinkModel,
)
from tests.sat_com_topology_tests.test_multiple_satellite_configuration import (
    make_basic_4_isl_satellite_installation_intershell_unauthorized,
    make_small_single_walker_shell,
    make_three_isl_configuration,
)

BASIC = OpticalInterSatelliteLinkModel.BASIC
ADVANCED = OpticalInterSatelliteLinkModel.ADVANCED
ADDRESSING_PLANS = (
    "sat_com_connectivity.inter_satellite_link_connectivity.addressing_plans"
)


def _four_isl_walker(model: OpticalInterSatelliteLinkModel | None):
    """10 x 10 Walker Delta, 4 ISL, full mesh. model=None keeps the default."""
    simulation_property = make_small_single_walker_shell(
        make_basic_4_isl_satellite_installation_intershell_unauthorized()
    )
    simulation_property.start_date = "2026-01-01 00:00:00"
    simulation_property.end_date = "2026-01-02 00:00:00"
    if model is not None:
        simulation_property.optical_inter_satellite_link_model = model
    return BaseConfigurationManager(simulation_property=simulation_property)


def _eci_distance_km(link) -> float:
    position = lambda sat: np.asarray(  # noqa: E731
        sat.get_movement_model().get_position_earth_general_inertial(), dtype=float
    )
    return float(np.linalg.norm(position(link.source) - position(link.destination)))


# ---------------------------------------------------------------------------
# Option
# ---------------------------------------------------------------------------


def test_basic_is_the_default():
    assert SimulationProperty().optical_inter_satellite_link_model == BASIC


def test_enable_dynamic_reassignment_was_removed():
    assert "enable_dynamic_reassignment" not in OpticalTerminalProperty.model_fields


def test_strategies_declare_whether_they_compute_metrics():
    assert InterShellSSOPriorityConnectivity.requires_oisl_metrics is True
    assert IntraShellStaticConnectivity.requires_oisl_metrics is False


# ---------------------------------------------------------------------------
# BASIC
# ---------------------------------------------------------------------------


def test_basic_never_computes_optical_metrics():
    def fail(*_, **__):
        raise AssertionError("optical metrics computed in BASIC mode")

    with patch(
        f"{ADDRESSING_PLANS}.compute_OISL_links_from_terminal_pools", fail
    ), patch(f"{ADDRESSING_PLANS}.compute_OISL_constraint_for_known_pair", fail):
        simulation_manager = _four_isl_walker(None).load_simulation()
        simulation_manager.time_manager.tick(seconds=60)

    assert simulation_manager.get_inter_satellites_links()


def test_basic_full_mesh_creates_every_grid_link_on_distinct_terminals():
    simulation_manager = _four_isl_walker(BASIC).load_simulation()
    links = simulation_manager.get_inter_satellites_links()

    # 10 x 10 full mesh: 100 orbital + 100 adjacent links, 4 per satellite,
    # including the wrap-around ones stored as (min id, max id) in the grid.
    directions = Counter(link.inter_satellite_direction for link in links)
    assert directions == {
        InterSatelliteLinkDirection.ORBITAL: 100,
        InterSatelliteLinkDirection.ADJACENT: 100,
    }
    per_satellite = Counter()
    terminals = []
    for link in links:
        per_satellite[link.source.topology_uniq_id] += 1
        per_satellite[link.destination.topology_uniq_id] += 1
        terminals += [link.source_optical_terminal, link.destination_optical_terminal]
    assert set(per_satellite.values()) == {4}
    assert len(set(terminals)) == len(terminals)


def test_basic_orbital_links_use_forward_and_backward_terminals():
    simulation_manager = _four_isl_walker(BASIC).load_simulation()
    for link in simulation_manager.get_inter_satellites_links():
        if link.inter_satellite_direction != InterSatelliteLinkDirection.ORBITAL:
            continue
        descriptors = {
            link.source_optical_terminal.descriptor.name,
            link.destination_optical_terminal.descriptor.name,
        }
        assert descriptors == {"INTRA_PLANE_FORWARD", "INTRA_PLANE_BACKWARD"}


def test_basic_links_have_no_constraints_and_the_real_distance():
    simulation_manager = _four_isl_walker(BASIC).load_simulation()
    simulation_manager.time_manager.tick(seconds=60)

    for link in simulation_manager.get_inter_satellites_links():
        assert link.optical_link_model == BASIC
        assert not link.has_optical_metrics
        assert link.source_constraint is None
        assert link.destination_constraint is None
        assert link.distance_km == pytest.approx(_eci_distance_km(link), rel=1e-12)


def test_basic_topology_does_not_change_over_time():
    simulation_manager = _four_isl_walker(BASIC).load_simulation()
    before = {link.link_id for link in simulation_manager.get_inter_satellites_links()}
    for _ in range(5):
        simulation_manager.time_manager.tick(seconds=600)
    after = {link.link_id for link in simulation_manager.get_inter_satellites_links()}
    assert before == after


def test_basic_checkerboard_three_isl():
    simulation_property = make_three_isl_configuration(10, 10)
    assert simulation_property.optical_inter_satellite_link_model == BASIC
    simulation_manager = BaseConfigurationManager(
        simulation_property=simulation_property
    ).load_simulation()

    per_satellite = Counter()
    for link in simulation_manager.get_inter_satellites_links():
        per_satellite[link.source.topology_uniq_id] += 1
        per_satellite[link.destination.topology_uniq_id] += 1
    assert set(per_satellite.values()) == {3}


def test_events_carry_the_distance_and_the_model():
    simulation_manager = _four_isl_walker(BASIC).load_simulation()
    link = simulation_manager.get_inter_satellites_links()[0]

    factory = DefaultISLEventFactory()
    for event in (factory.created(link), factory.updated(link)):
        assert event.distance_km == link.distance_km
        assert event.optical_link_model == "basic"
        assert event.elevation_a_deg is None


# ---------------------------------------------------------------------------
# ADVANCED
# ---------------------------------------------------------------------------


def test_advanced_links_carry_constraints_and_their_range_as_distance():
    simulation_manager = _four_isl_walker(ADVANCED).load_simulation()
    simulation_manager.time_manager.tick(seconds=60)

    links = simulation_manager.get_inter_satellites_links()
    assert links
    for link in links:
        assert link.has_optical_metrics
        assert link.source_constraint is not None
        assert link.destination_constraint is not None
        assert link.distance_km == link.source_constraint.range_distance_km


# ---------------------------------------------------------------------------
# SimulationManager check: None by design vs missing metrics
# ---------------------------------------------------------------------------


def _run_strategy_result(simulation_manager, association):
    result = MagicMock(new_links=[association], updated_links=[], obsolete_links=[])
    simulation_manager.inter_satellite_link_connection_strategy = MagicMock(
        compute_strategy=MagicMock(return_value=result)
    )
    simulation_manager.update_inter_satellite_links()


def test_manager_rejects_an_advanced_link_without_constraints():
    simulation_manager = _four_isl_walker(BASIC).load_simulation()
    satellites = simulation_manager.get_satellites()
    association = LinkAssociation(
        satellite_a=satellites[0],
        satellite_b=satellites[55],
        direction=InterSatelliteLinkDirection.ADJACENT,
        optical_link_model=ADVANCED,
    )

    with pytest.raises(ValueError, match="without optical constraints"):
        _run_strategy_result(simulation_manager, association)


def test_manager_accepts_a_basic_link_without_constraints():
    simulation_manager = _four_isl_walker(BASIC).load_simulation()
    satellites = simulation_manager.get_satellites()
    association = LinkAssociation(
        satellite_a=satellites[0],
        satellite_b=satellites[55],
        direction=InterSatelliteLinkDirection.ADJACENT,
        optical_link_model=BASIC,
    )
    _run_strategy_result(simulation_manager, association)

    created = simulation_manager.get_inter_satellites_links()[-1]
    assert created.optical_link_model == BASIC
    assert created.distance_km == pytest.approx(_eci_distance_km(created), rel=1e-12)
