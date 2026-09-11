import heapq
import math
from collections import deque

from .models import Demand, RouteDecision
from .network import NetworkState


def validate_parameters(alpha: float, beta: float, candidate_limit: int) -> None:
    for weight in (alpha, beta):
        if isinstance(weight, bool) or not isinstance(weight, (int, float)):
            raise ValueError("alpha e beta devem ser números finitos")
        try:
            finite = math.isfinite(weight)
        except OverflowError:
            finite = False
        if not finite or weight < 0:
            raise ValueError("alpha e beta devem ser finitos e não negativos")
    if alpha == 0 and beta == 0:
        raise ValueError("ao menos um de alpha e beta deve ser positivo")
    if isinstance(candidate_limit, bool) or not isinstance(candidate_limit, int) or candidate_limit < 1:
        raise ValueError("candidate_limit deve ser um inteiro positivo")


def _rejection(demand: Demand, state: NetworkState) -> RouteDecision:
    if state.has_topological_path(demand.source, demand.target):
        reason = "capacidade residual insuficiente em todos os caminhos"
    else:
        reason = "não existe caminho topológico entre origem e destino"
    return RouteDecision(demand.id, False, None, reason, f"Demanda rejeitada: {reason}.")


def shortest_path_route(demand: Demand, state: NetworkState) -> RouteDecision:
    """Breadth-first shortest feasible path, with deterministic tie breaking."""
    state.validate_demand(demand)
    queue = deque([(demand.source,)])
    visited = {demand.source}
    while queue:
        path = queue.popleft()
        node = path[-1]
        if node == demand.target:
            state.allocate(path, demand.bandwidth)
            hops = len(path) - 1
            return RouteDecision(
                demand.id, True, path, "aceita",
                f"Menor caminho viável com {hops} salto(s): {' -> '.join(path)}.",
                float(hops),
            )
        for neighbor in state.adjacency[node]:
            if neighbor not in visited and demand.bandwidth <= state.residual(node, neighbor):
                visited.add(neighbor)
                queue.append(path + (neighbor,))
    return _rejection(demand, state)


def _candidate_paths(demand: Demand, state: NetworkState, limit: int) -> list[tuple[str, ...]]:
    # The heap orders first by hops and then by the complete path tuple.
    heap: list[tuple[int, tuple[str, ...]]] = [(0, (demand.source,))]
    candidates: list[tuple[str, ...]] = []
    while heap and len(candidates) < limit:
        _, path = heapq.heappop(heap)
        node = path[-1]
        if node == demand.target:
            candidates.append(path)
            continue
        for neighbor in state.adjacency[node]:
            if neighbor not in path and demand.bandwidth <= state.residual(node, neighbor):
                new_path = path + (neighbor,)
                heapq.heappush(heap, (len(new_path) - 1, new_path))
    return candidates


def heuristic_route(
    demand: Demand,
    state: NetworkState,
    alpha: float,
    beta: float,
    candidate_limit: int = 8,
) -> RouteDecision:
    """Choose the lowest score among the first k feasible simple paths."""
    validate_parameters(alpha, beta, candidate_limit)
    state.validate_demand(demand)
    candidates = _candidate_paths(demand, state, candidate_limit)
    if not candidates:
        return _rejection(demand, state)

    ranked = []
    for path in candidates:
        hops = len(path) - 1
        projected = state.projected_path_max_utilization(path, demand.bandwidth)
        try:
            score = alpha * hops + beta * projected
        except OverflowError as exc:
            raise ValueError("score fora do intervalo numérico; reduza alpha e beta") from exc
        if not math.isfinite(score):
            raise ValueError("score fora do intervalo numérico; reduza alpha e beta")
        ranked.append((score, hops, path, projected))
    score, hops, path, projected = min(ranked)
    state.allocate(path, demand.bandwidth)
    explanation = (
        f"Escolhida {' -> '.join(path)} entre {len(candidates)} caminho(s) viável(is): "
        f"hops={hops}, utilização máxima projetada={projected!r}, "
        f"score={alpha!r}*{hops}+{beta!r}*{projected!r}={score!r}. "
        "Menor score; empates por saltos e ordem lexicográfica."
    )
    return RouteDecision(demand.id, True, path, "aceita", explanation, score)
