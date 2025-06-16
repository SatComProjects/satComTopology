import datetime

import networkx as nx

from sat_com_adapter.discrete_event_emitter.models import TopologyChangeEvent


class DiscreteEventManager:

    def __init__(self):
        self.former_network_xgraph = nx.Graph()

    def generate_change_event(self, new_graph: nx.Graph) -> TopologyChangeEvent:
        """
        Compares two NetworkX graphs and generates a topology_change_event of the differences.

        Args:
            new_graph: The new graph (NetworkX Graph object).

        Returns:
            TopologyChangeEvent: An object containing the differences between the two graphs.
        """

        former_graph = self.former_network_xgraph

        if not isinstance(new_graph, nx.Graph):
            raise TypeError("new_graph must be a NetworkX Graph object.")
        if not isinstance(former_graph, nx.Graph):
            raise TypeError("former_graph must be a NetworkX Graph object.")

        nodes_to_remove = set(former_graph.nodes) - set(new_graph.nodes)
        nodes_to_add = set(new_graph.nodes) - set(former_graph.nodes)

        links_to_remove = set(former_graph.edges) - set(new_graph.edges)
        links_to_add = set(new_graph.edges) - set(former_graph.edges)

        nodes_to_remove_dicts = [
            {node_id: former_graph.nodes[node_id]} for node_id in nodes_to_remove
        ]
        nodes_to_add_dicts = [
            {node_id: new_graph.nodes[node_id]} for node_id in nodes_to_add
        ]

        links_to_remove_dicts = [
            {"source": u, "target": v, "attributes": former_graph.edges[u, v]}
            for u, v in links_to_remove
        ]
        links_to_add_dicts = [
            {"source": u, "target": v, "attributes": new_graph.edges[u, v]}
            for u, v in links_to_add
        ]
        topology_change_event = TopologyChangeEvent(
            date=new_graph.graph.get(
                "current_simulation_date",
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            ),
            nodes_to_add=nodes_to_add_dicts,
            nodes_to_remove=nodes_to_remove_dicts,
            links_to_add=links_to_add_dicts,
            links_to_remove=links_to_remove_dicts,
        )
        return topology_change_event
