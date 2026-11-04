import numpy as np
import pytest

from misdet import embed
from misdet.embed import embed_policy_nodes
from misdet.graph import build_policy_graph


@pytest.fixture
def policy_graph():
    policies = [
        {
            "policy_id": "policy-similar-a",
            "org": "alpha",
            "source": "synthetic_custom",
            "document": {
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": ["s3:GetObject"],
                        "Resource": ["arn:aws:s3:::shared-bucket/*"],
                    }
                ]
            },
        },
        {
            "policy_id": "policy-similar-b",
            "org": "alpha",
            "source": "synthetic_custom",
            "document": {
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": ["s3:GetObject"],
                        "Resource": ["arn:aws:s3:::shared-bucket/*"],
                    }
                ]
            },
        },
        {
            "policy_id": "policy-different-c",
            "org": "alpha",
            "source": "synthetic_custom",
            "document": {
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": ["iam:CreateUser"],
                        "Resource": ["arn:aws:iam::*:user/*"],
                    }
                ]
            },
        },
    ]
    entities = [{"entity_id": "entity-01", "org": "alpha", "entity_type": "group"}]
    attachments = [{"entity_id": "entity-01", "policy_id": "policy-similar-a"}]
    return build_policy_graph(policies, entities=entities, attachments=attachments)


def test_embed_policy_nodes_returns_matrix(policy_graph):
    matrix, policy_ids = embed_policy_nodes(
        policy_graph,
        training_policy_ids=[
            "Policy:policy-similar-a",
            "Policy:policy-similar-b",
            "Policy:policy-different-c",
        ],
        config={"dimensions": 32, "walk_length": 12, "walks_per_node": 5, "seed": 7},
    )

    assert len(policy_ids) == 3
    assert matrix.shape == (3, 32)
    assert np.isfinite(matrix).all()
    assert not np.allclose(matrix[0], 0.0)


def test_embed_policy_nodes_is_repeatable(policy_graph):
    config = {"dimensions": 24, "walk_length": 10, "walks_per_node": 4, "seed": 13}
    training_policy_ids = [
        "Policy:policy-similar-a",
        "Policy:policy-similar-b",
        "Policy:policy-different-c",
    ]
    first, _ = embed_policy_nodes(
        policy_graph, training_policy_ids=training_policy_ids, config=config
    )
    second, _ = embed_policy_nodes(
        policy_graph, training_policy_ids=training_policy_ids, config=config
    )

    np.testing.assert_allclose(first, second)


def test_embed_policy_nodes_keeps_similar_policies_close(policy_graph):
    config = {"dimensions": 32, "walk_length": 12, "walks_per_node": 8, "seed": 11}
    matrix, _ = embed_policy_nodes(
        policy_graph,
        training_policy_ids=[
            "Policy:policy-similar-a",
            "Policy:policy-similar-b",
            "Policy:policy-different-c",
        ],
        config=config,
    )

    similar_distance = np.linalg.norm(matrix[0] - matrix[1])
    different_distance = np.linalg.norm(matrix[0] - matrix[2])

    assert similar_distance < different_distance


def test_embed_policy_nodes_rejects_non_policy_graph():
    with pytest.raises(TypeError):
        embed_policy_nodes({"not": "a graph"}, training_policy_ids=["Policy:example"])


def test_python_backend_excludes_inference_policies_and_averages_context(policy_graph, monkeypatch):
    observed_walks = []
    unseen_context = policy_graph.add_node("Action", "lambda:invokefunction")
    policy_graph.add_edge("Policy:policy-similar-b", unseen_context, "ALLOWS")

    class FakeWord2Vec:
        def __init__(self, *, sentences, **_kwargs):
            observed_walks.extend(sentences)
            tokens = {token for walk in sentences for token in walk}
            self.wv = {
                token: np.array([1.0, 3.0]) if token.startswith("Action:") else np.array([4.0, 6.0])
                for token in tokens
            }

    monkeypatch.setattr("misdet.embed.py_node2vec.Word2Vec", FakeWord2Vec)

    vectors, policy_ids = embed_policy_nodes(
        policy_graph,
        training_policy_ids=[
            "Policy:policy-similar-a",
            "Policy:policy-different-c",
        ],
        config={"dimensions": 2, "walk_length": 5, "walks_per_node": 2, "seed": 3},
    )

    assert policy_ids == [
        "Policy:policy-different-c",
        "Policy:policy-similar-a",
        "Policy:policy-similar-b",
    ]
    assert all("Policy:policy-similar-b" not in walk for walk in observed_walks)
    assert all("Action:lambda:invokefunction" not in walk for walk in observed_walks)
    np.testing.assert_array_equal(vectors[2], [1.0, 3.0])


def test_python_backend_rejects_inference_policy_without_trained_context(policy_graph):
    with pytest.raises(ValueError, match="No trained context embedding.*policy-different-c"):
        embed_policy_nodes(
            policy_graph,
            training_policy_ids=["Policy:policy-similar-a"],
            config={"dimensions": 4, "walk_length": 5, "walks_per_node": 2},
        )


def test_python_backend_validates_training_policy_ids(policy_graph):
    with pytest.raises(ValueError, match="Unknown training policy node IDs"):
        embed_policy_nodes(policy_graph, training_policy_ids=["Policy:unknown"])


class FakeResult:
    def __init__(self, *, row=None, records=None):
        self.row = row
        self.records = records or []

    def single(self):
        return self.row

    def consume(self):
        return None

    def __iter__(self):
        return iter(self.records)


