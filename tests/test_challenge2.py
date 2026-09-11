import csv
import json
import tempfile
import unittest
from fractions import Fraction
from itertools import product
from pathlib import Path

from online_routing.adversarial import family_instance, random_instance
from online_routing.algorithms import heuristic_route
from online_routing.challenge2 import evaluate_instance, run_experiments
from online_routing.models import Demand, Link, Topology
from online_routing.network import NetworkState
from online_routing.offline import _all_feasible_simple_paths, solve_offline_minimax


class OfflineSolverTests(unittest.TestCase):
    def test_offline_reports_infeasible_when_all_demands_cannot_fit(self):
        topology = Topology(("A", "B"), (Link("A", "B", 2),))
        result = solve_offline_minimax(
            topology, [Demand("1", "A", "B", 2), Demand("2", "A", "B", 1)]
        )
        self.assertFalse(result.feasible)
        self.assertIsNone(result.maximum_utilization)
        self.assertIsNone(result.paths)

    def test_exact_solver_matches_independent_cartesian_oracle(self):
        topology = Topology(("A", "B", "C", "D"), (
            Link("A", "B", 4), Link("B", "D", 3),
            Link("A", "C", 5), Link("C", "D", 4), Link("B", "C", 2),
        ))
        demands = [
            Demand("1", "A", "D", 2), Demand("2", "A", "D", 1),
            Demand("3", "B", "C", 1),
        ]
        state = NetworkState(topology)
        candidates = [_all_feasible_simple_paths(state, demand) for demand in demands]
        capacity = state._capacity
        oracle_value = None
        oracle_paths = None
        for paths in product(*candidates):
            usage = {edge: Fraction(0) for edge in capacity}
            feasible = True
            for demand, path in zip(demands, paths):
                for edge in state.path_edges(path):
                    usage[edge] += demand.bandwidth
                    feasible &= usage[edge] <= capacity[edge]
            if not feasible:
                continue
            value = max(usage[edge] / capacity[edge] for edge in capacity)
            if oracle_value is None or value < oracle_value:
                oracle_value, oracle_paths = value, paths
        exact = solve_offline_minimax(topology, demands)
        self.assertTrue(exact.feasible)
        self.assertEqual(exact.maximum_utilization, oracle_value)
        self.assertEqual(len(exact.paths or ()), len(oracle_paths or ()))

    def test_family_values_are_exact_and_online_heuristic_is_unchanged(self):
        for n, expected_ratio in ((4, 1), (10, 1), (12, 2), (20, 3)):
            topology, demands = family_instance(n)
            result = evaluate_instance(topology, demands, 1, 5, 8, f"family(n={n})")
            self.assertEqual(result.optimum_value, Fraction(1, n - 2))
            self.assertEqual(result.heuristic_value, Fraction(expected_ratio, n - 2))
            self.assertEqual(result.ratio, expected_ratio)
            state = NetworkState(topology)
            direct_paths = tuple(
                heuristic_route(demand, state, 1, 5, 8).path for demand in demands
            )
            self.assertEqual(result.heuristic_paths, direct_paths)

    def test_ratio_is_infinite_if_online_rejects_but_optimum_routes_all(self):
        topology = Topology(("A", "B", "C", "D"), (
            Link("A", "B", 1), Link("B", "D", 1),
            Link("A", "C", 1), Link("C", "D", 1),
        ))
        result = evaluate_instance(
            topology, [Demand("1", "A", "D", 1), Demand("2", "B", "D", 1)],
            1, 5, 8, "manual",
        )
        self.assertIsNone(result.ratio)
        self.assertTrue(result.ratio_infinite)
        self.assertEqual(result.optimum_value, 1)
        self.assertEqual(result.heuristic_paths, (("A", "B", "D"), None))

    def test_instance_infeasible_for_both_is_excluded(self):
        topology = Topology(("A", "B"), (Link("A", "B", 1),))
        result = evaluate_instance(
            topology, [Demand("1", "A", "B", 1), Demand("2", "A", "B", 1)],
            1, 5, 8, "manual",
        )
        self.assertIsNone(result.ratio)
        self.assertFalse(result.ratio_infinite)
        self.assertIn("ótimo", result.exclusion_reason or "")


class Challenge2IntegrationTests(unittest.TestCase):
    def test_seeded_search_is_reproducible_and_saves_every_trial(self):
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first = run_experiments(Path(first_dir), seed=42, trials=5, family_sizes=(4, 12))
            second = run_experiments(Path(second_dir), seed=42, trials=5, family_sizes=(4, 12))
            self.assertEqual(first, second)
            for name in (
                "challenge2_summary.csv", "challenge2_family.csv",
                "challenge2_search.csv", "challenge2_worst_instance.json",
            ):
                self.assertEqual(
                    (Path(first_dir) / name).read_bytes(), (Path(second_dir) / name).read_bytes()
                )
            with (Path(first_dir) / "challenge2_search.csv").open(encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 5)
            self.assertTrue(all(row["status"] in ("finite", "infinite", "excluded") for row in rows))
            worst = json.loads((Path(first_dir) / "challenge2_worst_instance.json").read_text(encoding="utf-8"))
            self.assertEqual(worst["ratio"], first["summary"]["worst_ratio"])
            self.assertEqual(worst["ratio_exact"], first["summary"]["worst_ratio_exact"])

    def test_random_generator_changes_dimensions_and_is_seeded(self):
        import random

        first_rng = random.Random(7)
        second_rng = random.Random(7)
        first = [random_instance(first_rng, index) for index in range(10)]
        second = [random_instance(second_rng, index) for index in range(10)]
        self.assertEqual(first, second)
        self.assertGreater(len({len(topology.nodes) for topology, _ in first}), 1)
        self.assertGreater(len({tuple(link.capacity for link in topology.links) for topology, _ in first}), 1)
        self.assertGreater(len({tuple((d.source, d.target, d.bandwidth) for d in demands) for _, demands in first}), 1)


if __name__ == "__main__":
    unittest.main()
