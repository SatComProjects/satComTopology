from sat_com_application.time_managers import TimeManager
from sat_com_model.models import Satellite, create_satellite
from sat_com_trajectopy.orbital_models import PyOrbitalModel


def generate_satellites_from_two_line_elements_with_pyorbital_model(
    two_line_elements: [], timer_manager: TimeManager
) -> [Satellite]:
    """
    Generate a list of Satellite from Two Line Element list at a given start date. It will use PyOrbitalModel to
    generate the satellites position. Satellites id will be generated in a range of 0 to amount of satellites minus one.

    If the PyOrbitalModel fail to generate a satellite, satellite will be ignored, and the next satellite will have the
    next id. The failed satellite id will not be used.

    :param timer_manager: TimeManager object to have the simulation time
    :param two_line_elements: List of Two Line Element
    :return:
    """
    id_index = 0
    satellites = []
    for tle in two_line_elements:
        satellite_model = None
        try:
            satellite_model = PyOrbitalModel(tle, timer_manager)

        except Exception as e:
            print(e)

        if satellite_model is not None:
            satellite = create_satellite(satellite_model.satellite_name, id_index)
            satellite.set_movement_model(satellite_model)
            satellites.append(satellite)

        id_index += 1

    return satellites
