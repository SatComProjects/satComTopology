"""The EMPTY addressing plan: no intra-shell link, for a Walker or an SSO shell.

Use case: SSO satellites that only link to a Walker shell (inter-shell terminals only). With the default LINKED_SSO
plan, the SSO shell asks for ORBITAL links its satellites have no terminal for, and warns once per satellite.
"""

import warnings

import pytest

from sat_com_builder.configuration_manager import BaseConfigurationManager
from sat_com_builder.models import (
    AddressingPlanType,
    DawnDuskSunSynchronousOrbitShellProperty,
    InterSatelliteLinkOrientationProperty as Orientation,
    OpticalTerminalInstallationProperty,
    OpticalTerminalProperty,
    OrbitalConnectivityProperty,
    SatelliteProperty,
    SimulationProperty,
    WalkerShellProperty,
)
from sat_com_connectivity.inter_satellite_link_connectivity.addressing_plans import (
    AvailableAddressingPlans,
    EmptyAddressingPlan,
)
from sat_com_connectivity.inter_satellite_link_connectivity.strategies import (
    InterShellSSOPriorityConnectivity,
)
from sat_com_constellation.models import (
    DawnDuskSunSynchronousOrbitConstellationProperty,
    WalkerConstellationProperty,
)
from sat_com_model.models import DawnDuskSSOShell, InterSatelliteLinkDirection


def _inter_shell_terminal(azimuth: float, descriptor: Orientation):
    return OpticalTerminalInstallationProperty(
        azimuth_angle_configuration=azimuth,
        elevation_angle_configuration=-180,
        optical_terminal_property=OpticalTerminalProperty(
            maximum_range_distance_km=5000
        ),
        orientation_possibilities=[
            descriptor,
            Orientation.INTER_SHELL_RIGHT,
            Orientation.INTER_SHELL_LEFT,
        ],
        descriptor=descriptor,
    )


def _walker_and_sso_hosts(sso_plan: AddressingPlanType | None) -> SimulationProperty:
    """A Walker shell, and SSO satellites with a single inter-shell terminal."""
    walker = WalkerShellProperty(
        constellation_property=WalkerConstellationProperty(
            identifier="Walker",
            amount_of_orbit_plane=6,
            amount_of_satellite_per_orbit_plane=11,
            inclination=87.0,
            mean_revolution_per_day=14,
            phase_difference_between_satellites=True,
        ),
        orbital_connectivity_property=OrbitalConnectivityProperty(),
        satellite_property=SatelliteProperty(
            optical_inter_satellite_link_installations=list(
                SatelliteProperty().optical_inter_satellite_link_installations
            )
            + [_inter_shell_terminal(-180, Orientation.INTER_SHELL_BACKWARD)]
        ),
    )
    sso = {
        "constellation_property": DawnDuskSunSynchronousOrbitConstellationProperty(
            identifier="SSO hosts", amount_of_satellite=5, altitude_in_km=650.0
        ),
        "orbital_connectivity_property": OrbitalConnectivityProperty(),
        "satellite_property": SatelliteProperty(
            optical_inter_satellite_link_installations=[
                _inter_shell_terminal(0, Orientation.INTER_SHELL_FORWARD)
            ]
        ),
    }
    if sso_plan is not None:
        sso["static_addressing_plan"] = sso_plan
    return SimulationProperty(
        simulation_name="Walker + SSO hosts",
        start_date="2026-01-01 00:00:00",
        end_date="2026-01-01 00:10:00",
        walker_shells=[walker],
        dawn_dusk_sso_shells=[DawnDuskSunSynchronousOrbitShellProperty(**sso)],
        inter_satellite_link_connection_strategy=InterShellSSOPriorityConnectivity.type,
    )


def _load_and_tick(simulation_property: SimulationProperty):
    """Load the simulation and tick it once; returns (manager, addressing-plan warnings)."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        simulation_manager = BaseConfigurationManager(
            simulation_property=simulation_property
        ).load_simulation()
        simulation_manager.time_manager.tick(5)
    plan_warnings = [
        w for w in caught if "addressing_plans" in w.filename.replace("\\", "/")
    ]
    return simulation_manager, plan_warnings


class TestEmptyAddressingPlanBuild:
    def test_builder_accepts_empty_for_an_sso_shell(self):
        prop = DawnDuskSunSynchronousOrbitShellProperty(
            constellation_property=DawnDuskSunSynchronousOrbitConstellationProperty(
                identifier="SSO", amount_of_satellite=2, altitude_in_km=650.0
            ),
            orbital_connectivity_property=OrbitalConnectivityProperty(),
            static_addressing_plan="EMPTY",
        )
        assert prop.static_addressing_plan == AddressingPlanType.EMPTY
        # survives a dump / re-validation (what an emulator does with the property)
        again = DawnDuskSunSynchronousOrbitShellProperty(**prop.model_dump())
        assert again.static_addressing_plan == AddressingPlanType.EMPTY

    @pytest.mark.parametrize("shell_kwarg", ["walker_shell", "sso_shell"])
    def test_empty_plan_builds_for_walker_and_sso_shells(self, shell_kwarg):
        shell = object()
        plan = AvailableAddressingPlans.EMPTY.build(**{shell_kwarg: shell})
        assert isinstance(plan, EmptyAddressingPlan)
        assert plan.shell is shell
        assert plan.get_type() == "EMPTY"
        assert plan.get_link_associations([]) == []

    def test_empty_plan_needs_no_parameter(self):
        assert AvailableAddressingPlans.EMPTY.required_parameters() == []


class TestEmptyAddressingPlanForSsoHosts:
    def test_default_linked_sso_plan_warns_for_satellites_without_orbital_terminals(
        self,
    ):
        _, plan_warnings = _load_and_tick(_walker_and_sso_hosts(None))
        assert any(
            "No free ORBITAL terminal pair" in str(w.message) for w in plan_warnings
        )

    def test_empty_plan_on_sso_shell_gives_inter_shell_links_only_and_no_warning(self):
        simulation_manager, plan_warnings = _load_and_tick(
            _walker_and_sso_hosts(AddressingPlanType.EMPTY)
        )
        assert plan_warnings == []

        plans = dict(
            (shell.identifier, plan)
            for shell, plan in simulation_manager.shell_addressing_plans
        )
        assert isinstance(plans["SSO hosts"], EmptyAddressingPlan)

        sso_ids = {
            s.topology_uniq_id
            for s in simulation_manager.get_satellites()
            if isinstance(s.shell, DawnDuskSSOShell)
        }
        sso_links = [
            link
            for link in simulation_manager.get_inter_satellites_links()
            if {link.source.topology_uniq_id, link.destination.topology_uniq_id}
            & sso_ids
        ]
        assert sso_links, "the SSO satellites should still get inter-shell links"
        for link in sso_links:
            assert (
                link.inter_satellite_direction
                == InterSatelliteLinkDirection.INTER_SHELL
            )
            assert (
                not {
                    link.source.topology_uniq_id,
                    link.destination.topology_uniq_id,
                }
                <= sso_ids
            )
