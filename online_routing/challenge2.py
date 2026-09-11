"""Reproducible experimental competitive-ratio search."""

import argparse
import csv
import json
import random
import sys
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from .adversarial import family_instance, random_instance
from .algorithms import heuristic_route, validate_parameters
from .models import Demand, Topology
from .network import NetworkState
from .offline import solve_offline_minimax

DEFAULT_FAMILY_SIZES = (4, 6, 8, 10, 12, 14, 16, 18, 20)


@dataclass(frozen=True)
class ExperimentResult:
    source: str
    network_size: int
    heuristic_value: Fraction | None
    optimum_value: Fraction | None
    ratio: Fraction | None
    heuristic_paths: tuple[tuple[str, ...] | None, ...] | None
    optimum_paths: tuple[tuple[str, ...], ...] | None
    offline_explored_states: int
    ratio_infinite: bool = False
    exclusion_reason: str | None = None


def _maximum_utilization_exact(state: NetworkState) -> Fraction:
    return max(
        (state.usage[edge] / state._capacity[edge] for edge in state.usage),
        default=Fraction(0),
    )


def evaluate_instance(
    topology: Topology,
    demands: list[Demand],
    alpha: float,
    beta: float,
    candidate_limit: int,
    source: str,
) -> ExperimentResult:
    """Run the unchanged online heuristic, then the exact offline solver."""
    validate_parameters(alpha, beta, candidate_limit)
    online_state = NetworkState(topology)
    decisions = [
        heuristic_route(demand, online_state, alpha, beta, candidate_limit)
        for demand in demands
    ]
    online_paths = tuple(decision.path for decision in decisions)
    offline = solve_offline_minimax(topology, demands)
    if not all(decision.accepted for decision in decisions):
        if offline.feasible:
            return ExperimentResult(
                source, len(topology.nodes), None, offline.maximum_utilization, None,
                online_paths, offline.paths, offline.explored_states, True,
                "heurística inviável, mas ótimo offline viável",
            )
        return ExperimentResult(
            source, len(topology.nodes), None, None, None,
            online_paths, None, offline.explored_states, False,
            "instância inviável também para o ótimo offline",
        )
    if not offline.feasible or offline.maximum_utilization is None:
        raise AssertionError("heurística encontrou solução, mas solver offline declarou inviável")
    heuristic_value = _maximum_utilization_exact(online_state)
    ratio = heuristic_value / offline.maximum_utilization if offline.maximum_utilization else Fraction(1)
    if ratio < 1:
        raise AssertionError("ótimo offline não pode ser pior que a heurística")
    return ExperimentResult(
        source, len(topology.nodes), heuristic_value, offline.maximum_utilization,
        ratio, online_paths, offline.paths, offline.explored_states,
    )


def _number(value: Fraction | None) -> float | None:
    return float(value) if value is not None else None


def _instance_json(
    topology: Topology, demands: list[Demand], result: ExperimentResult, configuration: dict
) -> dict:
    return {
        "configuration": configuration,
        "source": result.source,
        "topology": {
            "directed": topology.directed,
            "nodes": list(topology.nodes),
            "links": [
                {"source": link.source, "target": link.target, "capacity": float(link.capacity)}
                for link in topology.links
            ],
        },
        "demands": [
            {"id": d.id, "source": d.source, "target": d.target, "bandwidth": float(d.bandwidth)}
            for d in demands
        ],
        "heuristic_maximum_utilization": _number(result.heuristic_value),
        "optimum_maximum_utilization": _number(result.optimum_value),
        "ratio": _number(result.ratio),
        "ratio_exact": "infinity" if result.ratio_infinite else (
            str(result.ratio) if result.ratio is not None else None
        ),
        "ratio_infinite": result.ratio_infinite,
        "heuristic_paths": [list(path) if path is not None else None for path in result.heuristic_paths or ()],
        "heuristic_rejected_demands": [
            demand.id
            for demand, path in zip(demands, result.heuristic_paths or ())
            if path is None
        ],
        "optimum_paths": [list(path) for path in result.optimum_paths or ()],
        "offline_explored_states": result.offline_explored_states,
    }


