"""
Code of the "How to use satComTopology in my emulator" tutorials (main README,
sat_com_builder README and sat_com_application README). Keep both in sync.
"""

import ipaddress

from pydantic import BaseModel, Field

from sat_com_application.event_bus.bus import EventBus
from sat_com_application.event_bus.events import (
    EventType,
    ISLCreatedEvent,
    ISLRemovedEvent,
    ISLUpdatedEvent,
    TopologyObjectCreatedEvent,
)
from sat_com_application.event_bus.factories import (
    DefaultISLEventFactory,
    DefaultTopologyObjectEventFactory,
    EventFactories,
)
from sat_com_builder.configuration_manager import BaseConfigurationManager
from sat_com_builder.factories import TopologyObjectFactories
from sat_com_builder.models import SimulationProperty
from sat_com_model.factories import AbstractSatelliteFactory
from sat_com_model.models import InterSatelliteLink, Satellite, TopologyObject

# ---------------------------------------------------------------------------
# 1. Topology objects: SatelliteRouter = Satellite + NetworkMixin
# ---------------------------------------------------------------------------


class NetworkInterface(BaseModel):
    name: str
    mac_address: str
    is_up: bool = False


class NetworkMixin(BaseModel):
    ipv4_address: ipaddress.IPv4Address | None = None
    interfaces: list[NetworkInterface] = Field(default_factory=list)


class SatelliteRouter(Satellite, NetworkMixin):
    pass


class SatelliteRouterFactory(AbstractSatelliteFactory):
    def __init__(self, subnet: str = "10.0.0.0/16"):
        # One address pool for the whole constellation (every shell).
        self._free_addresses = ipaddress.IPv4Network(subnet).hosts()

    def create_satellite(
        self, satellite_name, object_id, shell, movement_model, domain="public"
    ) -> SatelliteRouter:
        ipv4_address = next(self._free_addresses)
        satellite = SatelliteRouter(
            satellite_name=satellite_name,
            object_id=object_id,
            shell=shell,
            movement_model=movement_model,
            domain=domain,
            ipv4_address=ipv4_address,
        )

        # One interface per optical terminal. The terminals exist once the
        # satellite is built (they come from the shell satellite configuration).
        mac_prefix = "02:" + ":".join(f"{byte:02x}" for byte in ipv4_address.packed)
        satellite.interfaces = [
            NetworkInterface(
                name=f"isl{index}", mac_address=f"{mac_prefix}:{index:02x}"
            )
            for index, _ in enumerate(satellite.optical_link_terminals)
        ]
        return satellite


# ---------------------------------------------------------------------------
# 2. Events: add the network information the emulator needs
# ---------------------------------------------------------------------------


class NetworkTopologyObjectEventFactory(DefaultTopologyObjectEventFactory):
    def created(self, topology_object: TopologyObject) -> TopologyObjectCreatedEvent:
        event = super().created(topology_object)
        if isinstance(topology_object, NetworkMixin):
            event.properties = {
                "ipv4_address": str(topology_object.ipv4_address),
                "interfaces": [i.model_dump() for i in topology_object.interfaces],
            }
        return event


class RoutedISLCreatedEvent(ISLCreatedEvent):
    satellite_a_ipv4: str
    satellite_b_ipv4: str


class RoutedISLEventFactory(DefaultISLEventFactory):
    def created(self, link: InterSatelliteLink) -> RoutedISLCreatedEvent:
        event = super().created(link)
        return RoutedISLCreatedEvent(
            **event.model_dump(),
            satellite_a_ipv4=str(link.get_satellite_source().ipv4_address),
            satellite_b_ipv4=str(link.get_satellite_destination().ipv4_address),
        )


# ---------------------------------------------------------------------------
# 3. sat_com_application README example: geo-informed ISL events
# ---------------------------------------------------------------------------


class GeoInformedISLCreatedEvent(ISLCreatedEvent):
    mean_latitude: float
    mean_longitude: float

    satellite_a_shell: str
    satellite_b_shell: str


class GeoInformedISLUpdatedEvent(ISLUpdatedEvent):
    mean_latitude: float
    mean_longitude: float

    satellite_a_shell: str
    satellite_b_shell: str


