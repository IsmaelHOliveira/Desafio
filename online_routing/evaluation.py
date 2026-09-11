from dataclasses import asdict
from functools import partial
from typing import Callable

from .algorithms import heuristic_route, shortest_path_route, validate_parameters
from .metrics import calculate_metrics
from .models import Demand, RouteDecision, Topology
from .network import NetworkState

Router = Callable[[Demand, NetworkState], RouteDecision]


def _run(topology: Topology, demands: list[Demand], router: Router) -> dict:
    state = NetworkState(topology)
    decisions: list[RouteDecision] = []
    # Only the current demand and accumulated network state are exposed to the router.
    for demand in demands:
        decisions.append(router(demand, state))
    serialized = []
    for decision in decisions:
        item = asdict(decision)
        item["path"] = list(decision.path) if decision.path else None
        serialized.append(item)
    return {"metrics": calculate_metrics(decisions, state), "decisions": serialized}


def compare_algorithms(
    topology: Topology,
    demands: list[Demand],
    alpha: float = 1.0,
    beta: float = 5.0,
    candidate_limit: int = 8,
) -> dict:
    validate_parameters(alpha, beta, candidate_limit)
    heuristic = partial(
        heuristic_route, alpha=alpha, beta=beta, candidate_limit=candidate_limit
    )
    return {
        "configuration": {
            "alpha": alpha,
            "beta": beta,
            "candidate_limit": candidate_limit,
            "processing_order": [demand.id for demand in demands],
        },
        "shortest_path": _run(topology, demands, shortest_path_route),
        "heuristic": _run(topology, demands, heuristic),
    }
