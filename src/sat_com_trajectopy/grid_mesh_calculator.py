def calculate_satellite_mesh_coordinates(
    object_id: int,
    number_orbit_plane: int,
    number_satellite_per_orbit_plane: int,
    inter_satellite_shift_phase: int,
) -> tuple[int, int]:
    """
    Return the coordinates on the constellation grid depending on the identifier of the satellite.
    Satellites identifier should start from 0 to total satellites numbers - 1.
    :param object_id: the identifier of the satellite
    :param number_orbit_plane: the number of orbit plane in the constellation grid
    :param number_satellite_per_orbit_plane: the number of satellite per orbit plane in the constellation grid
    :param inter_satellite_shift_phase: the shift phase between adjacent orbit planes the constellation
    :return: A tuple consisting of the orbit number of the satellite and its satellite number on its orbit plane
    """
    orbit_number = object_id // number_orbit_plane

    shift_plane_calculated = inter_satellite_shift_phase * orbit_number

    base_satellite_orbit_identifier = object_id % number_satellite_per_orbit_plane

    satellite_orbit_identifier_with_shift = (
        base_satellite_orbit_identifier - shift_plane_calculated
    )

    identifier_is_bigger_or_equal_to_number_satellite_per_orbit = (
        satellite_orbit_identifier_with_shift >= number_satellite_per_orbit_plane
    )
    identifier_is_smaller_than_0 = satellite_orbit_identifier_with_shift < 0

    if identifier_is_bigger_or_equal_to_number_satellite_per_orbit:
        satellite_orbit_identifier_with_shift = (
            satellite_orbit_identifier_with_shift - number_satellite_per_orbit_plane
        )

    elif identifier_is_smaller_than_0:
        satellite_orbit_identifier_with_shift = (
            number_satellite_per_orbit_plane + satellite_orbit_identifier_with_shift
        )

    return orbit_number, satellite_orbit_identifier_with_shift
