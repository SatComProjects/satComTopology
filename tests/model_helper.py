from src.sat_com_model.model import Satellite


def create_fake_satellite_with_satellite_id(satellite_id: int) -> Satellite:
    satellite = Satellite()
    satellite.satellite_id = satellite_id
    return satellite
