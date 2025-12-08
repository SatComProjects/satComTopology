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
from sat_com_application.simulation_manager import SimulationManager
from sat_com_builder.models import OrbitalConnectivityProperty, WalkerShellProperty

# Modifications :
# - Created transform_text_to_isl
# - create_isls_from_tles
# - Refactor and renamed functions (generate_plus_grid_isls)

# Source: https://github.com/snkas/hypatia

from sat_com_constellation.models import (
    WalkerConstellationProperty,
)
from sat_com_model.exceptions import (
    TopologyObjectNotFoundError,
    TopologyConnectionError,
)
from sat_com_model.models import InterSatelliteLinkDirection


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


def transform_grid_to_inter_satellite_links(
    simulation_service: SimulationManager,
    list_isl: list,
    walker_shell_property: WalkerShellProperty,
):
    """
    This function will create inter satellite links based on the ISL list previously generated.
    :param walker_shell_property: Property of the shell
    :param simulation_service: SimulationManager object
    :param list_isl: list of vector like object (int, int, InterSatelliteLinkDirection)
    :return:
    """
    for a, b, type_link in list_isl:
        satellite_a = None
        satellite_b = None
        try:
            satellite_a = simulation_service.get_satellite_by_object_id(
                a, walker_shell_property.constellation_property.identifier
            )
        except TopologyObjectNotFoundError:
            print("Satellite {sat_id} not found".format(sat_id=a))

        try:
            satellite_b = simulation_service.get_satellite_by_object_id(
                b, walker_shell_property.constellation_property.identifier
            )

        except TopologyObjectNotFoundError:
            print("Satellite {sat_id} not found".format(sat_id=b))

        if satellite_a is not None and satellite_b is not None:
            try:
                created_link = (
                    simulation_service.create_and_add_inter_satellite_link_connection(
                        satellite_a, satellite_b
                    )
                )
                created_link.inter_satellite_direction = type_link
            except TopologyConnectionError as tpe:
                print(
                    "Failed to connect {sat_a} and {sat_b} : {message}".format(
                        sat_a=str(satellite_a), sat_b=str(satellite_b), message=tpe
                    )
                )


def create_inter_satellite_links_for_walker_delta_constellation(
    walker_delta_constellation: WalkerConstellationProperty,
    connectivity_property: OrbitalConnectivityProperty,
):
    return generate_walker_delta_constellation_grid(
        number_orbits=walker_delta_constellation.amount_of_orbit_plane,
        number_satellites_per_orbit=walker_delta_constellation.amount_of_satellite_per_orbit_plane,
        isl_shift=connectivity_property.adjacent_inter_satellite_shifting,
    )


def create_inter_satellite_links_for_walker_star_constellation(
    walker_delta_constellation: WalkerConstellationProperty,
    connectivity_property: OrbitalConnectivityProperty,
):
    return generate_walker_star_constellation_grid(
        number_orbits=walker_delta_constellation.amount_of_orbit_plane,
        number_satellites_per_orbit=walker_delta_constellation.amount_of_satellite_per_orbit_plane,
        isl_shift=connectivity_property.adjacent_inter_satellite_shifting,
    )


def create_inter_satellite_links_for_walker_constellation(
    simulation_manager: SimulationManager,
    walker_shell_properties: WalkerShellProperty,
):

    if walker_shell_properties.type == "star":
        generated_grid = create_inter_satellite_links_for_walker_star_constellation(
            walker_shell_properties.constellation_property,
            walker_shell_properties.orbital_connectivity_property,
        )

    elif walker_shell_properties.type == "delta":
        generated_grid = create_inter_satellite_links_for_walker_delta_constellation(
            walker_shell_properties.constellation_property,
            walker_shell_properties.orbital_connectivity_property,
        )
    else:
        raise ValueError("Unknown type of walker constellation")

    transform_grid_to_inter_satellite_links(
        simulation_manager, generated_grid, walker_shell_properties
    )
