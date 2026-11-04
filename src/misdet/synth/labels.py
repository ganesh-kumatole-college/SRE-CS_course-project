"""Label generation for synthetic benchmark rows."""

from __future__ import annotations

import csv
from collections.abc import Mapping
from pathlib import Path
from typing import Any

LABEL_COLUMNS = [
    "policy_id",
    "org",
    "label",
    "misconfig_type",
    "operator_id",
    "difficulty",
    "hard_negative",
    "attached_entity_id",
    "source",
    "rationale",
]


def build_label_rows(
    policies: list[dict[str, Any]],
    entities: list[dict[str, Any]] | None = None,
    attachments: list[dict[str, Any]] | None = None,
    operator_by_policy_id: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Create label rows for each synthetic policy, including both positives and negatives."""
    if not isinstance(policies, list):
        raise ValueError("policies must be a list")

    attachment_map: dict[str, str] = {}
    if attachments:
        for attachment in attachments:
            policy_id = attachment.get("policy_id")
            entity_id = attachment.get("entity_id")
            if policy_id and entity_id:
                attachment_map[policy_id] = entity_id

    legacy_operator_ids = {0: "P1", 1: "P2", 2: "A3"}
    label_rows: list[dict[str, Any]] = []
    for index, policy in enumerate(policies):
        policy_id = str(policy.get("policy_id", f"policy-{index:02d}"))
        org = str(policy.get("org", "unknown"))
        entity_id = attachment_map.get(policy_id, "")
        operator_id = (
            operator_by_policy_id.get(policy_id)
            if operator_by_policy_id is not None
            else legacy_operator_ids.get(index % 4)
        )

        if operator_id == "P1":
            label = 1
            misconfig_type = "permissive"
            difficulty = "easy" if index % 8 == 0 else "medium"
            hard_negative = 0
            rationale = (
                f"Synthetic {org} policy over-grants {policy_id} in a permissive "
                "operating pattern."
            )
        elif operator_id == "P2":
            label = 1
            misconfig_type = "permissive"
            difficulty = "easy"
            hard_negative = 0
            rationale = f"Synthetic {org} policy grants a wildcard service on all resources."
        elif operator_id == "A3":
            label = 1
            misconfig_type = "misattached"
            difficulty = "medium"
            hard_negative = 0
            rationale = (
                f"Synthetic {org} policy is attached to the wrong entity, creating "
                "a misattached administrator role."
            )
        else:
            if operator_id is not None:
                raise ValueError(f"unsupported operator {operator_id!r} for policy {policy_id!r}")
            label = 0
            misconfig_type = "none"
            operator_id = "none"
            difficulty = "none"
            hard_negative = 0
            rationale = f"Synthetic {org} policy is a benign, hard-negative baseline record."

        label_rows.append(
            {
                "policy_id": policy_id,
                "org": org,
                "label": label,
                "misconfig_type": misconfig_type,
                "operator_id": operator_id,
                "difficulty": difficulty,
                "hard_negative": hard_negative,
                "attached_entity_id": entity_id,
                "source": "synthetic_custom",
                "rationale": rationale,
            }
        )

    return label_rows


def write_labels(path: str | Path, rows: list[dict[str, Any]]) -> Path:
    """Write label rows to a CSV file in canonical order."""
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=LABEL_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in LABEL_COLUMNS})
    return out_path


def generate_label_rows(
    policies: list[dict[str, Any]],
    entities: list[dict[str, Any]] | None = None,
    attachments: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Backward-compatible alias for label-row generation."""
    return build_label_rows(policies, entities=entities, attachments=attachments)
