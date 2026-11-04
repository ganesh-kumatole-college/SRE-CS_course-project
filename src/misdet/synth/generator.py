"""Deterministic synthetic benchmark generation for IAM policy misconfiguration experiments."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from random import Random
from typing import Any

from .injector import inject_misconfigurations
from .labels import LABEL_COLUMNS, build_label_rows
from .org_profiles import build_org_profiles


def _canonical_policy(org: str, index: int, template_name: str, action_seed: int) -> dict[str, Any]:
    action_values = ["s3:getobject", "ec2:describeinstances", "iam:listroles", "logs:getlogevents"]
    resource_values = [
        f"arn:aws:s3:::${org}-data/*",
        "arn:aws:ec2:*:*:instance/*",
        f"arn:aws:iam::*:role/{org}-*",
        f"arn:aws:logs:*:*:log-group:{org}/*",
    ]
    action = action_values[(index + action_seed) % len(action_values)]
    resource = resource_values[(index + action_seed + 1) % len(resource_values)]
    return {
        "policy_id": f"{org}-policy-{index:02d}",
        "org": org,
        "source": "synthetic_custom",
        "document": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": f"{org}-{template_name}-{index:02d}",
                    "Effect": "Allow",
                    "Action": [action],
                    "Resource": [resource],
                }
            ],
        },
    }


def generate_entities(
    org_profiles: dict[str, dict[str, Any]], seed: int = 7
) -> list[dict[str, Any]]:
    """Generate deterministic synthetic entities and group membership for each org."""
    rng = Random(seed)
    entities: list[dict[str, Any]] = []
    for org_name, profile in sorted(org_profiles.items()):
        roles = profile["roles"]
        for role_index, role in enumerate(roles):
            entities.append(
                {
                    "entity_id": f"{org_name}-entity-{role_index:02d}",
                    "org": org_name,
                    "entity_type": "group",
                    "name": role,
                    "seed_value": rng.randint(0, 100000),
                }
            )
    return entities


def generate_attachments(
    policies: list[dict[str, Any]],
    entities: list[dict[str, Any]],
    seed: int = 7,
) -> list[dict[str, Any]]:
    """Attach policies to entities in a deterministic round-robin sequence."""
    if not policies:
        return []
    entity_rows_by_org: dict[str, list[dict[str, Any]]] = {}
    for entity in entities:
        entity_rows_by_org.setdefault(entity["org"], []).append(entity)

    attachments: list[dict[str, Any]] = []
    for index, policy in enumerate(policies):
        org = policy["org"]
        candidates = entity_rows_by_org.get(org, [])
        if not candidates:
            continue
        entity = candidates[(index + seed) % len(candidates)]
        attachments.append(
            {
                "policy_id": policy["policy_id"],
                "org": org,
                "entity_id": entity["entity_id"],
                "attachment_type": "group",
            }
        )
    return attachments


def generate_benchmark(
    seed: int = 7,
    org_names: list[str] | None = None,
    out_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Generate the synthetic benchmark dataset and optionally write it to disk."""
    org_profiles = build_org_profiles(seed=seed)
    if org_names:
        org_profiles = {name: org_profiles[name] for name in org_names if name in org_profiles}

    policies: list[dict[str, Any]] = []
    for org_name in sorted(org_profiles):
        for index in range(6):
            if org_name == "alpha":
                template_name = "prod_read"
            elif org_name == "beta":
                template_name = "ops_read"
            else:
                template_name = "data_read"
            policies.append(_canonical_policy(org_name, index, template_name, seed + index))

    policies = inject_misconfigurations(policies, org_profiles=org_profiles, seed=seed)
    entities = generate_entities(org_profiles, seed=seed)
    attachments = generate_attachments(policies, entities, seed=seed)
    labels = build_label_rows(policies, entities=entities, attachments=attachments)

    benchmark = {
        "seed": seed,
        "org_profiles": org_profiles,
        "policies": policies,
        "entities": entities,
        "attachments": attachments,
        "labels": labels,
    }

    if out_dir is not None:
        write_benchmark(Path(out_dir), benchmark)
    return benchmark


def write_benchmark(out_dir: str | Path, benchmark: dict[str, Any]) -> dict[str, Path]:
    """Write benchmark artifacts to disk as JSONL and CSV files."""
    output_dir = Path(out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    policy_path = output_dir / "policies.jsonl"
    entity_path = output_dir / "entities.jsonl"
    attachment_path = output_dir / "attachments.jsonl"
    labels_path = output_dir / "labels.csv"

    with policy_path.open("w", encoding="utf-8") as handle:
        for record in benchmark["policies"]:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
    with entity_path.open("w", encoding="utf-8") as handle:
        for record in benchmark["entities"]:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
    with attachment_path.open("w", encoding="utf-8") as handle:
        for record in benchmark["attachments"]:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
    with labels_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=LABEL_COLUMNS)
        writer.writeheader()
        for row in benchmark["labels"]:
            writer.writerow({column: row.get(column, "") for column in LABEL_COLUMNS})

    return {
        "policies": policy_path,
        "entities": entity_path,
        "attachments": attachment_path,
        "labels": labels_path,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic IAM benchmark data.")
    parser.add_argument(
        "--seed",
        type=int,
        default=7,
        help="Random seed for deterministic generation",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data/benchmark"),
        help="Directory where benchmark files are written",
    )
    args = parser.parse_args()
    generate_benchmark(seed=args.seed, out_dir=args.out_dir)


if __name__ == "__main__":
    main()
