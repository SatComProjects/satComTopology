import random

from sat_com_application.simulation_manager import SimulationManager
from sat_com_traffic.traffic_models import TrafficModel, GeographicalBasedTrafficModel


class TrafficGenerator:
    simulation_manager: SimulationManager
    traffic_model: TrafficModel

    packet_size_octet: int = 64000

    def __init__(self, simulation_manager: SimulationManager):
        self.simulation_manager = simulation_manager

    @property
    def satellite_density(self) -> float:
        count_of_orbit_plane = self.simulation_manager.configuration.get(
            "number_of_orbit_plane"
        )
        count_of_satellite_per_orbit_plane = self.simulation_manager.configuration.get(
            "number_of_satellite_per_orbit_plane"
        )
        earth_area = 470000000
        return (count_of_orbit_plane * count_of_satellite_per_orbit_plane) / earth_area

    inter_satellite_capacity_mo_s: int = 1000

    propagation_delay_ms: int = 4

    @property
    def inter_satellite_buffer_size(self) -> int:
        return int(
            self.inter_satellite_capacity_mo_s * (self.propagation_delay_ms / 1000)
        )

    def generate_traffic(self):
        satellite_density = self.satellite_density
        hundred_km_radius_area = 125000
        count_of_satellite = hundred_km_radius_area * satellite_density
        self.traffic_model = GeographicalBasedTrafficModel()

        for (
            inter_satellite_link
        ) in self.simulation_manager.get_inter_satellites_links():
            random_area_amount_of_user = self.traffic_model.compute_traffic(
                link=inter_satellite_link,
                current_time=self.simulation_manager.time_manager.current_time.time(),
            )
            random_area_amount_of_user_for_one_satellite = (
                random_area_amount_of_user / count_of_satellite
            )

            occupied_capacity = (
                random_area_amount_of_user_for_one_satellite * self.packet_size_octet
            )
            if occupied_capacity > inter_satellite_link.link_maximum_capacity:
                residual_packets_capacity = (
                    occupied_capacity - inter_satellite_link.link_maximum_capacity
                )
                residual_packets = residual_packets_capacity / self.packet_size_octet

                too_much_packet_for_the_link = (
                    residual_packets > inter_satellite_link.buffer_length * 2
                )

                too_much_packet_for_one_buffer = (
                    residual_packets > inter_satellite_link.buffer_length
                )

                if too_much_packet_for_the_link:
                    inter_satellite_link.source_buffer_length = (
                        inter_satellite_link.buffer_length
                    )
                    inter_satellite_link.destination_buffer_length = (
                        inter_satellite_link.buffer_length
                    )

                elif too_much_packet_for_one_buffer:
                    inter_satellite_link.source_buffer_length = (
                        inter_satellite_link.buffer_length
                    )
                    inter_satellite_link.destination_buffer_length = (
                        residual_packets - inter_satellite_link.source_buffer_length
                    )
                else:
                    packet_ratio_repartition = random.uniform(0.1, 0.99)
                    inter_satellite_link.source_buffer_length = (
                        packet_ratio_repartition * residual_packets_capacity
                    )
                    inter_satellite_link.destination_buffer_length = (
                        residual_packets - inter_satellite_link.source_buffer_length
                    )
