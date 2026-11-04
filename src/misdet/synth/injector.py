"""Synthetic policy injection helpers for the benchmark generator."""

from __future__ import annotations

from typing import Any


def apply_injection_operator(policy: dict[str, Any], operator_id: str, org: str) -> dict[str, Any]:
    """Apply a deterministic operator to a synthetic policy record."""
    if not isinstance(policy, dict):
        raise ValueError("policy must be a dictionary")
    if not operator_id:
        raise ValueError("operator_id must be a non-empty string")

    document = dict(policy.get("document", {}))
    statements = list(document.get("Statement", []))
    if not statements:
        raise ValueError(f"policy {policy.get('policy_id', '<unknown>')} has no statements")

    statement = dict(statements[0])
    if operator_id == "P1":
        statement["Action"] = ["s3:getobject", "s3:listbucket"]
        statement["Resource"] = [f"arn:aws:s3:::{org}-prod/*", "arn:aws:s3:::*"]
        statement["Effect"] = "Allow"
    elif operator_id == "P2":
        statement["Action"] = ["iam:*", "ec2:runinstances"]
        statement["Resource"] = [f"arn:aws:iam::*:role/{org}-*", "arn:aws:ec2:*:*:instance/*"]
        statement["Effect"] = "Allow"
    elif operator_id == "A3":
        statement["Action"] = ["s3:putobject", "iam:createuser"]
        statement["Resource"] = [f"arn:aws:s3:::shared-{org}-data/*", "arn:aws:iam::*:user/*"]
        statement["Effect"] = "Allow"
    else:
        raise ValueError(f"unsupported injection operator: {operator_id}")

    statement.setdefault("Sid", f"{org}-{operator_id}-synthetic")
    statement["Condition"] = {"StringLike": {"aws:ResourceTag/Environment": "*"}}
    document["Statement"] = [statement]
    result = dict(policy)
    result["document"] = document
    result["org"] = org
    return result


def inject_misconfigurations(
    policies: list[dict[str, Any]],
    org_profiles: dict[str, dict[str, Any]] | None = None,
    seed: int = 7,
) -> list[dict[str, Any]]:
    """Return the policy list with selective injection operators applied."""
    if not isinstance(policies, list):
        raise ValueError("policies must be a list")
    if not policies:
        return []

    result: list[dict[str, Any]] = []
    for index, policy in enumerate(policies):
        org = policy.get("org")
        if org is None:
            raise ValueError(f"policy at index {index} is missing an org")

        operator_id = "P1"
        if index % 3 == 1:
            operator_id = "P2"
        elif index % 3 == 2:
            operator_id = "A3"

        if org_profiles and org in org_profiles:
            if index % 2:
                operator_id = next(iter(org_profiles[org]["positive_operators"]))
        result.append(apply_injection_operator(policy, operator_id, org))
    return result


def generate_injections(
    policies: list[dict[str, Any]],
    org_profiles: dict[str, dict[str, Any]] | None = None,
    seed: int = 7,
) -> list[dict[str, Any]]:
    """Backward-compatible alias for the injection helper."""
    return inject_misconfigurations(policies, org_profiles=org_profiles, seed=seed)
