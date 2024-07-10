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
from sat_com_model.models import GroundStation, create_ground_station


# Modifications:
#   - Renamed some variables
#   - Renamed function name
#   - Adapted code to return sat_com_topology objects

# sources: https://github.com/snkas/hypatia


def generate_ground_stations_from_file(
    ground_station_file_path: str,
) -> [GroundStation]:
    """
    Reads ground stations from the input file.

    :param ground_station_file_path: Filename of ground stations basic (typically /path/to/ground_stations.txt)

    :return: List of ground stations
    """
    ground_stations = []
    ground_station_id = 0
    with open(ground_station_file_path, "r") as file:
        for line in file:
            split = line.split(",")
            if len(split) != 5:
                raise ValueError("Basic ground station file has 5 columns")
            if int(split[0]) != ground_station_id:
                raise ValueError("Ground station id must increment each line")

            ground_station = create_ground_station(ground_station_id)
            ground_station.set_position(
                longitude=float(split[3]),
                latitude=float(split[2]),
                elevation=float(split[4]),
            )
            ground_station.city = split[1]

            ground_stations.append(ground_station)
            ground_station_id += 1

        file.close()

    return ground_stations
