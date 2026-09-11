from .models import RouteDecision
from .network import NetworkState


def calculate_metrics(decisions: list[RouteDecision], state: NetworkState) -> dict[str, int | float]:
    accepted = [decision for decision in decisions if decision.accepted]
    total_hops = sum(len(decision.path or ()) - 1 for decision in accepted)
    return {
        "total_demands": len(decisions),
        "accepted_demands": len(accepted),
        "rejected_demands": len(decisions) - len(accepted),
        "total_hops": total_hops,
        "average_hops": total_hops / len(accepted) if accepted else 0.0,
        "maximum_link_utilization": state.max_utilization(),
    }

