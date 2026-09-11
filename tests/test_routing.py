import unittest

from online_routing.algorithms import heuristic_route, shortest_path_route
from online_routing.evaluation import compare_algorithms
from online_routing.models import Demand, Link, Topology
from online_routing.network import NetworkState


def sample_topology() -> Topology:
    return Topology(
        nodes=("A", "B", "C", "D", "E"),
        links=(
            Link("A", "B", 10), Link("B", "D", 10),
            Link("A", "C", 10), Link("C", "E", 10), Link("E", "D", 10),
        ),
    )


class RoutingTests(unittest.TestCase):
    def test_shortest_path_rejects_instead_of_exceeding_capacity(self):
        state = NetworkState(Topology(("A", "B"), (Link("A", "B", 5),)))
        first = shortest_path_route(Demand("d1", "A", "B", 4), state)
        second = shortest_path_route(Demand("d2", "A", "B", 2), state)

        self.assertTrue(first.accepted)
        self.assertFalse(second.accepted)
        self.assertIn("capacidade residual", second.reason)
        for edge, used in state.usage.items():
            self.assertLessEqual(used, state._capacity[edge])

    def test_heuristic_can_choose_longer_less_congested_path(self):
        state = NetworkState(sample_topology())
        state.allocate(("A", "B", "D"), 6)

        decision = heuristic_route(Demand("d", "A", "D", 4), state, alpha=1, beta=10)

        self.assertEqual(decision.path, ("A", "C", "E", "D"))
        self.assertIn("utilização máxima projetada=0.4,", decision.explanation)

    def test_no_topological_path_has_specific_reason(self):
        topology = Topology(("A", "B", "C"), (Link("A", "B", 1),))
        state = NetworkState(topology)
        decision = shortest_path_route(Demand("d", "A", "C", 1), state)
        self.assertIn("não existe caminho topológico", decision.reason)

    def test_same_input_produces_same_result(self):
        demands = [
            Demand("d1", "A", "D", 6),
            Demand("d2", "A", "D", 4),
        ]
        first = compare_algorithms(sample_topology(), demands, alpha=1, beta=10)
        second = compare_algorithms(sample_topology(), demands, alpha=1, beta=10)
        self.assertEqual(first, second)

    def test_metrics_count_accepted_and_rejected(self):
        topology = Topology(("A", "B"), (Link("A", "B", 5),))
        result = compare_algorithms(topology, [
            Demand("d1", "A", "B", 4), Demand("d2", "A", "B", 2)
        ])
        metrics = result["heuristic"]["metrics"]
        self.assertEqual(metrics["accepted_demands"], 1)
        self.assertEqual(metrics["rejected_demands"], 1)
        self.assertEqual(metrics["total_hops"], 1)


if __name__ == "__main__":
    unittest.main()