def _write_csv(path: Path, rows: list[dict], fieldnames: tuple[str, ...]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def run_experiments(
    output_dir: Path,
    seed: int = 20260910,
    trials: int = 80,
    family_sizes: tuple[int, ...] = DEFAULT_FAMILY_SIZES,
    alpha: float = 1.0,
    beta: float = 5.0,
    candidate_limit: int = 8,
) -> dict:
    validate_parameters(alpha, beta, candidate_limit)
    if trials < 0:
        raise ValueError("trials deve ser não negativo")
    if not family_sizes or any(n < 4 for n in family_sizes):
        raise ValueError("family_sizes deve conter tamanhos a partir de 4")
    output_dir.mkdir(parents=True, exist_ok=True)
    configuration = {
        "seed": seed, "trials": trials, "family_sizes": list(family_sizes),
        "alpha": alpha, "beta": beta, "candidate_limit": candidate_limit,
        "objective": "minimize maximum link utilization; route every demand",
    }

    candidates: list[tuple[Topology, list[Demand], ExperimentResult]] = []
    family_rows = []
    for n in family_sizes:
        topology, demands = family_instance(n)
        result = evaluate_instance(topology, demands, alpha, beta, candidate_limit, f"family(n={n})")
        candidates.append((topology, demands, result))
        family_rows.append({
            "n": n,
            "heuristic_maximum_utilization": _number(result.heuristic_value),
            "optimum_maximum_utilization": _number(result.optimum_value),
            "ratio": _number(result.ratio),
            "ratio_exact": str(result.ratio),
        })

    rng = random.Random(seed)
    searched = 0
    finite = 0
    infinite = 0
    excluded = 0
    search_rows = []
    for index in range(trials):
        topology, demands = random_instance(rng, index)
        result = evaluate_instance(topology, demands, alpha, beta, candidate_limit, f"random(trial={index})")
        searched += 1
        search_rows.append({
            "trial": index, "nodes": len(topology.nodes), "links": len(topology.links),
            "demands": len(demands),
            "heuristic_maximum_utilization": _number(result.heuristic_value),
            "optimum_maximum_utilization": _number(result.optimum_value),
            "ratio": _number(result.ratio),
            "ratio_exact": "infinity" if result.ratio_infinite else (
                str(result.ratio) if result.ratio is not None else ""
            ),
            "ratio_infinite": result.ratio_infinite,
            "status": "infinite" if result.ratio_infinite else (
                "finite" if result.ratio is not None else "excluded"
            ),
            "exclusion_reason": result.exclusion_reason or "",
        })
        if result.ratio is None and not result.ratio_infinite:
            excluded += 1
            continue
        if result.ratio_infinite:
            infinite += 1
        else:
            finite += 1
        candidates.append((topology, demands, result))

    eligible_candidates = [
        item for item in candidates if item[2].ratio is not None or item[2].ratio_infinite
    ]
    worst_topology, worst_demands, worst = max(
        eligible_candidates,
        key=lambda item: (
            item[2].ratio_infinite,
            item[2].ratio or Fraction(0),
            -item[2].network_size,
            item[2].source,
        ),
    )
    summary_rows = [{
        "seed": seed, "random_trials": searched, "random_finite": finite,
        "random_infinite": infinite, "random_excluded": excluded,
        "family_instances": len(family_rows),
        "worst_source": worst.source,
        "heuristic_maximum_utilization": _number(worst.heuristic_value),
        "optimum_maximum_utilization": _number(worst.optimum_value),
        "worst_ratio": _number(worst.ratio),
        "worst_ratio_exact": "infinity" if worst.ratio_infinite else str(worst.ratio),
        "worst_ratio_infinite": worst.ratio_infinite,
    }]
    _write_csv(
        output_dir / "challenge2_summary.csv", summary_rows, tuple(summary_rows[0])
    )
    _write_csv(output_dir / "challenge2_family.csv", family_rows, tuple(family_rows[0]))
    search_fields = (
        "trial", "nodes", "links", "demands", "heuristic_maximum_utilization",
        "optimum_maximum_utilization", "ratio", "ratio_exact",
        "ratio_infinite", "status", "exclusion_reason",
    )
    _write_csv(output_dir / "challenge2_search.csv", search_rows, search_fields)
    (output_dir / "challenge2_worst_instance.json").write_text(
        json.dumps(
            _instance_json(worst_topology, worst_demands, worst, configuration),
            ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False,
        ) + "\n",
        encoding="utf-8",
    )
    return {"configuration": configuration, "summary": summary_rows[0], "family": family_rows}


def _family_sizes(value: str) -> tuple[int, ...]:
    try:
        return tuple(int(item) for item in value.split(",") if item)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("use inteiros separados por vírgula") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Busca experimental de casos adversariais")
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    parser.add_argument("--seed", type=int, default=20260910)
    parser.add_argument("--trials", type=int, default=80)
    parser.add_argument("--family-sizes", type=_family_sizes, default=DEFAULT_FAMILY_SIZES)
    parser.add_argument("--alpha", type=float, default=1.0)
    parser.add_argument("--beta", type=float, default=5.0)
    parser.add_argument("--candidates", type=int, default=8)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        result = run_experiments(
            args.output_dir, args.seed, args.trials, args.family_sizes,
            args.alpha, args.beta, args.candidates,
        )
    except ValueError as exc:
        print(f"Erro: {exc}")
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
