from sat_com_model.model import Simulation


def generate_ground_station_link_with_position(
    simulation: Simulation, ground_station_link_range_in_meter: float
):
    """
    Generates a ground station link between satellite and ground station.
    :param ground_station_link_range_in_meter:
    :param simulation:
    :return:
    """
    for ground_station in simulation.ground_stations:
        for satellite in simulation.satellites:
            distance = simulation.get_distance_model().get_distance_meters(
                ground_station.get_coordinates(), satellite.get_coordinates()
            )
            if distance < ground_station_link_range_in_meter:
                simulation.create_ground_station_link_connection(
                    satellite, ground_station
                )
