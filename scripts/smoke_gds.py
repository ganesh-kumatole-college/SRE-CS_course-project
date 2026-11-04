from __future__ import annotations

import getpass
import os
from uuid import uuid4

from neo4j import GraphDatabase


def main() -> None:
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    username = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD") or getpass.getpass(
        "Neo4j password: "
    )
    run_id = uuid4().hex
    graph_name = f"misdetSmoke{run_id}"
    label = f"MisdetSmoke{run_id}"
    nodes_created = False
    graph_created = False

    with GraphDatabase.driver(uri, auth=(username, password)) as driver:
        driver.verify_connectivity()
        with driver.session() as session:
            try:
                session.run(
                    f"""
                    UNWIND range(0, 4) AS id
                    CREATE (node:{label} {{id: id}})
                    WITH collect(node) AS nodes
                    UNWIND range(0, 4) AS index
                    WITH nodes[index] AS source,
                         nodes[(index + 1) % size(nodes)] AS target
                    CREATE (source)-[:SMOKE_LINK]->(target)
                    """
                ).consume()
                nodes_created = True

                projection = session.run(
                    """
                    CALL gds.graph.project($graph_name, $label, 'SMOKE_LINK')
                    YIELD graphName, nodeCount, relationshipCount
                    RETURN graphName, nodeCount, relationshipCount
                    """,
                    graph_name=graph_name,
                    label=label,
                ).single()
                if projection is None:
                    raise RuntimeError("Graph projection returned no result.")
                graph_created = True
                if projection["nodeCount"] != 5:
                    raise RuntimeError(
                        f"Expected 5 projected nodes, got {projection['nodeCount']}."
                    )

                result = session.run(
                    """
                    CALL gds.node2vec.stream($graph_name, $config)
                    YIELD embedding
                    RETURN count(embedding) AS node_count,
                           min(size(embedding)) AS min_dimension,
                           max(size(embedding)) AS max_dimension
                    """,
                    graph_name=graph_name,
                    config={
                        "embeddingDimension": 128,
                        "walkLength": 5,
                        "walksPerNode": 2,
                        "windowSize": 3,
                        "randomSeed": 42,
                    },
                ).single()
                if result is None:
                    raise RuntimeError("Node2Vec returned no result.")
                if result["node_count"] != 5 or result["min_dimension"] != 128:
                    raise RuntimeError(f"Unexpected Node2Vec output: {dict(result)}.")
                print(
                    "Node2Vec smoke test passed: "
                    f"{result['node_count']} nodes, "
                    f"{result['min_dimension']} dimensions."
                )
            finally:
                try:
                    if graph_created:
                        session.run(
                            "CALL gds.graph.drop($graph_name, false)",
                            graph_name=graph_name,
                        ).consume()
                finally:
                    if nodes_created:
                        session.run(
                            f"MATCH (node:{label}) DETACH DELETE node"
                        ).consume()


if __name__ == "__main__":
    main()
