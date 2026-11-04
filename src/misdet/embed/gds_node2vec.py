"""Neo4j Graph Data Science Node2Vec backend."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import uuid4

import numpy as np

from misdet.graph import PolicyGraph

from .py_node2vec import embed_policy_nodes, load_node2vec_config

_NODE_LABEL_PREFIX = "MisdetEmbedding"
_EDGE_TYPE = "MISDET_EMBED_EDGE"


def _gds_config(config: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "embeddingDimension": config["dimensions"],
        "walkLength": config["walk_length"],
        "walksPerNode": config["walks_per_node"],
        "returnFactor": config["return_factor"],
        "inOutFactor": config["in_out_factor"],
        "windowSize": config["window_size"],
        "randomSeed": config["seed"],
    }


def embed_policy_nodes_with_gds(
    policy_graph: PolicyGraph,
    *,
    config: Mapping[str, Any] | None = None,
    seed: int | None = None,
    uri: str | None = None,
    user: str | None = None,
    password: str | None = None,
) -> tuple[np.ndarray, list[str]]:
    """Run GDS Node2Vec when connection settings are supplied, otherwise use Python."""
    if not isinstance(policy_graph, PolicyGraph):
        raise TypeError("policy_graph must be a PolicyGraph instance")

    supplied_connection = any(value is not None for value in (uri, user, password))
    if not supplied_connection:
        return embed_policy_nodes(policy_graph, config=config, seed=seed)
    if not isinstance(uri, str) or not uri.strip():
        raise ValueError("uri must be supplied when requesting the GDS backend")
    if not isinstance(user, str) or not user:
        raise ValueError("user must be supplied when requesting the GDS backend")
    if not isinstance(password, str) or not password:
        raise ValueError("password must be supplied when requesting the GDS backend")

    resolved = load_node2vec_config(config, seed=seed)
    if resolved["dimensions"] <= 0:
        raise ValueError("dimensions must be positive")
    if resolved["walk_length"] <= 0 or resolved["walks_per_node"] <= 0:
        raise ValueError("walk_length and walks_per_node must be positive")
    if resolved["window_size"] <= 0:
        raise ValueError("window_size must be positive")
    if resolved["return_factor"] <= 0 or resolved["in_out_factor"] <= 0:
        raise ValueError("return_factor and in_out_factor must be positive")

    policy_nodes = sorted(
        node.node_id for node in policy_graph.nodes if node.kind == "Policy"
    )
    if not policy_nodes:
        return np.zeros((0, resolved["dimensions"]), dtype=float), []

    try:
        from neo4j import GraphDatabase
    except ImportError as exc:  # pragma: no cover - dependency is pinned by the project
        raise RuntimeError("The neo4j driver is not installed for the GDS backend") from exc

    run_id = uuid4().hex
    node_label = f"{_NODE_LABEL_PREFIX}{run_id}"
    graph_name = f"misdetEmbedding{run_id}"
    nodes_created = False
    graph_projected = False

    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        with driver.session() as session:
            nodes = [
                {"node_id": node.node_id, "kind": node.kind}
                for node in policy_graph.nodes
            ]
            edges = [
                {"source": edge.source, "target": edge.target, "label": edge.label}
                for edge in policy_graph.edges
            ]

            session.run(
                f"""
                UNWIND $nodes AS row
                CREATE (node:{node_label} {{
                    nodeId: row.node_id,
                    kind: row.kind
                }})
                """,
                nodes=nodes,
            ).consume()
            nodes_created = True

            if edges:
                session.run(
                    f"""
                    UNWIND $edges AS row
                    MATCH (source:{node_label} {{nodeId: row.source}})
                    MATCH (target:{node_label} {{nodeId: row.target}})
                    CREATE (source)-[:{_EDGE_TYPE} {{label: row.label}}]->(target)
                    """,
                    edges=edges,
                ).consume()

            projection = session.run(
                """
                CALL gds.graph.project($graph_name, $node_label, $edge_type)
                YIELD nodeCount, relationshipCount
                RETURN nodeCount, relationshipCount
                """,
                graph_name=graph_name,
                node_label=node_label,
                edge_type=_EDGE_TYPE,
            ).single()
            if projection is None:
                raise RuntimeError("GDS graph projection returned no result")
            graph_projected = True
            if projection["nodeCount"] != len(nodes) or projection[
                "relationshipCount"
            ] != len(edges):
                raise RuntimeError(
                    "GDS graph projection count mismatch: "
                    f"expected {len(nodes)} nodes and {len(edges)} edges, "
                    f"got {projection['nodeCount']} nodes and "
                    f"{projection['relationshipCount']} edges"
                )

            # Procedure parameters follow the current GDS Node2Vec stream API:
            # https://neo4j.com/docs/graph-data-science/current/algorithms/node2vec/
            result = session.run(
                """
                CALL gds.node2vec.stream($graph_name, $config)
                YIELD nodeId, embedding
                RETURN gds.util.asNode(nodeId).nodeId AS node_id,
                       gds.util.asNode(nodeId).kind AS kind,
                       embedding
                """,
                graph_name=graph_name,
                config=_gds_config(resolved),
            )

            embeddings: dict[str, np.ndarray] = {}
            for record in result:
                if record["kind"] != "Policy":
                    continue
                node_id = record["node_id"]
                vector = np.asarray(record["embedding"], dtype=float)
                if node_id not in policy_nodes:
                    raise RuntimeError(f"GDS returned an unknown policy node: {node_id!r}")
                if node_id in embeddings:
                    raise RuntimeError(f"GDS returned a duplicate policy node: {node_id!r}")
                if vector.shape != (resolved["dimensions"],):
                    raise RuntimeError(
                        f"GDS returned an invalid embedding for {node_id!r}: "
                        f"expected {resolved['dimensions']} dimensions, "
                        f"got {vector.shape}"
                    )
                if not np.isfinite(vector).all():
                    raise RuntimeError(f"GDS returned a non-finite embedding for {node_id!r}")
                embeddings[node_id] = vector

            missing = sorted(set(policy_nodes) - embeddings.keys())
            if missing:
                raise RuntimeError(f"GDS returned no embeddings for policy nodes: {missing}")
            vectors = np.vstack([embeddings[node_id] for node_id in policy_nodes])
            return vectors, policy_nodes
    finally:
        try:
            if graph_projected:
                with driver.session() as session:
                    session.run(
                        "CALL gds.graph.drop($graph_name, false)",
                        graph_name=graph_name,
                    ).consume()
        finally:
            try:
                if nodes_created:
                    with driver.session() as session:
                        session.run(
                            f"MATCH (node:{node_label}) DETACH DELETE node"
                        ).consume()
            finally:
                driver.close()
