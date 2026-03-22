from sat_com_application.time_managers import TimeManager
from sat_com_constellation.models import (
    Constellation,
)
from sat_com_model.models import Satellite, create_satellite, Shell
from sat_com_trajectopy.orbital_models import PyOrbitalModel


def generate_satellites_from_walker_constellation(
    constellation: Constellation, timer_manager: TimeManager, shell: Shell
) -> list[Satellite]:
    """
    Generate a list of Satellite from Two Line Element list at a given start date. It will use PyOrbitalModel to
    generate the satellites position. Satellites id will be generated in a range of 0 to amount of satellites minus one.

    If the PyOrbitalModel fail to generate a satellite, satellite will be ignored, and the next satellite will have the
    next id. The failed satellite id will not be used.

    :param shell:  Shell of the satellite to generate
    :param constellation: Walker constellation
    :param timer_manager: TimeManager object to have the simulation time
    :return:
    """
    id_index = 0
    satellites = []
    for tle in constellation.generated_two_line_elements:
        satellite_model = None
        try:
            satellite_model = PyOrbitalModel(tle.model_dump(), timer_manager)

        except Exception as e:
            print(e)

        if satellite_model is not None:
            satellite = create_satellite(
                satellite_name=satellite_model.satellite_name,
                object_id=id_index,
                domain=constellation.identifier,
                shell=shell,
            )
            satellite.set_movement_model(satellite_model)
            satellites.append(satellite)

        id_index += 1

    return satellites
