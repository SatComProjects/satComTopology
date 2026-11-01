from sat_com_application.time_managers import TimeManager
from sat_com_constellation.models import (
    Constellation,
)
from sat_com_model.factories import create_satellite, AbstractSatelliteFactory
from sat_com_model.models import Satellite, Shell, T_Shell
from sat_com_trajectopy.orbital_models import PyOrbitalModel


def create_satellite_from_tle(
    tle: dict,
    object_id: int,
    shell: T_Shell,
    timer_manager: TimeManager,
    domain: str = "public",
    satellite_factory: AbstractSatelliteFactory = None,
) -> Satellite[T_Shell] | None:
    """
    Create a Satellite from a TLE dict, instantiating the PyOrbitalModel internally.
    Returns None if the TLE is invalid and SGP4 initialisation fails.

    Parameters
    ----------
    tle : dict
        TLE dict with keys: satellite_name, line1, line2.
    object_id : int
        Business identifier within its constellation.
    shell : T_Shell
        Walker or SSO shell the satellite belongs to.
    timer_manager : TimeManager
        Simulation clock passed to the movement model.
    domain : str
        Constellation identifier / owner domain.
    satellite_factory : AbstractSatelliteFactory
        Factory used to build the satellite. Defaults to sat_com_model.factories.create_satellite.
    """
    try:
        movement_model = PyOrbitalModel(tle, timer_manager)
    except Exception as e:
        print(
            f"Failed to create movement model for TLE {tle.get('satellite_name')}: {e}"
        )
        return None

    create = (
        satellite_factory.create_satellite
        if satellite_factory is not None
        else create_satellite
    )
    return create(
        satellite_name=movement_model.satellite_name,
        object_id=object_id,
        shell=shell,
        movement_model=movement_model,
        domain=domain,
    )


def generate_satellites_from_walker_constellation(
    constellation: Constellation,
    timer_manager: TimeManager,
    shell: Shell,
    satellite_factory: AbstractSatelliteFactory = None,
) -> list[Satellite]:
    satellites = []
    for id_index, tle in enumerate(constellation.generated_two_line_elements):
        satellite = create_satellite_from_tle(
            tle=tle.model_dump(),
            object_id=id_index,
            shell=shell,
            timer_manager=timer_manager,
            domain=constellation.identifier,
            satellite_factory=satellite_factory,
        )
        if satellite is not None:
            satellites.append(satellite)

    return satellites


# def generate_satellites_from_walker_constellation(
#     constellation: Constellation, timer_manager: TimeManager, shell: Shell
# ) -> list[Satellite]:
#     """
#     Generate a list of Satellite from Two Line Element list at a given start date. It will use PyOrbitalModel to
#     generate the satellites position. Satellites id will be generated in a range of 0 to amount of satellites minus one.
#
#     If the PyOrbitalModel fail to generate a satellite, satellite will be ignored, and the next satellite will have the
#     next id. The failed satellite id will not be used.
#
#     :param shell:  Shell of the satellite to generate
#     :param constellation: Walker constellation
#     :param timer_manager: TimeManager object to have the simulation time
#     :return:
#     """
#     id_index = 0
#     satellites = []
#     for tle in constellation.generated_two_line_elements:
#         satellite_model = None
#         try:
#             satellite_model = PyOrbitalModel(tle.model_dump(), timer_manager)
#
#         except Exception as e:
#             print(e)
#
#         if satellite_model is not None:
#             satellite = create_satellite(
#                 satellite_name=satellite_model.satellite_name,
#                 object_id=id_index,
#                 domain=constellation.identifier,
#                 shell=shell,
#             )
#             satellite.set_movement_model(satellite_model)
#             satellites.append(satellite)
#
#         id_index += 1
#
#     return satellites
