"""Train-only anomaly threshold calibration."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np

from .models import fit_detector


def calibrate_threshold(scores: Sequence[float], *, percentile: float = 95.0) -> float:
    """Return a high-score threshold from normal validation scores."""
    values = np.asarray(scores, dtype=float)
    if values.ndim != 1 or values.size == 0 or not np.isfinite(values).all():
        raise ValueError("validation scores must be a non-empty finite vector")
    if not 0 <= percentile <= 100:
        raise ValueError("percentile must be between 0 and 100")
    return float(np.percentile(values, percentile))


def predict_with_threshold(scores: Sequence[float], threshold: float) -> np.ndarray:
    """Convert anomaly scores into misconfiguration-positive predictions."""
    values = np.asarray(scores, dtype=float)
    if values.ndim != 1 or not np.isfinite(values).all():
        raise ValueError("scores must be a finite vector")
    if not np.isfinite(threshold):
        raise ValueError("threshold must be finite")
    return (values >= threshold).astype(int)


def cross_validated_normal_scores(
    train_ids: Sequence[str],
    train_features: np.ndarray,
    validation_folds: Sequence[Sequence[str]],
    *,
    detector_name: str,
    detector_params: Mapping[str, object] | None = None,
    scale: bool = True,
    seed: int = 42,
) -> np.ndarray:
    """Score each normal validation fold using a model that excluded that fold."""
    ids = list(train_ids)
    if len(ids) != len(set(ids)) or not ids:
        raise ValueError("train_ids must be unique and non-empty")
    values = np.asarray(train_features, dtype=float)
    if values.ndim != 2 or values.shape[0] != len(ids):
        raise ValueError("train_features rows must align with train_ids")
    index_by_id = {policy_id: index for index, policy_id in enumerate(ids)}
    observed: set[str] = set()
    output: list[np.ndarray] = []
    for fold in validation_folds:
        fold_ids = list(fold)
        if not fold_ids or observed.intersection(fold_ids):
            raise ValueError("validation folds must be non-empty and disjoint")
        if any(policy_id not in index_by_id for policy_id in fold_ids):
            raise ValueError("validation fold contains an unknown training policy")
        observed.update(fold_ids)
        held_out = np.asarray([index_by_id[policy_id] for policy_id in fold_ids])
        fitting = np.asarray(
            [index for index, policy_id in enumerate(ids) if policy_id not in set(fold_ids)]
        )
        model = fit_detector(
            detector_name,
            values[fitting],
            params=detector_params,
            scale=scale,
            seed=seed,
        )
        output.append(model.score(values[held_out]))
    if observed != set(ids):
        raise ValueError("validation folds must cover every training policy exactly once")
    return np.concatenate(output)
