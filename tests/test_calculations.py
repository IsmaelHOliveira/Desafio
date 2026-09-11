import re
import unittest

from online_routing.algorithms import heuristic_route
from online_routing.evaluation import compare_algorithms
from online_routing.models import Demand, Link, Topology
from online_routing.network import NetworkState


class CalculationTests(unittest.TestCase):
    def test_baseline_uses_longer_path_when_shortcut_is_full(self):
        topology = Topology(("A", "B", "D"), (
            Link("A", "D", 1), Link("A", "B", 4), Link("B", "D", 4),
        ))
        result = compare_algorithms(topology, [Demand("1", "A", "D", 2)])
        for name in ("shortest_path", "heuristic"):
            self.assertEqual(result[name]["decisions"][0]["path"], ["A", "B", "D"])

    def test_projected_utilization_uses_ratios_and_only_candidate_edges(self):
        topology = Topology(("A", "B", "D", "X", "Y"), (
            Link("A", "D", 5), Link("A", "B", 10), Link("B", "D", 20), Link("X", "Y", 1),
        ))
        state = NetworkState(topology)
        state.allocate(("B", "D"), 6)
        state.allocate(("X", "Y"), 1)
        before = state.usage.copy()
        # Direct: 4/5=0.8, score=1+5*0.8=5.
        # Via B: max(4/10, (6+4)/20)=0.5, score=2+5*0.5=4.5.
        self.assertEqual(state.projected_path_max_utilization(("A", "B", "D"), 4), 0.5)
        self.assertEqual(state.usage, before)
        decision = heuristic_route(Demand("d", "A", "D", 4), state, 1, 5)
        self.assertEqual(decision.path, ("A", "B", "D"))
        self.assertEqual(decision.score, 4.5)
        self.assertEqual(state.max_utilization(), 1.0)  # The unrelated X-Y link is still full.
        self.assertEqual(state.usage[("B", "D")], 10)
        self.assertEqual(state.usage[("A", "D")], 0)

    def test_weights_and_candidate_limit_change_actual_selection(self):
        topology = Topology(("A", "B", "D"), (
            Link("A", "D", 10), Link("A", "B", 20), Link("B", "D", 20),
        ))
        demand = Demand("d", "A", "D", 5)
        # The tie at beta=4 scores 3 for both routes; fewer hops wins.
        for alpha, beta, limit, expected in (
            (1, 0, 8, ("A", "D")), (0, 1, 8, ("A", "B", "D")),
            (1, 4, 8, ("A", "D")), (1, 5, 8, ("A", "B", "D")),
            (1, 5, 1, ("A", "D")),
        ):
            with self.subTest(alpha=alpha, beta=beta, limit=limit):
                result = compare_algorithms(topology, [demand], alpha, beta, limit)
                self.assertEqual(result["heuristic"]["decisions"][0]["path"], list(expected))
                self.assertEqual(result["configuration"]["alpha"], alpha)
                self.assertEqual(result["configuration"]["beta"], beta)
                self.assertEqual(result["configuration"]["candidate_limit"], limit)

    def test_explanation_can_be_recalculated_without_hidden_rounding(self):
        state = NetworkState(Topology(("A", "B"), (Link("A", "B", 3),)))
        decision = heuristic_route(Demand("d", "A", "B", 1), state, 1.123456789, 100)
        match = re.search(r"score=([^*]+)\*(\d+)\+([^*]+)\*([^=]+)=([^ ]+)\. ", decision.explanation)
        self.assertIsNotNone(match)
        alpha, hops, beta, projected, score = map(float, match.groups())
        self.assertEqual(alpha, 1.123456789)
        self.assertEqual(hops, 1)
        self.assertEqual(projected, 1 / 3)
        self.assertEqual(alpha * hops + beta * projected, score)
        self.assertEqual(score, decision.score)
        self.assertIn("A -> B entre 1 caminho(s)", decision.explanation)

    def test_overflowing_score_is_reported_before_allocation(self):
        for alpha in (1e308, 10 ** 308):
            state = NetworkState(Topology(("A", "B", "C"), (Link("A", "B", 2), Link("B", "C", 2))))
            with self.assertRaisesRegex(ValueError, "score"):
                heuristic_route(Demand("d", "A", "C", 1), state, alpha, 1)
            self.assertEqual(state.max_utilization(), 0)

    def test_every_final_metric_matches_a_manual_two_link_case(self):
        topology = Topology(("A", "B", "C"), (Link("A", "B", 5), Link("B", "C", 4)))
        result = compare_algorithms(topology, [
            Demand("1", "A", "C", 2), Demand("2", "A", "B", 1), Demand("3", "A", "C", 3),
        ])
        # Routes: A-B-C (2 hops), A-B (1 hop), rejected; loads: 3/5 and 2/4.
        for name in ("shortest_path", "heuristic"):
            self.assertEqual(result[name]["metrics"], {
                "total_demands": 3, "accepted_demands": 2, "rejected_demands": 1,
                "total_hops": 3, "average_hops": 1.5, "maximum_link_utilization": 0.6,
            })

    def test_empty_and_all_rejected_inputs_have_zero_metrics(self):
        topology = Topology(("A", "B"), ())
        for demands in ([], [Demand("d", "A", "B", 1)]):
            result = compare_algorithms(topology, demands)
            for name in ("shortest_path", "heuristic"):
                self.assertEqual(result[name]["metrics"], {
                    "total_demands": len(demands), "accepted_demands": 0,
                    "rejected_demands": len(demands), "total_hops": 0,
                    "average_hops": 0.0, "maximum_link_utilization": 0.0,
                })


if __name__ == "__main__":
    unittest.main()
