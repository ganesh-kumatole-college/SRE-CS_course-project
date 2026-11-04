"""Build a canonical IAM policy graph from normalized policy and attachment rows."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

try:
    import networkx as nx
except ImportError:  # pragma: no cover - optional dependency is installed in the project
    nx = None


class GraphError(ValueError):
    """Raised when a graph cannot be built from the supplied data."""


@dataclass(frozen=True)
class GraphNode:
    """A graph node keyed by type and stable identifier."""

    kind: str
    node_id: str
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GraphEdge:
    """A graph edge with a source, target, label, and metadata."""

    source: str
    target: str
    label: str
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class PolicyGraph:
    """A canonical IAM policy graph representation."""

    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)

    def add_node(self, kind: str, node_id: str, **properties: Any) -> str:
        normalized_id = _canonical_node_id(kind, node_id)
        if not any(
            node.kind == kind and node.node_id == normalized_id for node in self.nodes
        ):
            self.nodes.append(
                GraphNode(
                    kind=kind,
                    node_id=normalized_id,
                    properties=dict(properties),
                )
            )
        return normalized_id

    def add_edge(
        self,
        source: str,
        target: str,
        label: str,
        **properties: Any,
    ) -> GraphEdge:
        edge = GraphEdge(source=source, target=target, label=label, properties=dict(properties))
        self.edges.append(edge)
        return edge

    def to_networkx(self):
        """Return a directed NetworkX graph for local inspection and downstream work."""
        if nx is None:  # pragma: no cover - networkx is an explicit project dependency
            raise RuntimeError("networkx is required to export PolicyGraph to a NetworkX graph")

        graph = nx.DiGraph()
        for node in self.nodes:
            graph.add_node(node.node_id, kind=node.kind, **node.properties)
        for edge in self.edges:
            graph.add_edge(edge.source, edge.target, label=edge.label, **edge.properties)
        return graph

    def to_serializable(self) -> dict[str, Any]:
        return {
            "nodes": [
                {"kind": node.kind, "node_id": node.node_id, **node.properties}
                for node in self.nodes
            ],
            "edges": [
                {
                    "source": edge.source,
                    "target": edge.target,
                    "label": edge.label,
                    **edge.properties,
                }
                for edge in self.edges
            ],
        }


def _coerce_string_list(value: Any, *, field_name: str) -> list[str]:
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, list):
        values = value
    else:
        raise GraphError(f"{field_name} must be a string or a non-empty list of strings")

    items: list[str] = []
    for item in values:
        if not isinstance(item, str) or not item.strip():
            raise GraphError(f"{field_name} contains an invalid value: {item!r}")
        items.append(item.lower())
    if not items:
        raise GraphError(f"{field_name} must contain at least one value")
    return items


def _statement_fields(statement: dict[str, Any], field_name: str) -> tuple[list[str], str]:
    candidates = [field for field in (field_name, "Not" + field_name) if field in statement]
    if len(candidates) != 1:
        raise GraphError(
            f"Statement must contain exactly one of {field_name} or Not{field_name}"
        )
    field = candidates[0]
    return _coerce_string_list(statement[field], field_name=field), field


def _canonical_node_id(kind: str, value: str) -> str:
    return f"{kind}:{value.lower()}"


def build_policy_graph(
    policies: Iterable[dict[str, Any]],
    *,
    entities: Iterable[dict[str, Any]] | None = None,
    attachments: Iterable[dict[str, Any]] | None = None,
) -> PolicyGraph:
    """Build the canonical IAM graph from policy, entity, and attachment data."""
    graph = PolicyGraph()
    policy_records = list(policies)
    entity_records = list(entities or [])
    attachment_records = list(attachments or [])

    policy_by_id: dict[str, dict[str, Any]] = {}
    for policy in policy_records:
        if not isinstance(policy, dict):
            raise GraphError("Each policy record must be a JSON object")
        policy_id = policy.get("policy_id")
        if not isinstance(policy_id, str) or not policy_id:
            raise GraphError("Each policy record must include a non-empty policy_id")
        policy_by_id[policy_id] = policy

    for entity in entity_records:
        if not isinstance(entity, dict):
            raise GraphError("Each entity record must be a JSON object")
        entity_id = entity.get("entity_id")
        if not isinstance(entity_id, str) or not entity_id:
            raise GraphError("Each entity record must include a non-empty entity_id")
        graph.add_node(
            "Entity",
            entity_id,
            **{key: value for key, value in entity.items() if key != "entity_id"},
        )

    for attachment in attachment_records:
        if not isinstance(attachment, dict):
            raise GraphError("Each attachment record must be a JSON object")
        entity_id = attachment.get("entity_id")
        policy_id = attachment.get("policy_id")
        if not isinstance(entity_id, str) or not entity_id:
            raise GraphError("Each attachment record must include an entity_id")
        if not isinstance(policy_id, str) or not policy_id:
            raise GraphError("Each attachment record must include a policy_id")
        if policy_id not in policy_by_id:
            raise GraphError(f"Attachment references unknown policy_id: {policy_id!r}")
        entity_node = graph.add_node("Entity", entity_id)
        policy_node = graph.add_node("Policy", policy_id, **policy_by_id[policy_id])
        graph.add_edge(
            entity_node,
            policy_node,
            "ATTACHED_TO",
            org=policy_by_id[policy_id].get("org"),
            entity_type=(
                next(
                    (
                        item.get("entity_type")
                        for item in entity_records
                        if item.get("entity_id") == entity_id
                    ),
                    None,
                )
            ),
        )

    for policy in policy_records:
        policy_id = str(policy["policy_id"])
        document = policy.get("document")
        if not isinstance(document, dict):
            raise GraphError(f"Policy {policy_id!r} must include a document object")
        statements = document.get("Statement")
        if not isinstance(statements, list) or not statements:
            raise GraphError(f"Policy {policy_id!r} must include a non-empty Statement list")

        policy_node = graph.add_node(
            "Policy",
            policy_id,
            **{key: value for key, value in policy.items() if key != "policy_id"},
        )

        for index, statement in enumerate(statements):
            if not isinstance(statement, dict):
                raise GraphError(f"Policy {policy_id!r} statement {index} must be an object")
            effect = statement.get("Effect")
            if effect not in {"Allow", "Deny"}:
                raise GraphError(
                    f"Policy {policy_id!r} statement {index} must have Effect 'Allow' or 'Deny'"
                )

            action_values, action_field = _statement_fields(statement, "Action")
            for action in action_values:
                action_node = graph.add_node(
                    "Action",
                    action,
                    **{"value": action, "negative_match": action_field.startswith("Not")},
                )
                graph.add_edge(
                    policy_node,
                    action_node,
                    "ALLOWS" if effect == "Allow" else "DENIES",
                    statement_index=index,
                    field=action_field,
                    negative_match=action_field.startswith("Not"),
                )

                resource_values, resource_field = _statement_fields(statement, "Resource")
                for resource in resource_values:
                    resource_node = graph.add_node(
                        "Resource",
                        resource,
                        **{"value": resource, "negative_match": resource_field.startswith("Not")},
                    )
                    graph.add_edge(
                        action_node,
                        resource_node,
                        "WORKS_ON",
                        statement_index=index,
                        field=resource_field,
                        negative_match=resource_field.startswith("Not"),
                    )

    return graph
