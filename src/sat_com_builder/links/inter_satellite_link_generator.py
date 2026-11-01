# The MIT License (MIT)
#
# Copyright (c) 2020 ETH Zurich
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# Modifications :
# - Created transform_text_to_isl
# - create_isls_from_tles
# - Refactor and renamed functions (generate_plus_grid_isls)

# Source: https://github.com/snkas/hypatia


from sat_com_model.models import (
    InterSatelliteLinkDirection,
)


def generate_walker_star_constellation_grid(
    number_orbits: int, number_satellites_per_orbit: int, isl_shift: int, idx_offset=0
):
    """
    This code generate a grid that represent inter-satellite links. This is for a walker star Mega-constellation.

    :param number_orbits:                Number of orbits
    :param number_satellites_per_orbit:        Number of satellites per orbit
    :param isl_shift:               ISL shift between orbits (e.g., if satellite id in orbit is X,
                                    does it also connect to the satellite at X in the adjacent orbit)
    :param idx_offset:              Index offset (e.g., if you have multiple shells)
    :return : list of inter-satellite links under the following format (int, int, InterSatelliteLinkDirection)
    """
    if number_orbits < 3 or number_satellites_per_orbit < 3:
        raise ValueError("Number of x and y must each be at least 3")

    list_inter_satellite_links = []
    for i in range(number_orbits):
        for j in range(number_satellites_per_orbit):
            sat = i * number_satellites_per_orbit + j

            # Link to the next in the orbit
            sat_same_orbit = i * number_satellites_per_orbit + (
                (j + 1) % number_satellites_per_orbit
            )

            has_an_inter_plane = i + 1 < number_orbits
            if has_an_inter_plane:
                sat_adjacent_orbit = (i + 1) * number_satellites_per_orbit + (
                    (j + isl_shift) % number_satellites_per_orbit
                )
                # Adjacent orbit
                list_inter_satellite_links.append(
                    (
                        idx_offset + min(sat, sat_adjacent_orbit),
                        idx_offset + max(sat, sat_adjacent_orbit),
                        InterSatelliteLinkDirection.ADJACENT,
                    )
                )

            # Same orbit
            list_inter_satellite_links.append(
                (
                    idx_offset + min(sat, sat_same_orbit),
                    idx_offset + max(sat, sat_same_orbit),
                    InterSatelliteLinkDirection.ORBITAL,
                )
            )

    return list_inter_satellite_links


def generate_walker_delta_constellation_grid(
    number_orbits: int, number_satellites_per_orbit: int, isl_shift: int, idx_offset=0
) -> list:
    """
    This code generate a grid that represent inter-satellite links. This code come from Hypatia software.


    :param number_orbits:                Number of orbits
    :param number_satellites_per_orbit:        Number of satellites per orbit
    :param isl_shift:               ISL shift between orbits (e.g., if satellite id in orbit is X,
                                    does it also connect to the satellite at X in the adjacent orbit)
    :param idx_offset:              Index offset (e.g., if you have multiple shells)
    :return : list of inter-satellite links under the following format (int, int, InterSatelliteLinkDirection)
    """

    if number_orbits < 3 or number_satellites_per_orbit < 3:
        raise ValueError("Number of x and y must each be at least 3")

    list_inter_satellite_links = []
    for i in range(number_orbits):
        for j in range(number_satellites_per_orbit):
            sat = i * number_satellites_per_orbit + j

            # Link to the next in the orbit
            sat_same_orbit = i * number_satellites_per_orbit + (
                (j + 1) % number_satellites_per_orbit
            )
            sat_adjacent_orbit = (
                (i + 1) % number_orbits
            ) * number_satellites_per_orbit + (
                (j + isl_shift) % number_satellites_per_orbit
            )

            # Same orbit
            list_inter_satellite_links.append(
                (
                    idx_offset + min(sat, sat_same_orbit),
                    idx_offset + max(sat, sat_same_orbit),
                    InterSatelliteLinkDirection.ORBITAL,
                )
            )

            # Adjacent orbit
            list_inter_satellite_links.append(
                (
                    idx_offset + min(sat, sat_adjacent_orbit),
                    idx_offset + max(sat, sat_adjacent_orbit),
                    InterSatelliteLinkDirection.ADJACENT,
                )
            )
    return list_inter_satellite_links


