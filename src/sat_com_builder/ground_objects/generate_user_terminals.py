from sat_com_builder.ground_objects.utils import generate_ground_object_from_file
from sat_com_model.models import (
    UserTerminal,
    create_user_terminal,
)


def generate_user_terminal_from_file(
    user_terminal_file_path: str,
) -> list[UserTerminal]:
    """
    Reads ground stations from the input file.

    :param user_terminal_file_path: Filename of ground stations basic (typically /path/to/ground_stations.txt)

    :return: List of ground stations
    """
    user_terminals = list()

    user_terminal_objects = generate_ground_object_from_file(user_terminal_file_path)

    for user_terminal_object in user_terminal_objects:
        user_terminal = create_user_terminal(
            user_terminal_object.id, user_terminal_object.label
        )
        user_terminal.set_position(
            longitude=user_terminal_object.longitude,
            latitude=user_terminal_object.latitude,
            altitude=user_terminal_object.altitude,
        )
        user_terminals.append(user_terminal)

    return user_terminals
