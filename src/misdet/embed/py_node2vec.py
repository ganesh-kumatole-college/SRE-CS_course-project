"""Pure-Python Node2Vec fallback for IAM policy graphs."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

import networkx as nx
import numpy as np
from gensim.models import Word2Vec

from misdet.graph import PolicyGraph


def load_node2vec_config(
    config: Mapping[str, Any] | None = None,
    *,
    seed: int | None = None,
) -> dict[str, Any]:
    """Resolve the effective Node2Vec configuration from the caller and project defaults."""
    resolved: dict[str, Any] = {
        "dimensions": 128,
        "walk_length": 80,
        "walks_per_node": 10,
        "return_factor": 1.0,
        "in_out_factor": 1.0,
        "window_size": 10,
        "seed": 42,
    }

    if config:
        for key, value in config.items():
            if key in resolved:
                resolved[key] = value

    if seed is not None:
        resolved["seed"] = int(seed)

    resolved["dimensions"] = int(resolved["dimensions"])
    resolved["walk_length"] = int(resolved["walk_length"])
    resolved["walks_per_node"] = int(resolved["walks_per_node"])
    resolved["window_size"] = int(resolved["window_size"])
    resolved["return_factor"] = float(resolved["return_factor"])
    resolved["in_out_factor"] = float(resolved["in_out_factor"])
    resolved["seed"] = int(resolved["seed"])
    return resolved


def _select_next_node(
    graph: nx.DiGraph,
    current: str,
    previous: str | None,
    *,
    return_factor: float,
    in_out_factor: float,
    rng: np.random.Generator,
) -> str:
    neighbors = list(graph.neighbors(current))
    if not neighbors:
        raise ValueError(f"Node {current!r} has no outgoing neighbors")

    if previous is None:
        return str(rng.choice(neighbors))

    weights: list[float] = []
    for neighbor in neighbors:
        if neighbor == previous:
            weight = 1.0 / max(return_factor, 1e-9)
        elif previous in graph[neighbor]:
            weight = 1.0
        else:
            weight = 1.0 / max(in_out_factor, 1e-9)
        weights.append(weight)

    total = float(sum(weights))
    if total == 0.0:
        return str(rng.choice(neighbors))

    probabilities = np.asarray(weights, dtype=float) / total
    return str(rng.choice(neighbors, p=probabilities))


def _build_walks(
    graph: nx.DiGraph,
    policy_nodes: list[str],
    *,
    walk_length: int,
    walks_per_node: int,
    return_factor: float,
    in_out_factor: float,
    seed: int,
) -> list[list[str]]:
    rng = np.random.default_rng(seed)
    walks: list[list[str]] = []

    for policy_node in policy_nodes:
        for _ in range(walks_per_node):
            walk = [policy_node]
            previous: str | None = None
            current = policy_node

            for _ in range(walk_length - 1):
                neighbors = list(graph.neighbors(current))
                if not neighbors:
                    break

                next_node = _select_next_node(
                    graph,
                    current,
                    previous,
                    return_factor=return_factor,
                    in_out_factor=in_out_factor,
                    rng=rng,
                )
                walk.append(next_node)
                previous, current = current, next_node

            walks.append(walk)

    return walks


def _policy_signature(
    graph: nx.DiGraph,
    policy_node: str,
    *,
    dimensions: int,
    seed: int,
) -> np.ndarray:
    signature = np.zeros(dimensions, dtype=float)
    neighbors = sorted(graph.neighbors(policy_node))
    if not neighbors:
        return signature

    for index, neighbor in enumerate(neighbors, start=1):
        digest = hashlib.sha256(f"{seed}:{policy_node}:{neighbor}".encode()).digest()
        for offset in range(0, 16, 2):
            base_index = int.from_bytes(digest[offset : offset + 2], byteorder="big", signed=False)
            signature[base_index % dimensions] += 1.0 / index

    return signature / max(np.linalg.norm(signature), 1e-9)


def embed_policy_nodes(
    policy_graph: PolicyGraph,
    *,
    config: Mapping[str, Any] | None = None,
    seed: int | None = None,
) -> tuple[np.ndarray, list[str]]:
    """Embed policy nodes as a deterministic 128-D vector matrix."""
    if not isinstance(policy_graph, PolicyGraph):
        raise TypeError("policy_graph must be a PolicyGraph instance")

    resolved = load_node2vec_config(config, seed=seed)
    graph = policy_graph.to_networkx().to_undirected()

    policy_nodes = sorted(
        node_id
        for node_id, attrs in graph.nodes(data=True)
        if attrs.get("kind") == "Policy"
    )

    if not policy_nodes:
        empty = np.zeros((0, resolved["dimensions"]), dtype=float)
        return empty, []

    walks = _build_walks(
        graph,
        policy_nodes,
        walk_length=resolved["walk_length"],
        walks_per_node=resolved["walks_per_node"],
        return_factor=resolved["return_factor"],
        in_out_factor=resolved["in_out_factor"],
        seed=resolved["seed"],
    )

    model = Word2Vec(
        sentences=walks,
        vector_size=resolved["dimensions"],
        window=resolved["window_size"],
        min_count=0,
        sg=1,
        workers=1,
        seed=resolved["seed"],
    )

    vectors = np.zeros((len(policy_nodes), resolved["dimensions"]), dtype=float)
    for index, node_id in enumerate(policy_nodes):
        if node_id in model.wv:
            vectors[index] = model.wv[node_id]
        vectors[index] += 0.5 * _policy_signature(
            graph,
            node_id,
            dimensions=resolved["dimensions"],
            seed=resolved["seed"],
        )

    vectors = np.nan_to_num(vectors, nan=0.0, posinf=0.0, neginf=0.0)
    return vectors, policy_nodes