def generate_sun_synchronous_constellation_grid(
    number_satellites_per_orbit: int,
) -> list:

    list_inter_satellite_links = []
    for i in range(number_satellites_per_orbit):
        sat = i
        sat_same_orbit = (i + 1) % number_satellites_per_orbit
        list_inter_satellite_links.append(
            (sat, sat_same_orbit, InterSatelliteLinkDirection.ORBITAL)
        )

    return list_inter_satellite_links


def generate_checkerboard_walker_delta_constellation_grid(
    number_orbits: int, number_satellites_per_orbit: int, isl_shift: int, idx_offset=0
) -> list:

    if number_orbits < 3 or number_satellites_per_orbit < 3:
        raise ValueError(
            "Number of orbit and number of satellite per obit must each be at least 3"
        )

    is_number_of_orbit_even = number_orbits % 2 == 0

    is_number_of_sat_per_orbit_even = number_satellites_per_orbit % 2 == 0

    are_parameters_valid = is_number_of_orbit_even and is_number_of_sat_per_orbit_even

    if not are_parameters_valid:
        raise ValueError(
            "Number of orbit and number of satellite per obit must each be even for checkerboard pattern"
        )

    list_inter_satellite_links = []

    for i in range(number_orbits):
        for j in range(number_satellites_per_orbit):
            sat = i * number_satellites_per_orbit + j

            # Same orbit neighbor
            sat_same_orbit = i * number_satellites_per_orbit + (
                (j + 1) % number_satellites_per_orbit
            )

            # Adjacent orbit neighbor
            sat_adjacent_orbit = (
                (i + 1) % number_orbits
            ) * number_satellites_per_orbit + (
                (j + isl_shift) % number_satellites_per_orbit
            )

            # Always keep intra-orbit links
            list_inter_satellite_links.append(
                (
                    idx_offset + min(sat, sat_same_orbit),
                    idx_offset + max(sat, sat_same_orbit),
                    InterSatelliteLinkDirection.ORBITAL,
                )
            )

            if (i % 2 == 0 and j % 2 == 0) or (i % 2 == 1 and j % 2 == 1):
                list_inter_satellite_links.append(
                    (
                        idx_offset + min(sat, sat_adjacent_orbit),
                        idx_offset + max(sat, sat_adjacent_orbit),
                        InterSatelliteLinkDirection.ADJACENT,
                    )
                )

    return list_inter_satellite_links


def generate_checkerboard_walker_star_constellation_grid(
    number_orbits: int, number_satellites_per_orbit: int, isl_shift: int, idx_offset=0
):
    if number_orbits < 3 or number_satellites_per_orbit < 3:
        raise ValueError("Number of x and y must each be at least 3")

    is_number_of_sat_per_orbit_even = number_satellites_per_orbit % 2 == 0

    # Do not need to be even for the orbit number as it has a mesh anyway
    if not is_number_of_sat_per_orbit_even:
        raise ValueError("Number of satellite per obit must each be even")

    list_inter_satellite_links = []

    for i in range(number_orbits):
        for j in range(number_satellites_per_orbit):
            sat = i * number_satellites_per_orbit + j

            # Same orbit neighbor
            sat_same_orbit = i * number_satellites_per_orbit + (
                (j + 1) % number_satellites_per_orbit
            )

            # Always keep intra-orbit links
            list_inter_satellite_links.append(
                (
                    idx_offset + min(sat, sat_same_orbit),
                    idx_offset + max(sat, sat_same_orbit),
                    InterSatelliteLinkDirection.ORBITAL,
                )
            )

            # Only connect to next orbit (no wrap-around in Walker Star)
            has_an_inter_plane = i + 1 < number_orbits

            if has_an_inter_plane:
                sat_adjacent_orbit = (i + 1) * number_satellites_per_orbit + (
                    (j + isl_shift) % number_satellites_per_orbit
                )

                # ✅ Apply parity rule
                if (i % 2 == 0 and j % 2 == 0) or (i % 2 == 1 and j % 2 == 1):
                    list_inter_satellite_links.append(
                        (
                            idx_offset + min(sat, sat_adjacent_orbit),
                            idx_offset + max(sat, sat_adjacent_orbit),
                            InterSatelliteLinkDirection.ADJACENT,
                        )
                    )

    return list_inter_satellite_links
