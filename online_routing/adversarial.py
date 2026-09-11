"""Deterministic instance generators for Challenge 2."""

import random

from .models import Demand, Link, Topology


def family_instance(n: int) -> tuple[Topology, list[Demand]]:
    """n-2 equal two-hop paths; k-limited online routing sees only the first k."""
    if n < 4:
        raise ValueError("n deve ser pelo menos 4")
    middle = tuple(f"p{index:02d}" for index in range(n - 2))
    capacity = n - 2
    topology = Topology(
        nodes=("s", "t") + middle,
        links=tuple(
            link
            for node in middle
            for link in (Link("s", node, capacity), Link(node, "t", capacity))
        ),
    )
    demands = [Demand(f"d{index:02d}", "s", "t", 1) for index in range(n - 2)]
    return topology, demands


def random_instance(rng: random.Random, index: int) -> tuple[Topology, list[Demand]]:
    """Create a connected small graph, then vary capacities, demands and order."""
    node_count = rng.randint(4, 7)
    nodes = tuple(f"v{node}" for node in range(node_count))
    pairs: set[tuple[int, int]] = set()
    for node in range(1, node_count):
        parent = rng.randrange(node)
        pairs.add((parent, node))
    possible = [(a, b) for a in range(node_count) for b in range(a + 1, node_count)]
    rng.shuffle(possible)
    for pair in possible[: rng.randint(0, node_count)]:
        pairs.add(pair)
    links = tuple(
        Link(nodes[a], nodes[b], rng.randint(2, 7)) for a, b in sorted(pairs)
    )
    topology = Topology(nodes, links)
    demand_count = rng.randint(2, 6)
    demands = []
    for demand_index in range(demand_count):
        source, target = rng.sample(nodes, 2)
        demands.append(
            Demand(f"r{index:03d}-d{demand_index}", source, target, rng.randint(1, 3))
        )
    rng.shuffle(demands)
    return topology, demands

