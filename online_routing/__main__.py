import argparse
import json
import sys

from .data_reader import read_demands, read_topology
from .evaluation import compare_algorithms


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Avalia roteamento online determinístico")
    parser.add_argument("--topology", required=True, help="arquivo JSON da topologia")
    parser.add_argument("--demands", required=True, help="arquivo JSON das demandas")
    parser.add_argument("--alpha", type=float, default=1.0, help="peso dos saltos")
    parser.add_argument("--beta", type=float, default=5.0, help="peso do congestionamento")
    parser.add_argument("--candidates", type=int, default=8, help="máximo de caminhos candidatos")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        topology = read_topology(args.topology)
        demands = read_demands(args.demands, topology)
        result = compare_algorithms(topology, demands, args.alpha, args.beta, args.candidates)
    except ValueError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    # Keep redirected JSON and error messages portable on Windows too.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
