import unittest
from uuid import UUID

import networkx as nx

from sat_com_adapter.discrete_event_emitter.discrete_event import DiscreteEventManager
from sat_com_adapter.discrete_event_emitter.models import TopologyChangeEvent


class TestDiscreteEventManager(unittest.TestCase):
    def test_generate_change_event_detects_changes(self):
        manager = DiscreteEventManager()

        g1 = nx.Graph()
        g1.add_node("A", label="Node A")
        g1.add_node("B", label="Node B")
        g1.add_edge("A", "B", capacity=100)

        manager.former_network_xgraph = g1

        g2 = nx.Graph()
        g2.graph["current_simulation_date"] = "2025-05-19 12:00:00.000"
        g2.add_node("B", label="Node B")
        g2.add_node("C", label="Node C")
        g2.add_edge("B", "C", capacity=200)

        event = manager.generate_change_event(g2)

        self.assertIsInstance(event, TopologyChangeEvent)
        self.assertEqual(event.date, "2025-05-19 12:00:00.000")
        self.assertIsInstance(event.id, UUID)

        self.assertEqual(event.nodes_to_remove, [{"A": {"label": "Node A"}}])
        self.assertEqual(event.nodes_to_add, [{"C": {"label": "Node C"}}])

        self.assertEqual(
            event.links_to_remove,
            [{"source": "A", "target": "B", "attributes": {"capacity": 100}}],
        )
        self.assertEqual(
            event.links_to_add,
            [{"source": "B", "target": "C", "attributes": {"capacity": 200}}],
        )
