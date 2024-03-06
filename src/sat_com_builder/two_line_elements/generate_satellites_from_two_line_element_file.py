from sat_com_model.models import create_satellite


def generate_satellites_from_two_line_element(two_line_elements: []):
    id_index = 0
    satellites = []
    for tle in two_line_elements:
        satellite_name = tle.get("satellite_name")
        satellite = create_satellite(satellite_name, id_index)
        satellites.append(satellite)

        id_index += 1

    return satellites
