import unittest
from fractions import Fraction

from online_routing.algorithms import heuristic_route, shortest_path_route
from online_routing.evaluation import compare_algorithms
from online_routing.models import Demand, Link, Topology
from online_routing.network import NetworkState


class OnlineBehaviorTests(unittest.TestCase):
    def test_future_demands_cannot_change_any_prefix_decision(self):
        topology = Topology(("A", "B", "C", "D"), (
            Link("A", "B", 5), Link("B", "D", 5),
            Link("A", "C", 5), Link("C", "D", 5),
        ))
        prefix = [Demand("p1", "A", "D", 3), Demand("p2", "A", "D", 2)]
        for suffix in (
            [Demand("f1", "A", "B", 5)],
            [Demand("f2", "A", "C", 5), Demand("f3", "B", "D", 100)],
        ):
            extended = compare_algorithms(topology, prefix + suffix)
            for length in range(1, len(prefix) + 1):
                truncated = compare_algorithms(topology, prefix[:length])
                for name in ("shortest_path", "heuristic"):
                    with self.subTest(suffix=suffix, length=length, algorithm=name):
                        self.assertEqual(
                            truncated[name]["decisions"], extended[name]["decisions"][:length],
                        )

    def test_order_is_arrival_order_and_states_are_independent(self):
        topology = Topology(("A", "B"), (Link("A", "B", 5),))
        demands = [Demand("z-first", "A", "B", 5), Demand("a-second", "A", "B", 1)]
        original = list(demands)
        result = compare_algorithms(topology, demands)
        self.assertEqual(result["configuration"]["processing_order"], ["z-first", "a-second"])
        self.assertEqual(demands, original)
        self.assertEqual(topology.links[0].capacity, 5)
        for name in ("shortest_path", "heuristic"):
            self.assertEqual([d["accepted"] for d in result[name]["decisions"]], [True, False])
        reversed_result = compare_algorithms(topology, list(reversed(demands)))
        for name in ("shortest_path", "heuristic"):
            self.assertEqual(reversed_result[name]["decisions"][0]["demand_id"], "a-second")
            self.assertTrue(reversed_result[name]["decisions"][0]["accepted"])
            self.assertFalse(reversed_result[name]["decisions"][1]["accepted"])

    def test_load_is_added_once_per_edge_and_rejection_changes_nothing(self):
        topology = Topology(("A", "B", "C"), (Link("A", "B", 5), Link("B", "C", 3)))
        demands = [
            Demand("d1", "A", "C", 2), Demand("d2", "C", "A", 2),
            Demand("d3", "C", "A", 1),
        ]
        for router in (shortest_path_route, lambda d, s: heuristic_route(d, s, 1, 5)):
            state = NetworkState(topology)
            for demand, accepted, expected_usage in zip(demands, (True, False, True), (2, 2, 3)):
                decision = router(demand, state)
                self.assertEqual(decision.accepted, accepted)
                self.assertEqual(state.usage, {("A", "B"): expected_usage, ("B", "C"): expected_usage})
                self.assertEqual(state.residual("B", "C"), 3 - expected_usage)
                if not accepted:
                    self.assertIn("capacidade residual", decision.reason)
                    self.assertIsNone(decision.path)

    def test_directed_arcs_have_independent_capacity(self):
        topology = Topology(("A", "B", "C"), (
            Link("A", "B", 2), Link("B", "A", 3), Link("B", "C", 1),
        ), directed=True)
        demands = [
            Demand("1", "A", "B", 2), Demand("2", "B", "A", 3),
            Demand("3", "A", "B", 1), Demand("4", "C", "B", 1),
        ]
        result = compare_algorithms(topology, demands)
        for name in ("shortest_path", "heuristic"):
            decisions = result[name]["decisions"]
            self.assertEqual([d["accepted"] for d in decisions], [True, True, False, False])
            self.assertIn("capacidade residual", decisions[2]["reason"])
            self.assertIn("não existe caminho topológico", decisions[3]["reason"])

    def test_reordering_input_nodes_and_links_does_not_change_ties(self):
        topology = Topology(("A", "B", "C", "D"), (
            Link("A", "C", 3), Link("C", "D", 3),
            Link("A", "B", 3), Link("B", "D", 3),
        ))
        reordered = Topology(tuple(reversed(topology.nodes)), tuple(
            Link(link.target, link.source, link.capacity) for link in reversed(topology.links)
        ))
        demands = [Demand("1", "A", "D", 2)]
        first = compare_algorithms(topology, demands)
        self.assertEqual(first, compare_algorithms(reordered, demands))
        for name in ("shortest_path", "heuristic"):
            self.assertEqual(first[name]["decisions"][0]["path"], ["A", "B", "D"])

    def test_repeated_small_decimal_demands_cannot_exceed_capacity(self):
        topology = Topology(("A", "B"), (Link("A", "B", 1),))
        for router in (shortest_path_route, lambda d, s: heuristic_route(d, s, 1, 5)):
            state = NetworkState(topology)
            for index in range(11):
                decision = router(Demand(str(index), "A", "B", 0.1), state)
                self.assertEqual(decision.accepted, index < 10)
                self.assertEqual(state.usage[("A", "B")], Fraction(min(index + 1, 10), 10))


if __name__ == "__main__":
    unittest.main()
