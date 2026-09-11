from collections import deque
from fractions import Fraction

from .models import Amount, Demand, Topology, positive_amount

Edge = tuple[str, str]


class NetworkState:
    """Capacity usage accumulated by decisions already made."""

    def __init__(self, topology: Topology):
        self.topology = topology
        self._capacity: dict[Edge, Fraction] = {}
        adjacency: dict[str, list[str]] = {node: [] for node in topology.nodes}
        for link in topology.links:
            edge = self.edge_key(link.source, link.target)
            self._capacity[edge] = link.capacity
            adjacency[link.source].append(link.target)
            if not topology.directed:
                adjacency[link.target].append(link.source)
        self.adjacency = {node: tuple(sorted(neighbors)) for node, neighbors in adjacency.items()}
        self.usage = {edge: Fraction(0) for edge in self._capacity}

    def edge_key(self, source: str, target: str) -> Edge:
        return (source, target) if self.topology.directed else tuple(sorted((source, target)))

    def path_edges(self, path: tuple[str, ...]) -> tuple[Edge, ...]:
        if len(path) < 2 or len(path) != len(set(path)):
            raise ValueError("a rota deve ser um caminho simples com pelo menos dois nós")
        if any(b not in self.adjacency.get(a, ()) for a, b in zip(path, path[1:])):
            raise ValueError("a rota contém um enlace inexistente ou no sentido incorreto")
        return tuple(self.edge_key(a, b) for a, b in zip(path, path[1:]))

    def validate_demand(self, demand: Demand) -> None:
        if demand.source not in self.adjacency or demand.target not in self.adjacency:
            raise ValueError(f"demanda {demand.id} referencia nó inexistente")

    def residual(self, source: str, target: str) -> Fraction:
        edge = self.edge_key(source, target)
        return self._capacity[edge] - self.usage[edge]

    def can_allocate(self, path: tuple[str, ...], bandwidth: Amount) -> bool:
        bandwidth = positive_amount(bandwidth, "banda")
        return all(bandwidth <= self._capacity[e] - self.usage[e] for e in self.path_edges(path))

    def allocate(self, path: tuple[str, ...], bandwidth: Amount) -> None:
        bandwidth = positive_amount(bandwidth, "banda")
        projected = {edge: self.usage[edge] + bandwidth for edge in self.path_edges(path)}
        if any(used > self._capacity[edge] for edge, used in projected.items()):
            raise ValueError("alocação excederia a capacidade de pelo menos um enlace")
        # Commit only after validating every link; no partial writes on failure.
        self.usage.update(projected)

    def projected_path_max_utilization(self, path: tuple[str, ...], bandwidth: Amount) -> float:
        bandwidth = positive_amount(bandwidth, "banda")
        return float(max((self.usage[e] + bandwidth) / self._capacity[e] for e in self.path_edges(path)))

    def max_utilization(self) -> float:
        return float(max((self.usage[e] / self._capacity[e] for e in self._capacity), default=0))

    def has_topological_path(self, source: str, target: str) -> bool:
        queue = deque([source])
        visited = {source}
        while queue:
            node = queue.popleft()
            if node == target:
                return True
            for neighbor in self.adjacency[node]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        return False
