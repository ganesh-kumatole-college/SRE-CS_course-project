"""Pure-Python Node2Vec fallback for IAM policy graphs."""

from __future__ import annotations

import hashlib
from collections.abc import Collection, Mapping
from typing import Any

import networkx as nx
import numpy as np
from gensim.models import Word2Vec

from misdet.graph import PolicyGraph


def _prepare_training_graph(
    policy_graph: PolicyGraph,
    training_policy_ids: Collection[str],
) -> tuple[nx.Graph, list[str], list[str], nx.Graph]:
    graph = policy_graph.to_networkx().to_undirected()
    policy_nodes = sorted(
        node_id for node_id, attrs in graph.nodes(data=True) if attrs.get("kind") == "Policy"
    )
    if isinstance(training_policy_ids, (str, bytes)) or not isinstance(
        training_policy_ids, Collection
    ):
        raise TypeError("training_policy_ids must be a collection of policy node IDs")
    if any(not isinstance(node_id, str) for node_id in training_policy_ids):
        raise TypeError("training_policy_ids must contain only strings")

    training_nodes = set(training_policy_ids)
    if not training_nodes and policy_nodes:
        raise ValueError("training_policy_ids must include at least one normal policy")
    unknown = sorted(training_nodes - set(policy_nodes))
    if unknown:
        raise ValueError(f"Unknown training policy node IDs: {unknown}")

    context_nodes = {
        neighbor
        for policy_node in training_nodes
        for neighbor in graph.neighbors(policy_node)
        if graph.nodes[neighbor].get("kind") != "Policy"
    }
    training_graph = graph.subgraph(training_nodes | context_nodes).copy()
    return graph, policy_nodes, sorted(training_nodes), training_graph


def _assemble_policy_vectors(
    graph: nx.Graph,
    policy_nodes: list[str],
    training_policy_nodes: Collection[str],
    trained_vectors: Mapping[str, np.ndarray],
    *,
    dimensions: int,
) -> np.ndarray:
    training_set = set(training_policy_nodes)
    vectors = np.zeros((len(policy_nodes), dimensions), dtype=float)
    for index, policy_node in enumerate(policy_nodes):
        if policy_node in training_set:
            if policy_node in trained_vectors:
                vectors[index] = trained_vectors[policy_node]
            continue

        context_nodes = sorted(
            neighbor
            for neighbor in graph.neighbors(policy_node)
            if graph.nodes[neighbor].get("kind") != "Policy" and neighbor in trained_vectors
        )
        if not context_nodes:
            raise ValueError(
                f"No trained context embedding is available for inference policy "
                f"{policy_node!r}; include a training policy with shared context"
            )
        vectors[index] = np.mean([trained_vectors[node_id] for node_id in context_nodes], axis=0)
    return np.nan_to_num(vectors, nan=0.0, posinf=0.0, neginf=0.0)


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
    training_policy_ids: Collection[str],
    config: Mapping[str, Any] | None = None,
    seed: int | None = None,
) -> tuple[np.ndarray, list[str]]:
    """Fit on training policies and infer other policy vectors from shared context.

    ``training_policy_ids`` contains canonical policy node IDs, such as
    ``Policy:example``. The returned matrix remains ordered by all policy node IDs.
    """
    if not isinstance(policy_graph, PolicyGraph):
        raise TypeError("policy_graph must be a PolicyGraph instance")

    resolved = load_node2vec_config(config, seed=seed)
    graph, policy_nodes, training_nodes, training_graph = _prepare_training_graph(
        policy_graph, training_policy_ids
    )

    if not policy_nodes:
        empty = np.zeros((0, resolved["dimensions"]), dtype=float)
        return empty, []

    walks = _build_walks(
        training_graph,
        training_nodes,
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

    trained_vectors: dict[str, np.ndarray] = {}
    for node_id in training_graph.nodes:
        if node_id in model.wv:
            trained_vectors[node_id] = np.asarray(model.wv[node_id], dtype=float)
    for node_id in training_nodes:
        if node_id in trained_vectors:
            trained_vectors[node_id] = trained_vectors[node_id] + 0.5 * _policy_signature(
                training_graph,
                node_id,
                dimensions=resolved["dimensions"],
                seed=resolved["seed"],
            )

    vectors = _assemble_policy_vectors(
        graph,
        policy_nodes,
        training_nodes,
        trained_vectors,
        dimensions=resolved["dimensions"],
    )
    return vectors, policy_nodes
