def get_topology_object_cesium_unique_identifier(
    topology_object_identifier: int,
) -> str:
    return "topology-object_{id}".format(id=topology_object_identifier)


def get_link_cesium_unique_identifier(
    topology_object_id_a: int, topology_object_id_b: int
) -> str:
    return "link-from-{link_a}-{link_b}".format(
        link_a=topology_object_id_a, link_b=topology_object_id_b
    )
