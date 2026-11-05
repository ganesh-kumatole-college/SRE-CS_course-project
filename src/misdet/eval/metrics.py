"""Metrics for binary anomaly evaluation with misconfiguration as positive."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
from sklearn.metrics import average_precision_score, precision_recall_fscore_support, roc_auc_score


def evaluate_predictions(
    labels: Sequence[int],
    scores: Sequence[float],
    predictions: Sequence[int],
    *,
    alert_budgets: Sequence[int] = (10, 20, 50),
) -> dict[str, Any]:
    """Compute minority-class metrics and raw confusion counts."""
    y_true = np.asarray(labels, dtype=int)
    anomaly_scores = np.asarray(scores, dtype=float)
    y_pred = np.asarray(predictions, dtype=int)
    if y_true.ndim != 1 or anomaly_scores.ndim != 1 or y_pred.ndim != 1:
        raise ValueError("labels, scores, and predictions must be one-dimensional")
    if not (len(y_true) == len(anomaly_scores) == len(y_pred)) or not len(y_true):
        raise ValueError("labels, scores, and predictions must have the same non-zero length")
    if not np.isfinite(anomaly_scores).all() or not np.isin(y_true, [0, 1]).all():
        raise ValueError("labels must be binary and scores must be finite")
    if not np.isin(y_pred, [0, 1]).all():
        raise ValueError("predictions must be binary")

    tp = int(np.sum((y_true == 1) & (y_pred == 1)))
    fp = int(np.sum((y_true == 0) & (y_pred == 1)))
    fn = int(np.sum((y_true == 1) & (y_pred == 0)))
    tn = int(np.sum((y_true == 0) & (y_pred == 0)))
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average="binary", pos_label=1, zero_division=0
    )
    result: dict[str, Any] = {
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "pr_auc": _safe_auc(average_precision_score, y_true, anomaly_scores),
        "roc_auc": _safe_auc(roc_auc_score, y_true, anomaly_scores),
        "false_positive_rate": float(fp / (fp + tn)) if fp + tn else None,
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "alert_budgets": {},
    }
    order = np.argsort(-anomaly_scores, kind="stable")
    for budget in alert_budgets:
        if not isinstance(budget, int) or isinstance(budget, bool) or budget <= 0:
            raise ValueError("alert budgets must be positive integers")
        if budget > len(y_true):
            result["alert_budgets"][str(budget)] = None
            continue
        selected = y_true[order[:budget]]
        result["alert_budgets"][str(budget)] = {
            "precision": float(np.mean(selected)),
            "recall": float(np.sum(selected) / max(1, np.sum(y_true))),
        }
    return result


def _safe_auc(metric: Any, labels: np.ndarray, scores: np.ndarray) -> float | None:
    if len(np.unique(labels)) < 2:
        return None
    try:
        return float(metric(labels, scores))
    except ValueError:
        return None
