"""Deterministic rule and feature baselines for normalized IAM policies."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

BASELINE_NAMES = (
    "random",
    "prevalence",
    "wildcard",
    "permissiveness",
    "offline_custodian_equivalent",
    "handcrafted_feature",
)

HANDCRAFTED_FEATURE_NAMES = (
    "statement_count",
    "allow_statement_count",
    "deny_statement_count",
    "action_pattern_count",
    "resource_pattern_count",
    "wildcard_action_count",
    "wildcard_resource_count",
    "not_action_statement_count",
    "not_resource_statement_count",
    "condition_statement_count",
    "principal_statement_count",
)


@dataclass(frozen=True)
class BaselineOutput:
    """Anomaly scores and misconfiguration-positive predictions."""

    name: str
    scores: np.ndarray
    predictions: np.ndarray


def _validate_policy_records(policies: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(policies, (str, bytes)) or not isinstance(policies, Sequence):
        raise TypeError("policies must be a sequence of policy mappings")
    records: list[dict[str, Any]] = []
    ids: set[str] = set()
    for policy in policies:
        if not isinstance(policy, Mapping):
            raise ValueError("each policy must be a mapping")
        policy_id = policy.get("policy_id")
        if not isinstance(policy_id, str) or not policy_id or policy_id in ids:
            raise ValueError("policies must have unique non-empty policy_id values")
        document = policy.get("document")
        if not isinstance(document, Mapping):
            raise ValueError(f"policy {policy_id!r} must contain a document mapping")
        statements = document.get("Statement")
        if isinstance(statements, Mapping):
            statements = [statements]
        if not isinstance(statements, list) or not statements:
            raise ValueError(f"policy {policy_id!r} must contain non-empty Statement data")
        normalized_statements: list[dict[str, Any]] = []
        for index, statement in enumerate(statements):
            if not isinstance(statement, Mapping):
                raise ValueError(f"policy {policy_id!r} statement {index} must be a mapping")
            effect = statement.get("Effect")
            if effect not in {"Allow", "Deny"}:
                raise ValueError(f"policy {policy_id!r} statement {index} has invalid Effect")
            normalized: dict[str, Any] = dict(statement)
            for positive, negative in (("Action", "NotAction"), ("Resource", "NotResource")):
                present = [field for field in (positive, negative) if field in statement]
                if len(present) != 1:
                    raise ValueError(
                        f"policy {policy_id!r} statement {index} must contain exactly one of "
                        f"{positive} or {negative}"
                    )
                values = statement[present[0]]
                if not isinstance(values, list) or not values or any(
                    not isinstance(value, str) or not value for value in values
                ):
                    raise ValueError(
                        f"policy {policy_id!r} statement {index} {present[0]} must be a non-empty "
                        "list of strings"
                    )
                normalized[present[0]] = list(values)
            normalized_statements.append(normalized)
        record = dict(policy)
        record["document"] = {**document, "Statement": normalized_statements}
        records.append(record)
        ids.add(policy_id)
    if not records:
        raise ValueError("policies must not be empty")
    return records


def validate_policies(policies: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Validate and normalize the in-memory policy record view."""
    return _validate_policy_records(policies)


def _statements(policy: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return policy["document"]["Statement"]


def _selector_values(statement: Mapping[str, Any], positive: str, negative: str) -> list[str]:
    return list(statement.get(positive, statement.get(negative, [])))


def _wildcard_count(values: Sequence[str]) -> int:
    return sum("*" in value for value in values)


def _policy_feature_row(policy: Mapping[str, Any]) -> list[float]:
    statements = _statements(policy)
    allow = [statement for statement in statements if statement["Effect"] == "Allow"]
    deny = [statement for statement in statements if statement["Effect"] == "Deny"]
    action_values = [
        value
        for statement in statements
        for value in _selector_values(statement, "Action", "NotAction")
    ]
    resource_values = [
        value
        for statement in statements
        for value in _selector_values(statement, "Resource", "NotResource")
    ]
    return [
        float(len(statements)),
        float(len(allow)),
        float(len(deny)),
        float(len(action_values)),
        float(len(resource_values)),
        float(_wildcard_count(action_values)),
        float(_wildcard_count(resource_values)),
        float(sum("NotAction" in statement for statement in statements)),
        float(sum("NotResource" in statement for statement in statements)),
        float(sum("Condition" in statement for statement in statements)),
        float(sum("Principal" in statement for statement in statements)),
    ]


def handcrafted_features(policies: Sequence[Mapping[str, Any]]) -> np.ndarray:
    """Return the stable, document-only feature matrix for policy records."""
    records = _validate_policy_records(policies)
    values = np.asarray([_policy_feature_row(policy) for policy in records], dtype=float)
    if values.shape != (len(records), len(HANDCRAFTED_FEATURE_NAMES)):
        raise ValueError("hand-crafted feature matrix has an unexpected shape")
    return values


def _rule_score(policy: Mapping[str, Any], name: str) -> float:
    score = 0.0
    for statement in _statements(policy):
        if statement["Effect"] != "Allow":
            continue
        actions = _selector_values(statement, "Action", "NotAction")
        resources = _selector_values(statement, "Resource", "NotResource")
        action_wildcards = _wildcard_count(actions)
        resource_wildcards = _wildcard_count(resources)
        if name == "wildcard":
            score += float(action_wildcards + resource_wildcards)
        elif name == "permissiveness":
            score += float(
                len(actions) + len(resources) + 2 * action_wildcards + resource_wildcards
            )
        elif name == "offline_custodian_equivalent":
            broad_action = any(value == "*" or value.endswith(":*") for value in actions)
            broad_resource = any(value == "*" for value in resources)
            score = float(score > 0 or broad_action or broad_resource)
        else:
            raise ValueError(f"unsupported rule baseline {name!r}")
    return score


def rule_scores(
    policies: Sequence[Mapping[str, Any]], *, name: str
) -> np.ndarray:
    """Return deterministic scores for one supported rule baseline."""
    if name not in {"wildcard", "permissiveness", "offline_custodian_equivalent"}:
        raise ValueError(f"unsupported rule baseline {name!r}")
    records = _validate_policy_records(policies)
    return np.asarray([_rule_score(policy, name) for policy in records], dtype=float)


def random_scores(count: int, *, seed: int) -> np.ndarray:
    """Return a seeded random ranking for ``count`` policies."""
    if not isinstance(count, int) or isinstance(count, bool) or count <= 0:
        raise ValueError("count must be a positive integer")
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise TypeError("seed must be an integer")
    return np.random.default_rng(seed).random(count)


def prevalence_output(
    count: int, training_labels: Sequence[int]
) -> BaselineOutput:
    """Return the training-prevalence score and classification reference."""
    if not isinstance(count, int) or isinstance(count, bool) or count <= 0:
        raise ValueError("count must be a positive integer")
    labels = np.asarray(training_labels, dtype=int)
    if labels.ndim != 1 or labels.size == 0 or not np.isin(labels, [0, 1]).all():
        raise ValueError("training_labels must be a non-empty binary vector")
    prevalence = float(np.mean(labels))
    scores = np.full(count, prevalence, dtype=float)
    predictions = np.full(count, int(prevalence >= 0.5), dtype=int)
    return BaselineOutput("prevalence", scores, predictions)


def rule_output(policies: Sequence[Mapping[str, Any]], *, name: str) -> BaselineOutput:
    """Return thresholded predictions for a deterministic rule baseline."""
    scores = rule_scores(policies, name=name)
    return BaselineOutput(name, scores, (scores > 0).astype(int))
