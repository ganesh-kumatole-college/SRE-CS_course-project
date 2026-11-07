"""Persistence helpers for reproducible experiment run artifacts."""

from __future__ import annotations

import csv
import json
import platform
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

PREDICTION_FIELDS = ("policy_id", "score", "pred", "label", "misconfig_type")
OPTIONAL_PREDICTION_FIELDS = ("operator_id", "difficulty")
REQUIRED_ARTIFACTS = ("config.yaml", "metrics.json", "preds.csv", "env.txt", "git_sha.txt")


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _validate_predictions(
    predictions: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in predictions:
        if not isinstance(row, Mapping):
            raise ValueError("predictions must contain mappings")
        missing = [field for field in PREDICTION_FIELDS if field not in row]
        if missing:
            raise ValueError(f"prediction row is missing fields: {missing}")
        policy_id = row["policy_id"]
        if not isinstance(policy_id, str) or not policy_id:
            raise ValueError("prediction policy_id must be a non-empty string")
        if policy_id in seen:
            raise ValueError(f"duplicate prediction policy_id: {policy_id!r}")
        seen.add(policy_id)
        rows.append(
            {
                field: row[field]
                for field in (*PREDICTION_FIELDS, *OPTIONAL_PREDICTION_FIELDS)
                if field in row
            }
        )
    return rows


def write_run_artifacts(
    output_dir: str | Path,
    *,
    config: Mapping[str, Any],
    metrics: Mapping[str, Any],
    predictions: Sequence[Mapping[str, Any]],
) -> Path:
    """Write one complete run directory and refuse to overwrite it."""
    output = Path(output_dir)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing run directory: {output}")
    rows = _validate_predictions(predictions)
    output.mkdir(parents=True)
    try:
        (output / "config.yaml").write_text(
            yaml.safe_dump(dict(config), sort_keys=True), encoding="utf-8"
        )
        (output / "metrics.json").write_text(
            json.dumps(dict(metrics), indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        with (output / "preds.csv").open("w", newline="", encoding="utf-8") as handle:
            optional_fields = [
                field
                for field in OPTIONAL_PREDICTION_FIELDS
                if any(field in row for row in rows)
            ]
            writer = csv.DictWriter(
                handle, fieldnames=(*PREDICTION_FIELDS, *optional_fields), extrasaction="ignore"
            )
            writer.writeheader()
            writer.writerows(rows)
        (output / "env.txt").write_text(
            f"platform={platform.platform()}\npython={sys.version.split()[0]}\n",
            encoding="utf-8",
        )
        (output / "git_sha.txt").write_text(_git_sha() + "\n", encoding="utf-8")
    except Exception:
        for path in output.iterdir():
            path.unlink()
        output.rmdir()
        raise
    return output