class FakeSession:
    def __init__(self, *, records=None, fail_on_stream=False):
        self.records = records or []
        self.fail_on_stream = fail_on_stream
        self.queries = []
        self.node_count = 0
        self.relationship_count = 0

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def run(self, query, **parameters):
        self.queries.append((query, parameters))
        if "UNWIND $nodes" in query:
            self.node_count = len(parameters["nodes"])
        if "UNWIND $edges" in query:
            self.relationship_count = len(parameters["edges"])
        if "gds.graph.project" in query:
            return FakeResult(
                row={
                    "nodeCount": self.node_count,
                    "relationshipCount": self.relationship_count,
                }
            )
        if "gds.node2vec.stream" in query:
            if self.fail_on_stream:
                raise RuntimeError("Node2Vec procedure failed")
            return FakeResult(records=self.records)
        return FakeResult()


class FakeDriver:
    def __init__(self, session):
        self.fake_session = session
        self.closed = False

    def session(self):
        return self.fake_session

    def close(self):
        self.closed = True


def test_gds_backend_returns_embeddings_in_policy_id_order(policy_graph, monkeypatch):
    session = FakeSession(
        records=[
            {
                "node_id": "Policy:policy-different-c",
                "kind": "Policy",
                "embedding": [3.0, 4.0],
            },
            {
                "node_id": "Policy:policy-similar-a",
                "kind": "Policy",
                "embedding": [1.0, 2.0],
            },
            {
                "node_id": "Action:s3:getobject",
                "kind": "Action",
                "embedding": [1.0, 1.0],
            },
            {
                "node_id": "Action:iam:createuser",
                "kind": "Action",
                "embedding": [2.0, 2.0],
            },
            {
                "node_id": "Entity:entity-01",
                "kind": "Entity",
                "embedding": [3.0, 3.0],
            },
        ]
    )
    driver = FakeDriver(session)

    class FakeGraphDatabase:
        @staticmethod
        def driver(uri, auth):
            assert uri == "bolt://example"
            assert auth == ("neo4j", "password")
            return driver

    monkeypatch.setattr("neo4j.GraphDatabase", FakeGraphDatabase)

    vectors, policy_ids = embed.embed_policy_nodes_with_gds(
        policy_graph,
        training_policy_ids=[
            "Policy:policy-similar-a",
            "Policy:policy-different-c",
        ],
        config={
            "dimensions": 2,
            "walk_length": 5,
            "walks_per_node": 2,
            "window_size": 3,
            "seed": 19,
        },
        uri="bolt://example",
        user="neo4j",
        password="password",
    )

    assert policy_ids == [
        "Policy:policy-different-c",
        "Policy:policy-similar-a",
        "Policy:policy-similar-b",
    ]
    np.testing.assert_array_equal(vectors, [[3.0, 4.0], [1.0, 2.0], [1.0, 1.0]])
    projected_nodes = next(
        parameters["nodes"] for query, parameters in session.queries if "UNWIND $nodes" in query
    )
    assert "Policy:policy-similar-b" not in {node["node_id"] for node in projected_nodes}
    stream_query = next(query for query, _ in session.queries if "gds.node2vec.stream" in query)
    assert "gds.node2vec.stream" in stream_query
    assert driver.closed


def test_gds_backend_rejects_inference_policy_without_trained_context(policy_graph, monkeypatch):
    session = FakeSession(
        records=[
            {
                "node_id": "Policy:policy-similar-a",
                "kind": "Policy",
                "embedding": [1.0, 2.0],
            },
            {
                "node_id": "Action:s3:getobject",
                "kind": "Action",
                "embedding": [3.0, 4.0],
            },
            {
                "node_id": "Entity:entity-01",
                "kind": "Entity",
                "embedding": [5.0, 6.0],
            },
        ]
    )
    driver = FakeDriver(session)

    class FakeGraphDatabase:
        @staticmethod
        def driver(_uri, auth):
            assert auth == ("neo4j", "password")
            return driver

    monkeypatch.setattr("neo4j.GraphDatabase", FakeGraphDatabase)

    with pytest.raises(ValueError, match="No trained context embedding.*policy-different-c"):
        embed.embed_policy_nodes_with_gds(
            policy_graph,
            training_policy_ids=["Policy:policy-similar-a"],
            config={"dimensions": 2},
            uri="bolt://example",
            user="neo4j",
            password="password",
        )

    assert driver.closed


def test_gds_backend_does_not_fall_back_after_procedure_failure(policy_graph, monkeypatch):
    session = FakeSession(fail_on_stream=True)
    driver = FakeDriver(session)

    class FakeGraphDatabase:
        @staticmethod
        def driver(_uri, auth):
            assert auth == ("neo4j", "password")
            return driver

    monkeypatch.setattr("neo4j.GraphDatabase", FakeGraphDatabase)
    monkeypatch.setattr(
        "misdet.embed.gds_node2vec.embed_policy_nodes",
        lambda *_args, **_kwargs: pytest.fail("GDS errors must not use the fallback"),
    )

    with pytest.raises(RuntimeError, match="Node2Vec procedure failed"):
        embed.embed_policy_nodes_with_gds(
            policy_graph,
            training_policy_ids=["Policy:policy-similar-a"],
            uri="bolt://example",
            user="neo4j",
            password="password",
        )

    assert driver.closed


def test_gds_backend_fallback_preserves_training_policy_ids(policy_graph, monkeypatch):
    expected_ids = ["Policy:policy-similar-a"]
    expected_result = (np.array([[1.0, 2.0]]), expected_ids)

    def fake_python_backend(graph, *, training_policy_ids, config, seed):
        assert graph is policy_graph
        assert training_policy_ids == expected_ids
        assert config is None
        assert seed is None
        return expected_result

    monkeypatch.setattr("misdet.embed.gds_node2vec.embed_policy_nodes", fake_python_backend)

    result = embed.embed_policy_nodes_with_gds(policy_graph, training_policy_ids=expected_ids)

    assert result is expected_result
