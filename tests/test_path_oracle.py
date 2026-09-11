"""Independent exhaustive current-demand oracle using node permutations."""

import unittest
from fractions import Fraction
from itertools import permutations

from online_routing.algorithms import _candidate_paths, heuristic_route, shortest_path_route
from online_routing.models import Demand, Link, Topology
from online_routing.network import NetworkState


class PathOracleTests(unittest.TestCase):
    def test_all_small_graphs_against_independent_path_enumeration(self):
        nodes = ("A", "B", "C", "D")
        # 64 undirected + 64 directed graphs, each tested for all 12 ordered pairs.
        for directed in (False, True):
            edges = (("A", "B"), ("A", "C"), ("A", "D"), ("B", "C"), ("B", "D"), ("C", "D"))
            if directed:
                edges = (("A", "B"), ("B", "A"), ("B", "D"), ("A", "C"), ("C", "D"), ("D", "C"))
            for mask in range(64):
                links = tuple(Link(a, b, 2 + index % 3) for index, (a, b) in enumerate(edges) if mask & (1 << index))
                topology = Topology(nodes, links, directed)
                # Independent expected capacities and loads (some links are full).
                capacity = {}
                load = {}
                for index, link in enumerate(links):
                    arc = (link.source, link.target)
                    capacity[arc] = link.capacity
                    load[arc] = link.capacity * Fraction(index % 3, 2)
                    if not directed:
                        capacity[arc[::-1]] = capacity[arc]
                        load[arc[::-1]] = load[arc]
                for source, target in permutations(nodes, 2):
                    with self.subTest(directed=directed, mask=mask, source=source, target=target):
                        demand = Demand("d", source, target, 1)
                        middle_nodes = [node for node in nodes if node not in (source, target)]
                        feasible = []
                        for count in range(len(middle_nodes) + 1):
                            for middle in permutations(middle_nodes, count):
                                path = (source,) + middle + (target,)
                                arcs = list(zip(path, path[1:]))
                                if all(arc in capacity and load[arc] + 1 <= capacity[arc] for arc in arcs):
                                    feasible.append(path)
                        feasible.sort(key=lambda path: (len(path), path))
                        for algorithm in ("baseline", "heuristic"):
                            state = NetworkState(topology)
                            for index, link in enumerate(links):
                                used = link.capacity * Fraction(index % 3, 2)
                                if used:
                                    state.allocate((link.source, link.target), used)
                            before = state.usage.copy()
                            if algorithm == "baseline":
                                decision = shortest_path_route(demand, state)
                                expected = feasible[0] if feasible else None
                            else:
                                self.assertEqual(_candidate_paths(demand, state, 2), feasible[:2])
                                scores = []
                                for path in feasible[:2]:
                                    projected = float(max(
                                        (load[arc] + 1) / capacity[arc] for arc in zip(path, path[1:])
                                    ))
                                    scores.append((len(path) - 1 + 5 * projected, len(path), path))
                                expected = min(scores)[2] if scores else None
                                decision = heuristic_route(demand, state, 1, 5, 2)
                                if scores:
                                    self.assertEqual(decision.score, min(scores)[0])
                            self.assertEqual(decision.path, expected)
                            self.assertEqual(decision.accepted, expected is not None)
                            expected_load = before.copy()
                            if expected:
                                for a, b in zip(expected, expected[1:]):
                                    edge = (a, b) if directed else tuple(sorted((a, b)))
                                    expected_load[edge] += 1
                            self.assertEqual(state.usage, expected_load)
                            self.assertLessEqual(state.max_utilization(), 1)


if __name__ == "__main__":
    unittest.main()
