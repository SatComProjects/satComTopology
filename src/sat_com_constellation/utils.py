import math

from pydantic import BaseModel
from sgp4.api import Satrec, WGS72
from sgp4.api import jday
from sgp4.exporter import export_tle


class TwoLineElement(BaseModel):
    satellite_name: str
    line1: str
    line2: str


def generate_two_line_elements(
    constellation_name: str,
    number_of_orbits: int,
    number_of_satellites_per_plane: int,
    phase_difference: int,
    inclination_degree: float,
    mean_motion_revolution_per_day: float,
    eccentricity: float = 0.00001,
    argument_of_perigee_degree: float = 0.0,
    orbit_spreading_degree: float = 360,
) -> list[TwoLineElement]:
    satellite_counter = 0
    two_line_elements = []

    minimum_elevation_angle = 10

    for orbit in range(0, number_of_orbits):
        # Orbit-dependent
        raan_degree = orbit * orbit_spreading_degree / number_of_orbits
        orbit_wise_shift = 0
        if orbit % 2 == 1:
            if phase_difference:
                orbit_wise_shift = orbit_spreading_degree / (
                    number_of_satellites_per_plane * 2.0
                )

        # For each satellite in the orbit
        for n_sat in range(0, number_of_satellites_per_plane):
            if (
                inclination_degree > 80
                and inclination_degree < 100
                and (
                    number_of_satellites_per_plane > 1.3 * number_of_orbits
                    and number_of_satellites_per_plane < 2.2 * number_of_orbits
                )
            ):  # For polar orbits

                mean_motion_rad_per_second = (
                    mean_motion_revolution_per_day * 2 * math.pi / 86400
                )
                semi_major_axis = (
                    398600.4418 * (1 / mean_motion_rad_per_second) ** 2
                ) ** (1 / 3)
                altitude = (
                    semi_major_axis - 6378.137
                )  # We need the altitude to obtain half cone angle

                orbit_wise_shift = 180.0 / number_of_satellites_per_plane
                mean_anomaly_degree = n_sat * 360.0 / number_of_satellites_per_plane

                if orbit % 2 == 0:
                    mean_anomaly_degree += orbit_wise_shift

                mean_anomaly_degree %= 360.0

                half_cone_angle = math.degrees(
                    math.acos(
                        6378.137
                        / (6378.137 + altitude)
                        * math.cos(math.radians(minimum_elevation_angle))
                    )
                )

                delta = (180.0 - (number_of_orbits - 1) * half_cone_angle) / (
                    number_of_orbits + 1
                )
                phi = half_cone_angle + delta

                raan_degree = orbit * phi

            else:  # For non-polar orbits
                mean_anomaly_degree = orbit_wise_shift + (
                    n_sat * 360 / number_of_satellites_per_plane
                )

            # Epoch is set to the year 2000
            # This conveniently in TLE format gives 00001.00000000
            # for the epoch year and Julian day fraction entry
            jd, fr = jday(2000, 1, 1, 0, 0, 0)

            # Use SGP-4 to generate TLE
            sat_sgp4 = Satrec()

            # Based on: https://pypi.org/project/sgp4/
            sat_sgp4.sgp4init(
                WGS72,  # Gravity model [1]
                "i",  # Operating mode (a = old AFPSC mode, i = improved mode)
                satellite_counter + 1,  # satnum:  satellite number
                (jd + fr)
                - 2433281.5,  # epoch:   days since 1949 December 31 00:00 UT [2]
                0.0,  # bstar:   drag coefficient (kg/m2er)
                0.0,  # ndot:    ballistic coefficient (revs/day)
                0.0,  # nndot:   second derivative of mean motion (revs/day^3)
                eccentricity,  # ecco:    eccentricity
                math.radians(
                    argument_of_perigee_degree
                ),  # argpo:   argument or perigee (radians)
                math.radians(inclination_degree),  # inclo:    inclination(radians)
                math.radians(mean_anomaly_degree),  # mo:       mean anomaly (radians)
                mean_motion_revolution_per_day
                * 60
                / 13750.9870831397,  # no_kazai: mean motion (radians/minute) [3]
                math.radians(raan_degree),  # nodeo:    right ascension of
                #           ascending node (radians)
            )

            # Side notes:
            # [1] WGS72 is also used in the NS-3 model
            # [2] Due to a bug in sgp4init, the TLE below irrespective of the value here gives zeros.
            # [3] Conversion factor from:
            #     https://www.translatorscafe.com/unit-converter/en-US/ (continue on next line)
            #     velocity-angular/1-9/radian/second-revolution/day/
            #

            # Export TLE from the SGP-4 object
            line1, line2 = export_tle(sat_sgp4)

            # Line 1 has some problems: there are unknown characters entered for the international
            # designator, and the Julian date is not respected
            # As such, we set our own bogus international designator 00000ABC
            # and we set our own epoch date as 1 January, 2000
            # Why it's 00001.00000000: https://www.celestrak.com/columns/v04n03/#FAQ04
            tle_line1 = line1[:7] + "U 00000ABC 00001.00000000 " + line1[33:]
            tle_line1 = tle_line1[:68] + str(
                calculate_tle_line_checksum(tle_line1[:68])
            )
            tle_line2 = line2

            # Check that the checksum is correct
            if len(tle_line1) != 69 or calculate_tle_line_checksum(
                tle_line1[:68]
            ) != int(tle_line1[68]):
                raise ValueError("TLE line 1 checksum failed")
            if len(tle_line2) != 69 or calculate_tle_line_checksum(
                tle_line2[:68]
            ) != int(tle_line2[68]):
                raise ValueError("TLE line 2 checksum failed")

            two_line_element_set = TwoLineElement(
                satellite_name=f"{constellation_name} {satellite_counter}",
                line1=tle_line1,
                line2=tle_line2,
            )
            two_line_elements.append(two_line_element_set)

            # One more satellite there
            satellite_counter += 1

    return two_line_elements


def calculate_tle_line_checksum(tle_line_without_checksum):
    if len(tle_line_without_checksum) != 68:
        raise ValueError("Must have exactly 68 characters")
    s = 0
    for i in range(len(tle_line_without_checksum)):
        if tle_line_without_checksum[i].isnumeric():
            s += int(tle_line_without_checksum[i])
        if tle_line_without_checksum[i] == "-":
            s += 1
    return s % 10
