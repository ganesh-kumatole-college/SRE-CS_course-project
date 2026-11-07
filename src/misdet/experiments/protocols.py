"""Reusable leakage-safe protocols for the Phase 9 experiments."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from misdet.detect.models import DETECTOR_NAMES, fit_detector
from misdet.detect.thresholds import (
    calibrate_threshold,
    cross_validated_normal_scores,
    predict_with_threshold,
)
from misdet.eval.metrics import evaluate_predictions
from misdet.eval.splits import EvaluationSplit, make_evaluation_split

from .artifacts import write_run_artifacts


def _split_indices(
    policy_ids: Sequence[str], split: EvaluationSplit
) -> tuple[np.ndarray, np.ndarray]:
    index_by_id = {policy_id: index for index, policy_id in enumerate(policy_ids)}
    train = np.asarray([index_by_id[policy_id] for policy_id in split.train_normal_ids])
    test = np.asarray([index_by_id[policy_id] for policy_id in split.test_ids])
    return train, test


def run_detector_comparison(
    policy_ids: Sequence[str],
    features: np.ndarray,
    labels: Mapping[str, int],
    output_root: str | Path,
    *,
    detector_params: Mapping[str, Mapping[str, Any]] | None = None,
    detector_grid: Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
    detectors: Sequence[str] = DETECTOR_NAMES,
    scale: bool = True,
    threshold_percentile: float = 95.0,
    validation_folds: int = 5,
    bootstrap_replicates: int = 2000,
    seed: int = 42,
    label_rows: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Path]:
    """Run detectors on one shared split and persist one artifact directory each."""
    ids = list(policy_ids)
    values = np.asarray(features, dtype=float)
    if values.ndim != 2 or values.shape[0] != len(ids):
        raise ValueError("features must be a matrix aligned with policy_ids")
    names = tuple(detectors)
    if not names or len(set(names)) != len(names) or any(
        name not in DETECTOR_NAMES for name in names
    ):
        raise ValueError(f"detectors must be unique names from {DETECTOR_NAMES}")
    split = make_evaluation_split(
        ids,
        labels,
        validation_folds=validation_folds,
        seed=seed,
    )
    train_indices, test_indices = _split_indices(ids, split)
    test_labels = np.asarray([labels[policy_id] for policy_id in split.test_ids], dtype=int)
    params_by_detector = detector_params or {}
    grid_by_detector = detector_grid or {}
    outputs: dict[str, Path] = {}
    for name in names:
        params = dict(params_by_detector.get(name, {}))
        candidates = tuple(grid_by_detector.get(name, ()))
        tuning: dict[str, Any] = {"mode": "none"}
        if candidates:
            validation_ids = split.validation_folds[0]
            validation_set = set(validation_ids)
            fit_ids = tuple(
                policy_id for policy_id in split.train_normal_ids if policy_id not in validation_set
            )
            fit_indices, validation_indices = _split_indices(
                ids,
                EvaluationSplit(
                    train_normal_ids=fit_ids,
                    validation_folds=(),
                    test_ids=validation_ids,
                ),
            )
            params = select_detector_params(
                name,
                values[fit_indices],
                values[validation_indices],
                [0] * len(validation_indices),
                candidates,
                scale=scale,
                seed=seed,
            )
            tuning = {
                "mode": "validation_normal_fold",
                "candidate_count": len(candidates),
                "validation_ids": list(validation_ids),
            }
        model = fit_detector(name, values[train_indices], params=params, scale=scale, seed=seed)
        validation_scores = cross_validated_normal_scores(
            split.train_normal_ids,
            values[train_indices],
            split.validation_folds,
            detector_name=name,
            detector_params=params,
            scale=scale,
            seed=seed,
        )
        threshold = calibrate_threshold(validation_scores, percentile=threshold_percentile)
        scores = model.score(values[test_indices])
        predictions = predict_with_threshold(scores, threshold)
        metrics = evaluate_predictions(test_labels, scores, predictions)
        metrics["run"] = {
            "detector": name,
            "threshold": threshold,
            "seed": seed,
            "test_ids": list(split.test_ids),
        }
        prediction_rows = [
            {
                "policy_id": policy_id,
                "score": float(score),
                "pred": int(prediction),
                "label": int(labels[policy_id]),
                "misconfig_type": "",
                **(
                    {
                        "operator_id": str(label_rows[policy_id].get("operator_id", "")),
                        "difficulty": str(label_rows[policy_id].get("difficulty", "")),
                    }
                    if label_rows is not None
                    else {}
                ),
            }
            for policy_id, score, prediction in zip(
                split.test_ids, scores, predictions, strict=True
            )
        ]
        output = Path(output_root) / name
        outputs[name] = write_run_artifacts(
            output,
            config={
                "seed": seed,
                "detector": {"name": name, "params": params, "scale": scale},
                "tuning": tuning,
                "split": {
                    "protocol": "paper_90_10",
                    "validation_folds": validation_folds,
                    "test_ids": list(split.test_ids),
                },
                "threshold": {"mode": "calibrated", "percentile": threshold_percentile},
                "bootstrap": {"replicates": bootstrap_replicates, "alpha": 0.05},
            },
            metrics=metrics,
            predictions=prediction_rows,
        )
    return outputs


def select_detector_params(
    detector_name: str,
    train_features: np.ndarray,
    validation_features: np.ndarray,
    validation_labels: Sequence[int],
    candidates: Sequence[Mapping[str, Any]],
    *,
    scale: bool = True,
    seed: int = 42,
) -> dict[str, Any]:
    """Select detector parameters using a labelled validation set only."""
    if not candidates:
        raise ValueError("candidates must be non-empty")
    labels = np.asarray(validation_labels, dtype=int)
    values = np.asarray(validation_features, dtype=float)
    if values.ndim != 2 or len(labels) != len(values) or not np.isin(labels, [0, 1]).all():
        raise ValueError("validation features and labels must be aligned and binary")
    best_params: dict[str, Any] | None = None
    best_score = -np.inf
    for candidate in candidates:
        params = dict(candidate)
        model = fit_detector(detector_name, train_features, params=params, scale=scale, seed=seed)
        scores = model.score(values)
        predictions = model.predict_default(values)
        if np.any(labels == 1):
            score = evaluate_predictions(labels, scores, predictions)["f1"]
        else:
            # Paper-style validation contains normals only; select the
            # candidate with the fewest validation false positives.
            score = -float(np.mean(predictions))
        if score > best_score:
            best_score = score
            best_params = params
    assert best_params is not None
    return best_params


def run_feature_ablation(
    policy_ids: Sequence[str],
    feature_sets: Mapping[str, np.ndarray],
    labels: Mapping[str, int],
    output_root: str | Path,
    *,
    detector_name: str = "lof",
    detector_params: Mapping[str, Any] | None = None,
    validation_folds: int = 5,
    seed: int = 42,
    label_rows: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Path]:
    """Compare feature representations using the same deterministic split."""
    if not feature_sets:
        raise ValueError("feature_sets must be non-empty")
    outputs: dict[str, Path] = {}
    for name, features in feature_sets.items():
        if not isinstance(name, str) or not name:
            raise ValueError("feature set names must be non-empty strings")
        result = run_detector_comparison(
            policy_ids,
            features,
            labels,
            Path(output_root) / name,
            detectors=(detector_name,),
            detector_params={detector_name: dict(detector_params or {})},
            validation_folds=validation_folds,
            seed=seed,
            label_rows=label_rows,
        )
        outputs[name] = result[detector_name]
    return outputs


def contaminated_training_ids(
    train_normal_ids: Sequence[str],
    contamination_pool: Sequence[str],
    *,
    count: int,
    seed: int,
) -> tuple[str, ...]:
    """Select contamination rows without changing the separately locked test set."""
    normals = list(train_normal_ids)
    pool = list(contamination_pool)
    if len(normals) != len(set(normals)) or len(pool) != len(set(pool)):
        raise ValueError("training and contamination IDs must be unique")
    if any(policy_id in normals for policy_id in pool):
        raise ValueError("contamination IDs must not already be training normals")
    if isinstance(count, bool) or count < 0 or count > len(pool):
        raise ValueError("contamination count must fit the contamination pool")
    rng = np.random.default_rng(seed)
    selected = rng.choice(np.asarray(pool, dtype=object), size=count, replace=False)
    return tuple(normals + sorted(str(policy_id) for policy_id in selected))


def run_transfer_evaluation(
    source_policy_ids: Sequence[str],
    source_features: np.ndarray,
    source_labels: Mapping[str, int],
    target_policy_ids: Sequence[str],
    target_features: np.ndarray,
    target_labels: Mapping[str, int],
    *,
    detector_name: str = "lof",
    detector_params: Mapping[str, Any] | None = None,
    scale: bool = True,
    validation_folds: int = 5,
    threshold_percentile: float = 95.0,
    seed: int = 42,
) -> dict[str, Any]:
    """Tune a detector on the source organization and score a target split."""
    source_ids = list(source_policy_ids)
    target_ids = list(target_policy_ids)
    source_values = np.asarray(source_features, dtype=float)
    target_values = np.asarray(target_features, dtype=float)
    if source_values.ndim != 2 or source_values.shape[0] != len(source_ids):
        raise ValueError("source features must align with source policy IDs")
    if target_values.ndim != 2 or target_values.shape[0] != len(target_ids):
        raise ValueError("target features must align with target policy IDs")
    if source_values.shape[1] != target_values.shape[1]:
        raise ValueError("source and target features must have the same dimensions")
    source_split = make_evaluation_split(
        source_ids, source_labels, validation_folds=validation_folds, seed=seed
    )
    target_split = make_evaluation_split(
        target_ids, target_labels, validation_folds=validation_folds, seed=seed
    )
    source_train, _ = _split_indices(source_ids, source_split)
    target_train, target_test = _split_indices(target_ids, target_split)
    del target_train
    params = dict(detector_params or {})
    model = fit_detector(
        detector_name, source_values[source_train], params=params, scale=scale, seed=seed
    )
    validation_scores = cross_validated_normal_scores(
        source_split.train_normal_ids,
        source_values[source_train],
        source_split.validation_folds,
        detector_name=detector_name,
        detector_params=params,
        scale=scale,
        seed=seed,
    )
    threshold = calibrate_threshold(validation_scores, percentile=threshold_percentile)
    scores = model.score(target_values[target_test])
    predictions = predict_with_threshold(scores, threshold)
    labels = np.asarray([target_labels[policy_id] for policy_id in target_split.test_ids])
    return {
        "metrics": evaluate_predictions(labels, scores, predictions),
        "test_ids": target_split.test_ids,
        "scores": scores,
        "predictions": predictions,
        "threshold": threshold,
    }


def run_contamination_evaluation(
    policy_ids: Sequence[str],
    features: np.ndarray,
    labels: Mapping[str, int],
    *,
    fixed_test_ids: Sequence[str],
    contamination_pool: Sequence[str],
    contamination_counts: Sequence[int],
    detector_name: str = "lof",
    detector_params: Mapping[str, Any] | None = None,
    scale: bool = True,
    validation_folds: int = 5,
    threshold_percentile: float = 95.0,
    seed: int = 42,
) -> dict[int, dict[str, Any]]:
    """Evaluate training contamination while preserving one fixed test set."""
    ids = list(policy_ids)
    values = np.asarray(features, dtype=float)
    if values.ndim != 2 or values.shape[0] != len(ids):
        raise ValueError("features must align with policy IDs")
    fixed_test = tuple(fixed_test_ids)
    pool = tuple(contamination_pool)
    if not fixed_test or len(set(fixed_test)) != len(fixed_test):
        raise ValueError("fixed_test_ids must be unique and non-empty")
    if any(policy_id not in ids for policy_id in (*fixed_test, *pool)):
        raise ValueError("fixed test and contamination IDs must be known policy IDs")
    if set(fixed_test).intersection(pool):
        raise ValueError("contamination pool must not overlap the fixed test set")
    test_set = set(fixed_test)
    pool_set = set(pool)
    train_normal_ids = [
        policy_id
        for policy_id in ids
        if policy_id not in test_set and policy_id not in pool_set and labels[policy_id] == 0
    ]
    index_by_id = {policy_id: index for index, policy_id in enumerate(ids)}
    test_indices = np.asarray([index_by_id[policy_id] for policy_id in fixed_test])
    test_labels = np.asarray([labels[policy_id] for policy_id in fixed_test], dtype=int)
    normal_split = make_evaluation_split(
        train_normal_ids,
        {policy_id: 0 for policy_id in train_normal_ids},
        validation_folds=validation_folds,
        seed=seed,
    )
    normal_train_indices = np.asarray(
        [index_by_id[policy_id] for policy_id in normal_split.train_normal_ids]
    )
    params = dict(detector_params or {})
    outputs: dict[int, dict[str, Any]] = {}
    for count in contamination_counts:
        selected_ids = contaminated_training_ids(
            normal_split.train_normal_ids,
            pool,
            count=count,
            seed=seed + count,
        )
        fit_indices = np.asarray([index_by_id[policy_id] for policy_id in selected_ids])
        model = fit_detector(
            detector_name, values[fit_indices], params=params, scale=scale, seed=seed
        )
        validation_scores = cross_validated_normal_scores(
            normal_split.train_normal_ids,
            values[normal_train_indices],
            normal_split.validation_folds,
            detector_name=detector_name,
            detector_params=params,
            scale=scale,
            seed=seed,
        )
        threshold = calibrate_threshold(validation_scores, percentile=threshold_percentile)
        scores = model.score(values[test_indices])
        predictions = predict_with_threshold(scores, threshold)
        outputs[count] = {
            "metrics": evaluate_predictions(test_labels, scores, predictions),
            "test_ids": fixed_test,
            "training_ids": selected_ids,
            "threshold": threshold,
            "scores": scores,
            "predictions": predictions,
        }
    return outputs
