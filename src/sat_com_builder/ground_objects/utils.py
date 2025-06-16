from sat_com_builder.models import GroundObjectData


def generate_ground_object_from_file(file_path: str) -> list[GroundObjectData]:
    """
    Read and add every ground object from a file.
    :param file_path:
    :return:
    """
    ground_objects = list()
    with open(file_path, "r") as file:
        for line in file:
            split = line.split(",")
            if len(split) != 5:
                raise ValueError("Basic ground station file has 5 columns")

            ground_object = GroundObjectData(
                id=int(split[0]),
                label=split[1],
                longitude=float(split[3]),
                latitude=float(split[2]),
                altitude=float(split[4]),
            )
            ground_objects.append(ground_object)

        file.close()

    return ground_objects
