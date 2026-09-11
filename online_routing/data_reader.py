import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from .models import Demand, Link, Topology


def _load_json(path: str | Path) -> Any:
    try:
        with Path(path).open(encoding="utf-8-sig") as stream:
            return json.load(stream, parse_float=Decimal, parse_constant=_reject_constant)
    except (OSError, ValueError) as exc:
        raise ValueError(f"não foi possível ler {path}: {exc}") from exc


def _reject_constant(value: str) -> None:
    raise ValueError(f"constante inválida em JSON: {value}")


def _identifier(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError("identificadores devem ser strings ou inteiros")
    if not str(value).strip():
        raise ValueError("identificadores não podem ser vazios")
    return str(value)


def read_topology(path: str | Path) -> Topology:
    data = _load_json(path)
    if not isinstance(data, dict):
        raise ValueError("o arquivo de topologia deve conter um objeto JSON")
    if not isinstance(data.get("nodes"), list) or not isinstance(data.get("links"), list):
        raise ValueError("nodes e links devem ser listas JSON")
    try:
        nodes = tuple(_identifier(node) for node in data["nodes"])
        links = tuple(
            Link(_identifier(item["source"]), _identifier(item["target"]), item["capacity"])
            for item in data["links"]
        )
        directed = data.get("directed", False)
        return Topology(nodes=nodes, links=links, directed=directed)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"topologia inválida em {path}: {exc}") from exc


def read_demands(path: str | Path, topology: Topology) -> list[Demand]:
    data = _load_json(path)
    if not isinstance(data, list):
        raise ValueError("o arquivo de demandas deve conter uma lista JSON")
    demands: list[Demand] = []
    ids: set[str] = set()
    node_set = set(topology.nodes)
    for index, item in enumerate(data):
        try:
            demand = Demand(
                id=_identifier(item["id"]),
                source=_identifier(item["source"]),
                target=_identifier(item["target"]),
                bandwidth=item["bandwidth"],
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"demanda inválida na posição {index}: {exc}") from exc
        if demand.id in ids:
            raise ValueError(f"id de demanda duplicado: {demand.id}")
        if demand.source not in node_set or demand.target not in node_set:
            raise ValueError(f"demanda {demand.id} referencia nó inexistente")
        ids.add(demand.id)
        demands.append(demand)
    return demands
