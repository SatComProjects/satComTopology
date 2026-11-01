from sat_com_builder.factories import DefaultUserTerminalFactory
from sat_com_builder.ground_objects.utils import generate_ground_object_from_file
from sat_com_builder.models import GroundObjectData
from sat_com_model.factories import AbstractUserTerminalFactory
from sat_com_model.models import UserTerminal, GroundObjectDomain


def generate_user_terminals_from_ground_objects(
    ground_objects: list[GroundObjectData],
    ground_object_domain: GroundObjectDomain = None,
    factory: AbstractUserTerminalFactory = None,
) -> list[UserTerminal]:
    """
    Build user terminals from ground object data.

    :param ground_objects: Ground object data (id, label, position).
    :param ground_object_domain: Ground object domain to use.
    :param factory: Factory used to build each user terminal. Defaults to DefaultUserTerminalFactory.
    :return: List of user terminals
    """
    factory = factory or DefaultUserTerminalFactory()
    return [
        factory.create_user_terminal(
            object_id=ground_object.id,
            label=ground_object.label,
            longitude=ground_object.longitude,
            latitude=ground_object.latitude,
            altitude=ground_object.altitude,
            ground_object_domain=ground_object_domain,
        )
        for ground_object in ground_objects
    ]


def generate_user_terminal_from_file(
    user_terminal_file_path: str,
    ground_object_domain: GroundObjectDomain = None,
    factory: AbstractUserTerminalFactory = None,
) -> list[UserTerminal]:
    """
    Reads user terminals from the input file.

    :param ground_object_domain: GroundObjectDomain to use
    :param user_terminal_file_path: Filename of user terminals (typically /path/to/user_terminals.txt)
    :param factory: Factory used to build each user terminal. Defaults to DefaultUserTerminalFactory.

    :return: List of user terminals
    """
    return generate_user_terminals_from_ground_objects(
        generate_ground_object_from_file(user_terminal_file_path),
        ground_object_domain=ground_object_domain,
        factory=factory,
    )
