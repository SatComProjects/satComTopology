from datetime import datetime

from sat_com_model.models import Simulation, Satellite, create_satellite
from sat_com_trajectopy.orbital_models import PyOrbitalModel


def generate_satellites_from_two_line_elements_with_pyorbital_model(
    two_line_elements: [], start_date: datetime
) -> [Satellite]:
    id_index = 0
    satellites = []
    for tle in two_line_elements:
        satellite_model = None
        try:
            satellite_model = PyOrbitalModel(tle, start_date)

        except Exception as e:
            print(e)

        if satellite_model is not None:
            satellite = create_satellite(satellite_model.satellite_name, id_index)
            satellite.set_movement_model(satellite_model)
            satellites.append(satellite)

        id_index += 1

    return satellites
