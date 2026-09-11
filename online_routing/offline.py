"""Exact offline minimax routing for the small Challenge 2 instances."""

from dataclasses import dataclass
from fractions import Fraction

from .models import Demand, Topology
from .network import Edge, NetworkState


@dataclass(frozen=True)
class OfflineResult:
    feasible: bool
    maximum_utilization: Fraction | None
    paths: tuple[tuple[str, ...], ...] | None
    explored_states: int


def _all_feasible_simple_paths(
    state: NetworkState, demand: Demand
) -> tuple[tuple[str, ...], ...]:
    paths: list[tuple[str, ...]] = []
    stack = [(demand.source, (demand.source,))]
    while stack:
        node, path = stack.pop()
        if node == demand.target:
            paths.append(path)
            continue
        for neighbor in reversed(state.adjacency[node]):
            if neighbor not in path and demand.bandwidth <= state._capacity[state.edge_key(node, neighbor)]:
                stack.append((neighbor, path + (neighbor,)))
    return tuple(sorted(paths, key=lambda path: (len(path), path)))


def solve_offline_minimax(topology: Topology, demands: list[Demand]) -> OfflineResult:
    """Globally minimize maximum link utilization without rejecting demands.

    This is exhaustive branch-and-bound over every feasible simple path, so a
    returned solution is exact. It is intended only for small instances.
    """
    state = NetworkState(topology)
    if not demands:
        return OfflineResult(True, Fraction(0), (), 1)

    candidates = [_all_feasible_simple_paths(state, demand) for demand in demands]
    if any(not paths for paths in candidates):
        return OfflineResult(False, None, None, 0)

    edge_order = tuple(sorted(state.usage))
    capacity = state._capacity
    path_edges = [
        tuple((path, state.path_edges(path)) for path in paths) for paths in candidates
    ]

    # Reordering is internal to the exact search and does not change the global problem.
    search_order = sorted(
        range(len(demands)),
        key=lambda index: (-demands[index].bandwidth, len(candidates[index]), demands[index].id, index),
    )
    universal_lower_bound = max(
        min(
            max(demands[index].bandwidth / capacity[edge] for edge in edges)
            for _, edges in path_edges[index]
        )
        for index in range(len(demands))
    )

    usage = {edge: Fraction(0) for edge in edge_order}
    selected: list[tuple[str, ...] | None] = [None] * len(demands)
    best_value: Fraction | None = None
    best_paths: tuple[tuple[str, ...], ...] | None = None
    explored = 0
    memo: dict[tuple[int, tuple[Fraction, ...]], Fraction] = {}

    def current_maximum() -> Fraction:
        return max((usage[edge] / capacity[edge] for edge in edge_order), default=Fraction(0))

    def visit(position: int) -> None:
        nonlocal best_value, best_paths, explored
        explored += 1
        current = current_maximum()
        if best_value is not None and current >= best_value:
            return
        if position == len(search_order):
            best_value = current
            best_paths = tuple(path for path in selected if path is not None)
            return

        key = (position, tuple(usage[edge] for edge in edge_order))
        if key in memo and memo[key] <= current:
            return
        memo[key] = current

        demand_index = search_order[position]
        demand = demands[demand_index]
        choices = []
        for path, edges in path_edges[demand_index]:
            projected = {edge: usage[edge] + demand.bandwidth for edge in edges}
            if any(projected[edge] > capacity[edge] for edge in edges):
                continue
            projected_max = max(
                current,
                max(projected[edge] / capacity[edge] for edge in edges),
            )
            choices.append((projected_max, len(path), path, edges))
        choices.sort()

        for _, _, path, edges in choices:
            for edge in edges:
                usage[edge] += demand.bandwidth
            selected[demand_index] = path
            visit(position + 1)
            selected[demand_index] = None
            for edge in edges:
                usage[edge] -= demand.bandwidth
            if best_value == universal_lower_bound:
                return

    visit(0)
    if best_value is None or best_paths is None:
        return OfflineResult(False, None, None, explored)
    return OfflineResult(True, best_value, best_paths, explored)

