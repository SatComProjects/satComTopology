"""
Regression tests for the inter-shell OISL angular-velocity / range-rate
finite-difference computation.

Background
----------
Commit "Huge performance improvement on the optical link creation" (8ae0139 /
a7dcce5) moved the satellite position sampled at "t + dt" (used to finite-
difference az/el/range into rates) behind `_EciCache`, which is given a `dt`
at construction time (`_EciCache(self, dt: float = 0.0)`).

Only the intra-shell path (addressing_plans.py, `_build_associations_from_grid`)
was updated to construct `_EciCache(self.delta_t_velocity)`. The inter-shell
path in optical_helpers.py — `compute_OISL_feasibility_for_terminal_pair`
(per-tick update of an EXISTING inter-shell link) and
`compute_OISL_links_from_terminal_pools_filtered` (creation of a NEW
inter-shell link) — kept constructing a bare `_EciCache()`, silently
defaulting `dt=0.0` regardless of the `angular_velocity_dt_seconds` argument
threaded through the rest of the call. That made the "t + dt" sample
identical to "t", so every inter-shell `angular_velocity_rate_degree_per_second`
and `range_rate` computed to exactly 0.0 — while intra-shell (ORBITAL /
ADJACENT) links, going through the correctly-wired path, were unaffected.

This was invisible to the existing test suite because
test_inter_shell_connectivity.py mocks out `compute_OISL_feasibility_for_terminal_pair`
/ `compute_OISL_links_from_terminal_pools_filtered` entirely (it only tests
strategy-level bookkeeping), and the one test module that exercised the real
numeric path (test_compute_oisl_connectivity.py) is fully commented out.

These tests call the real, unmocked numeric functions with genuinely
different satellite velocity vectors and assert the resulting rates are
nonzero — which fails outright under the bug above.
"""

import numpy as np
from unittest.mock import MagicMock

from sat_com_connectivity.inter_satellite_link_connectivity.optical_helpers import (
    compute_OISL_feasibility_for_terminal_pair,
    compute_OISL_links_from_terminal_pools_filtered,
)
from sat_com_model.models import Satellite, OpticalLinkTerminal


def _make_satellite(topology_id, shell_identifier, position_km, velocity_km_s):
    sat = MagicMock(spec=Satellite)
    sat.topology_uniq_id = topology_id
    shell = MagicMock()
    shell.identifier = shell_identifier
    sat.shell = shell

    movement_model = MagicMock()
    movement_model.get_position_earth_general_inertial.return_value = np.array(
        position_km
    )
    movement_model.get_velocity_earth_general_inertial.return_value = np.array(
        velocity_km_s
    )
    sat.get_movement_model.return_value = movement_model
    return sat


def _make_terminal(host_satellite):
    terminal = MagicMock(spec=OpticalLinkTerminal)
    terminal.host_satellite = host_satellite
    terminal.azimuth_angle_configuration = 0.0
    terminal.elevation_angle_configuration = -180.0

    cfg = MagicMock()
    # Deliberately permissive so feasibility/candidate gating never masks
    # the thing under test: the raw rate computation itself.
    cfg.min_elevation_degrees = -90.0
    cfg.max_elevation_degrees = 90.0
    cfg.max_azimuth_degrees = 180.0
    cfg.maximum_range_distance_km = 1_000_000.0
    cfg.maximum_angular_velocity_degree_per_second = 1_000.0
    cfg.minimum_contact_duration_seconds = 0
    terminal.terminal_configuration = cfg
    return terminal


# Two LEO-ish satellites ~2083 km apart with a clear line of sight
# (los_min_altitude ~= 417 km, well above the 80 km atmosphere exclusion
# zone) and genuinely different velocity vectors, so the LOS angle must
# measurably drift between t and t+dt.
_SAT_A_POS, _SAT_A_VEL = (7000.0, 0.0, 0.0), (0.0, 7.5, 0.2)
_SAT_B_POS, _SAT_B_VEL = (6500.0, 2000.0, 300.0), (-1.0, 7.0, -0.3)


def _make_pair():
    sat_a = _make_satellite(1, "sso-a", _SAT_A_POS, _SAT_A_VEL)
    sat_b = _make_satellite(2, "walker-a", _SAT_B_POS, _SAT_B_VEL)
    return sat_a, sat_b, _make_terminal(sat_a), _make_terminal(sat_b)


def test_existing_link_feasibility_pair_has_nonzero_rates():
    """
    compute_OISL_feasibility_for_terminal_pair is the per-tick update path
    for an EXISTING inter-shell link (InterShellSSOPriorityConnectivity,
    CASE 3 in strategies.py). With differing velocity vectors both
    directions' angular velocity and range rate must be nonzero.
    """
    sat_a, sat_b, term_a, term_b = _make_pair()

    result = compute_OISL_feasibility_for_terminal_pair(
        satellite_a=sat_a,
        terminal_a=term_a,
        satellite_b=sat_b,
        terminal_b=term_b,
        angular_velocity_dt_seconds=1.0,
    )

    assert result.constraint_a_to_b.angular_velocity_rate_degree_per_second != 0.0
    assert result.constraint_b_to_a.angular_velocity_rate_degree_per_second != 0.0
    assert result.constraint_a_to_b.range_rate != 0.0
    assert result.constraint_b_to_a.range_rate != 0.0


def test_existing_link_feasibility_pair_rate_depends_on_requested_dt():
    """
    Directly guards against the dt/_EciCache decoupling: two different
    `angular_velocity_dt_seconds` values must produce two different (both
    nonzero) rates. A regression that rebuilds `_EciCache()` with its
    default dt=0.0 makes the result identically 0.0 no matter what dt is
    requested, which this test also catches.
    """
    rates = {}
    for dt in (1.0, 5.0):
        sat_a, sat_b, term_a, term_b = _make_pair()
        result = compute_OISL_feasibility_for_terminal_pair(
            satellite_a=sat_a,
            terminal_a=term_a,
            satellite_b=sat_b,
            terminal_b=term_b,
            angular_velocity_dt_seconds=dt,
        )
        rates[dt] = result.constraint_a_to_b.angular_velocity_rate_degree_per_second

    assert rates[1.0] != 0.0
    assert rates[5.0] != 0.0
    assert rates[1.0] != rates[5.0]


def test_new_link_pool_creation_has_nonzero_rates():
    """
    compute_OISL_links_from_terminal_pools_filtered is the per-tick path for
    creating a NEW inter-shell link (InterShellSSOPriorityConnectivity, step
    2 in strategies.py). It builds its own _EciCache internally and hit the
    exact same dt-decoupling bug as the pair-feasibility path above.
    """
    sat_a, sat_b, term_a, term_b = _make_pair()

    links = compute_OISL_links_from_terminal_pools_filtered(
        terminals_group_1=[term_a],
        terminals_group_2=[term_b],
        maximum_range_to_filter_in_km=10_000.0,
        angular_velocity_dt_seconds=1.0,
    )

    assert len(links) == 1, "expected the permissive terminal pair to form a link"
    link = links[0]
    assert link.constraint_a_to_b.angular_velocity_rate_degree_per_second != 0.0
    assert link.constraint_b_to_a.angular_velocity_rate_degree_per_second != 0.0
    assert link.constraint_a_to_b.range_rate != 0.0
