"""Seeded bootstrap confidence intervals for evaluation metrics."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import numpy as np

MetricFunction = Callable[[np.ndarray, np.ndarray, np.ndarray], float | None]


def bootstrap_confidence_interval(
    labels: Sequence[int],
    scores: Sequence[float],
    predictions: Sequence[int],
    metric: MetricFunction,
    *,
    replicates: int = 2000,
    alpha: float = 0.05,
    seed: int = 0,
) -> tuple[float, float] | None:
    """Return a percentile interval, ignoring invalid one-class resamples."""
    y_true = np.asarray(labels, dtype=int)
    anomaly_scores = np.asarray(scores, dtype=float)
    y_pred = np.asarray(predictions, dtype=int)
    if not (y_true.ndim == anomaly_scores.ndim == y_pred.ndim == 1):
        raise ValueError("bootstrap inputs must be one-dimensional")
    if not (len(y_true) == len(anomaly_scores) == len(y_pred)) or not len(y_true):
        raise ValueError("bootstrap inputs must have the same non-zero length")
    if not isinstance(replicates, int) or isinstance(replicates, bool) or replicates <= 0:
        raise ValueError("replicates must be a positive integer")
    if not 0 < alpha < 1:
        raise ValueError("alpha must be between 0 and 1")
    rng = np.random.default_rng(seed)
    values: list[float] = []
    indices = np.arange(len(y_true))
    for _ in range(replicates):
        sample = rng.choice(indices, size=len(indices), replace=True)
        value = metric(y_true[sample], anomaly_scores[sample], y_pred[sample])
        if value is not None and np.isfinite(value):
            values.append(float(value))
    if not values:
        return None
    return (
        float(np.percentile(values, 100 * alpha / 2)),
        float(np.percentile(values, 100 * (1 - alpha / 2))),
    )
