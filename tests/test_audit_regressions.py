"""Small counterexamples found during the audit (not generated expectations)."""

import json
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

from online_routing.algorithms import heuristic_route
from online_routing.data_reader import read_demands, read_topology
from online_routing.evaluation import compare_algorithms
from online_routing.models import Demand, Link, Topology
from online_routing.network import NetworkState


class AuditRegressionTests(unittest.TestCase):
    def test_decimal_demands_fill_capacity_exactly(self):
        topology = Topology(("A", "B"), (Link("A", "B", 0.3),))
        result = compare_algorithms(topology, [
            Demand("1", "A", "B", 0.1), Demand("2", "B", "A", 0.2),
            Demand("3", "A", "B", 0.00000000000000001),
        ])
        for name in ("shortest_path", "heuristic"):
            self.assertEqual([d["accepted"] for d in result[name]["decisions"]], [True, True, False])
            self.assertEqual(result[name]["metrics"], {
                "total_demands": 3, "accepted_demands": 2, "rejected_demands": 1,
                "total_hops": 2, "average_hops": 1.0, "maximum_link_utilization": 1.0,
            })

    def test_invalid_allocations_are_atomic(self):
        state = NetworkState(Topology(("A", "B", "C"), (
            Link("A", "B", 5), Link("B", "C", 2),
        )))
        for path, bandwidth in (
            (("A", "B"), -1), (("A", "B"), 0),
            (("A", "B", "A"), 4), (("A", "B", "C"), 3),
            (("A", "C"), 1), (("A",), 1), ((), 1),
            (("A", "B"), float("nan")), (("A", "B"), float("inf")),
            (("A", "B"), True),
        ):
            with self.subTest(path=path, bandwidth=bandwidth):
                before = state.usage.copy()
                with self.assertRaises(ValueError):
                    state.allocate(path, bandwidth)
                self.assertEqual(state.usage, before)

    def test_invalid_data_cannot_bypass_readers_through_direct_model_creation(self):
        for amount in (0, -1, True, float("nan"), float("inf")):
            with self.subTest(amount=amount):
                with self.assertRaises(ValueError):
                    Link("A", "B", amount)
                with self.assertRaises(ValueError):
                    Demand("d", "A", "B", amount)
        with self.assertRaises(ValueError):
            Topology(("A", "B"), (Link("A", "C", 1),))
        with self.assertRaises(ValueError):
            Topology(("A", "B"), (Link("A", "B", 1), Link("B", "A", 1)))

    def test_direct_heuristic_rejects_invalid_configuration(self):
        topology = Topology(("A", "B"), (Link("A", "B", 3),))
        for alpha, beta, limit in (
            (1, 5, 0), (1, 5, 1.5), (1, 5, True),
            (-1, 5, 8), (0, 0, 8), (1, float("nan"), 8),
        ):
            with self.subTest(alpha=alpha, beta=beta, limit=limit):
                state = NetworkState(topology)
                with self.assertRaises(ValueError):
                    heuristic_route(Demand("d", "A", "B", 1), state, alpha, beta, limit)
                self.assertEqual(state.max_utilization(), 0)

    def test_topology_requires_a_list_of_nodes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "topology.json"
            path.write_text(json.dumps({"nodes": "AB", "links": []}), encoding="utf-8")
            with self.assertRaises(ValueError):
                read_topology(path)

    def test_booleans_are_not_bandwidth_or_capacity(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            path.write_text(json.dumps({"nodes": ["A", "B"], "links": [
                {"source": "A", "target": "B", "capacity": True},
            ]}), encoding="utf-8")
            with self.assertRaises(ValueError):
                read_topology(path)
            topology = Topology(("A", "B"), (Link("A", "B", 3),))
            path.write_text(json.dumps([
                {"id": "d", "source": "A", "target": "B", "bandwidth": True},
            ]), encoding="utf-8")
            with self.assertRaises(ValueError):
                read_demands(path, topology)

    def test_external_decimal_precision_is_not_lost(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "topology.json"
            path.write_text(
                '{"nodes":["A","B"],"links":[{"source":"A","target":"B",'
                '"capacity":0.100000000000000001}]}', encoding="utf-8",
            )
            topology = read_topology(path)
            self.assertEqual(topology.links[0].capacity, Fraction("0.100000000000000001"))


if __name__ == "__main__":
    unittest.main()
