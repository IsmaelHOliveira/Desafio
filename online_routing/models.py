from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction

Amount = int | float | Decimal | Fraction


def positive_amount(value: Amount, label: str) -> Fraction:
    """Preserve decimal quantities exactly; floats use their decimal spelling."""
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal, Fraction)):
        raise ValueError(f"{label} deve ser um número positivo e finito")
    try:
        amount = Fraction(str(value))
    except (ValueError, OverflowError) as exc:
        raise ValueError(f"{label} deve ser um número positivo e finito") from exc
    if amount <= 0:
        raise ValueError(f"{label} deve ser um número positivo e finito")
    return amount


def _validate_name(name: str) -> None:
    if not isinstance(name, str) or not name.strip():
        raise ValueError("identificadores devem ser strings não vazias")


@dataclass(frozen=True)
class Link:
    source: str
    target: str
    capacity: Amount

    def __post_init__(self) -> None:
        _validate_name(self.source)
        _validate_name(self.target)
        if self.source == self.target:
            raise ValueError("autoenlaces não são suportados")
        object.__setattr__(self, "capacity", positive_amount(self.capacity, "capacidade"))


@dataclass(frozen=True)
class Demand:
    id: str
    source: str
    target: str
    bandwidth: Amount

    def __post_init__(self) -> None:
        for name in (self.id, self.source, self.target):
            _validate_name(name)
        if self.source == self.target:
            raise ValueError(f"demanda {self.id} deve ter origem diferente do destino")
        object.__setattr__(self, "bandwidth", positive_amount(self.bandwidth, "banda"))


@dataclass(frozen=True)
class Topology:
    nodes: tuple[str, ...]
    links: tuple[Link, ...]
    directed: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.directed, bool):
            raise ValueError("o campo directed deve ser booleano")
        if not isinstance(self.nodes, (list, tuple)) or not isinstance(self.links, (list, tuple)):
            raise ValueError("nodes e links devem ser sequências")
        object.__setattr__(self, "nodes", tuple(self.nodes))
        object.__setattr__(self, "links", tuple(self.links))
        for node in self.nodes:
            _validate_name(node)
        if not self.nodes or len(self.nodes) != len(set(self.nodes)):
            raise ValueError("a lista de nós deve ser não vazia e não conter duplicatas")
        seen_edges = set()
        for link in self.links:
            if not isinstance(link, Link):
                raise ValueError("links deve conter enlaces Link")
            if link.source not in self.nodes or link.target not in self.nodes:
                raise ValueError(f"enlace {link.source}-{link.target} referencia nó inexistente")
            edge = (link.source, link.target)
            if not self.directed:
                edge = tuple(sorted(edge))
            if edge in seen_edges:
                raise ValueError(f"enlace duplicado: {link.source}-{link.target}")
            seen_edges.add(edge)


@dataclass(frozen=True)
class RouteDecision:
    demand_id: str
    accepted: bool
    path: tuple[str, ...] | None
    reason: str
    explanation: str
    score: float | None = None
