from sat_com_application.simulation_manager import SimulationManager
from sat_com_model.models import Simulation


def generate_ground_station_link_with_position(
    simulation_manager: SimulationManager, ground_station_link_range_in_meter: float
):
    """
    Generates a ground station link between satellite and ground station.
    :param ground_station_link_range_in_meter:
    :param simulation_manager:
    :return:
    """
    for ground_station in simulation_manager.simulation.ground_stations:
        for satellite in simulation_manager.simulation.satellites:
            distance = (
                simulation_manager.simulation.get_distance_model().get_distance_meters(
                    ground_station.get_coordinates(), satellite.get_coordinates()
                )
            )
            if distance < ground_station_link_range_in_meter:
                simulation_manager.create_ground_station_link_connection(
                    satellite, ground_station
                )
