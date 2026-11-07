"""Deterministic aggregation of repeated experiment results."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from misdet.eval.bootstrap import bootstrap_confidence_interval


def aggregate_seed_metrics(
    rows: Sequence[Mapping[str, Any]], metrics: Sequence[str]
) -> dict[str, Any]:
    """Summarize scalar metrics across seeds and sum raw confusion counts."""
    if not rows:
        raise ValueError("rows must be non-empty")
    result: dict[str, Any] = {"seed_count": len(rows)}
    for metric in metrics:
        values = [row[metric] for row in rows if row.get(metric) is not None]
        if not values:
            result[metric] = None
            continue
        numeric = np.asarray(values, dtype=float)
        result[metric] = {
            "mean": float(np.mean(numeric)),
            "sd": float(np.std(numeric, ddof=1)) if len(numeric) > 1 else 0.0,
            "count": len(values),
        }
    confusion: dict[str, int] = {}
    for row in rows:
        raw = row.get("confusion", {})
        if not isinstance(raw, Mapping):
            raise ValueError("confusion must be a mapping")
        for name in ("tp", "fp", "fn", "tn"):
            value = raw.get(name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"confusion.{name} must be a non-negative integer")
            confusion[name] = confusion.get(name, 0) + value
    result["confusion"] = confusion
    return result


def grouped_recall(
    prediction_rows: Sequence[Mapping[str, Any]],
    *,
    group_field: str,
    groups: Sequence[str] | None = None,
    bootstrap_replicates: int = 2000,
    seed: int = 0,
) -> list[dict[str, Any]]:
    """Return recall and seeded policy bootstrap intervals for each group."""
    if not prediction_rows:
        raise ValueError("prediction_rows must be non-empty")
    observed = {
        row.get(group_field)
        for row in prediction_rows
        if isinstance(row.get(group_field), str) and row.get(group_field)
    }
    requested = list(groups) if groups is not None else sorted(observed)
    if len(set(requested)) != len(requested):
        raise ValueError("groups must not contain duplicates")
    result: list[dict[str, Any]] = []
    for group in requested:
        rows = [row for row in prediction_rows if row.get(group_field) == group]
        labels = np.asarray([row["label"] for row in rows], dtype=int)
        scores = np.asarray([row["score"] for row in rows], dtype=float)
        predictions = np.asarray([row["pred"] for row in rows], dtype=int)
        positive_count = int(np.sum(labels == 1))
        recall = (
            float(np.sum((labels == 1) & (predictions == 1)) / positive_count)
            if positive_count
            else None
        )
        interval = None
        if positive_count and bootstrap_replicates > 0:
            interval = bootstrap_confidence_interval(
                labels,
                scores,
                predictions,
                lambda y, _s, p: float(np.sum((y == 1) & (p == 1)) / np.sum(y == 1)),
                replicates=bootstrap_replicates,
                seed=seed,
            )
        result.append(
            {
                "group": group,
                "count": len(rows),
                "positive_count": positive_count,
                "recall": recall,
                "bootstrap_ci": list(interval) if interval is not None else None,
            }
        )
    return result