class GeoInformedISLEventFactory(DefaultISLEventFactory):

    @staticmethod
    def _geo_information(link: InterSatelliteLink) -> dict:
        source = link.source.get_coordinates()
        destination = link.destination.get_coordinates()
        return dict(
            mean_latitude=(source.latitude + destination.latitude) / 2,
            mean_longitude=(source.longitude + destination.longitude) / 2,
            satellite_a_shell=link.get_satellite_source().shell.identifier,
            satellite_b_shell=link.get_satellite_destination().shell.identifier,
        )

    def created(self, link: InterSatelliteLink) -> GeoInformedISLCreatedEvent:
        event = super().created(link)
        return GeoInformedISLCreatedEvent(
            **event.model_dump(), **self._geo_information(link)
        )

    def updated(self, link: InterSatelliteLink) -> GeoInformedISLUpdatedEvent:
        event = super().updated(link)
        return GeoInformedISLUpdatedEvent(
            **event.model_dump(), **self._geo_information(link)
        )

    def removed(self, link: InterSatelliteLink) -> ISLRemovedEvent:
        return super().removed(link)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

CONFIGURATION = {
    "simulation_name": "Emulator",
    "start_date": "2024-11-18 00:00:00.000000",
    "end_date": "2024-11-18 00:10:00.000000",
    "walker_shells": [
        {
            "type": "delta",
            "constellation_property": {
                "identifier": "Walker",
                "amount_of_orbit_plane": 3,
                "amount_of_satellite_per_orbit_plane": 4,
                "inclination": 53.0,
                "phase_difference_between_satellites": True,
                "mean_revolution_per_day": 15.5,
            },
            "orbital_connectivity_property": {"adjacent_inter_satellite_shifting": 0},
        }
    ],
}


def _record(received: list):
    async def handler(event):
        received.append(event)

    return handler


def test_emulator_receives_routers_and_routed_links():
    created_nodes, created_links = [], []
    event_bus = EventBus()
    event_bus.subscribe(EventType.TO_CREATED, _record(created_nodes))
    event_bus.subscribe(EventType.ISL_CREATED, _record(created_links))

    simulation_manager = BaseConfigurationManager(
        simulation_property=SimulationProperty(**CONFIGURATION),
        event_bus=event_bus,
        event_factories=EventFactories(
            isl_event_factory=RoutedISLEventFactory(),
            topology_object_event_factory=NetworkTopologyObjectEventFactory(),
        ),
        topology_object_factories=TopologyObjectFactories(
            satellite_factory=SatelliteRouterFactory()
        ),
    ).load_simulation()

    satellites = simulation_manager.get_satellites()
    assert all(isinstance(satellite, SatelliteRouter) for satellite in satellites)
    assert len({satellite.ipv4_address for satellite in satellites}) == 12
    assert [i.name for i in satellites[0].interfaces] == [
        "isl0",
        "isl1",
        "isl2",
        "isl3",
    ]

    assert len(created_nodes) == 12
    assert created_nodes[0].properties["ipv4_address"] == "10.0.0.1"
    assert len(created_nodes[0].properties["interfaces"]) == 4

    assert created_links
    assert all(isinstance(event, RoutedISLCreatedEvent) for event in created_links)
    assert created_links[0].satellite_a_ipv4.startswith("10.0.")
    assert created_links[0].sim_time is not None

    simulation_manager.time_manager.tick(60)


def test_geo_informed_isl_events():
    created_links, updated_links = [], []
    event_bus = EventBus()
    event_bus.subscribe(EventType.ISL_CREATED, _record(created_links))
    event_bus.subscribe(EventType.ISL_UPDATED, _record(updated_links))

    event_factories = EventFactories()
    event_factories.isl_event_factory = GeoInformedISLEventFactory()

    simulation_manager = BaseConfigurationManager(
        simulation_property=SimulationProperty(**CONFIGURATION),
        event_bus=event_bus,
        event_factories=event_factories,
    ).load_simulation()
    simulation_manager.time_manager.tick(60)

    event = created_links[0]
    assert isinstance(event, GeoInformedISLCreatedEvent)
    assert event.satellite_a_shell == event.satellite_b_shell == "Walker"
    assert -90 <= event.mean_latitude <= 90
    assert updated_links and isinstance(updated_links[0], GeoInformedISLUpdatedEvent)
