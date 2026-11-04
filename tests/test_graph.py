import pytest

from misdet.graph import build_policy_graph


@pytest.fixture
def sample_policy_rows():
    return [
        {
            "policy_id": "alpha-policy-01",
            "org": "alpha",
            "source": "synthetic_custom",
            "document": {
                "Statement": [
                    {
                        "Sid": "allow-read",
                        "Effect": "Allow",
                        "Action": ["ec2:DescribeInstances", "s3:GetObject"],
                        "Resource": ["arn:aws:ec2:*:*:instance/*", "arn:aws:s3:::data-bucket/*"],
                    },
                    {
                        "Sid": "deny-iam",
                        "Effect": "Deny",
                        "NotAction": ["iam:*"],
                        "NotResource": ["arn:aws:iam::*:user/*"],
                    },
                ]
            },
        }
    ]


@pytest.fixture
def sample_entities():
    return [{"entity_id": "alpha-entity-00", "org": "alpha", "entity_type": "group"}]


@pytest.fixture
def sample_attachments():
    return [
        {
            "entity_id": "alpha-entity-00",
            "policy_id": "alpha-policy-01",
            "attachment_type": "group",
        }
    ]


def test_build_policy_graph_creates_expected_edges(
    sample_policy_rows,
    sample_entities,
    sample_attachments,
):
    graph = build_policy_graph(
        sample_policy_rows,
        entities=sample_entities,
        attachments=sample_attachments,
    )

    assert graph.to_serializable()["nodes"]
    labels = {edge.label for edge in graph.edges}
    assert {"ATTACHED_TO", "ALLOWS", "DENIES", "WORKS_ON"}.issubset(labels)

    policy_nodes = [node for node in graph.nodes if node.kind == "Policy"]
    action_nodes = [node for node in graph.nodes if node.kind == "Action"]
    resource_nodes = [node for node in graph.nodes if node.kind == "Resource"]

    assert len(policy_nodes) == 1
    assert len(action_nodes) == 3
    assert len(resource_nodes) == 3

    action_values = {node.node_id.lower() for node in action_nodes}
    assert "action:ec2:describeinstances" in action_values
    assert "action:iam:*" in action_values

    networkx_graph = graph.to_networkx()
    assert networkx_graph.number_of_nodes() == len(graph.nodes)
    assert networkx_graph.number_of_edges() == len(graph.edges)


def test_build_policy_graph_rejects_malformed_policy():
    with pytest.raises(ValueError):
        build_policy_graph(
            [
                {
                    "policy_id": "broken-policy",
                    "org": "alpha",
                    "source": "synthetic_custom",
                    "document": {"Statement": [{"Effect": "Allow", "Action": []}]},
                }
            ]
        )


def test_build_policy_graph_is_repeatable(
    sample_policy_rows,
    sample_entities,
    sample_attachments,
):
    first = build_policy_graph(
        sample_policy_rows,
        entities=sample_entities,
        attachments=sample_attachments,
    )
    second = build_policy_graph(
        sample_policy_rows,
        entities=sample_entities,
        attachments=sample_attachments,
    )

    assert first.to_serializable() == second.to_serializable()
