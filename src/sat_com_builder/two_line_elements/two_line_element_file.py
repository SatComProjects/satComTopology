class TwoLineElementFile:
    satellite_count_per_orbit: int
    count_of_orbit: int

    parsed_tles: list[dict]

    def __init__(self, satellite_count_per_orbit: int, count_of_orbit: int):
        self.satellite_count_per_orbit = satellite_count_per_orbit
        self.count_of_orbit = count_of_orbit
        self.parsed_tles = []


def parse_two_line_element_to_instance(file_path: str) -> TwoLineElementFile:
    """
    Parse a file containing Two-Line Element (TLE) data into a list of dictionaries.
    :param file_path: str, The path to the file containing TLE data.
    :return: list[dict] A list of dictionaries, each representing a TLE entry.
    """

    with open(file_path, "r") as file:
        count_of_orbit, satellite_count_per_orbit = map(int, file.readline().split())
        two_line_element_file = TwoLineElementFile(
            satellite_count_per_orbit, count_of_orbit
        )

        for _ in range(satellite_count_per_orbit * count_of_orbit):
            satellite_name = file.readline().strip()

            current_entry = {"satellite_name": satellite_name}

            for _ in range(2):
                tle_line = file.readline().strip()
                if tle_line.startswith("1 "):
                    current_entry["line1"] = tle_line
                elif tle_line.startswith("2 "):
                    current_entry["line2"] = tle_line

            two_line_element_file.parsed_tles.append(current_entry)

        file.close()

    return two_line_element_file
