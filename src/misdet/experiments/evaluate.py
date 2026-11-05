"""Run one deterministic detector evaluation and write its artifacts."""

from __future__ import annotations

import csv
import json
import platform
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from misdet.detect.models import fit_detector
from misdet.detect.thresholds import (
    calibrate_threshold,
    cross_validated_normal_scores,
    predict_with_threshold,
)
from misdet.eval.bootstrap import bootstrap_confidence_interval
from misdet.eval.metrics import evaluate_predictions
from misdet.eval.splits import EvaluationSplit, make_evaluation_split


def _label_mapping(labels: Mapping[str, int] | Sequence[Mapping[str, Any]]) -> dict[str, int]:
    if isinstance(labels, Mapping):
        rows = labels.items()
    else:
        rows = ((row.get("policy_id"), row.get("label")) for row in labels)
    result: dict[str, int] = {}
    for policy_id, label in rows:
        if not isinstance(policy_id, str) or not policy_id:
            raise ValueError("each label row must contain a non-empty policy_id")
        if isinstance(label, str) and label in {"0", "1"}:
            label = int(label)
        if isinstance(label, bool) or label not in (0, 1):
            raise ValueError(f"label for {policy_id!r} must be 0 or 1")
        if policy_id in result:
            raise ValueError(f"duplicate label for policy {policy_id!r}")
        result[policy_id] = int(label)
    return result


def _label_rows(
    labels: Mapping[str, int] | Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    if isinstance(labels, Mapping):
        return {policy_id: {"label": label} for policy_id, label in labels.items()}
    rows: dict[str, dict[str, Any]] = {}
    for row in labels:
        policy_id = row.get("policy_id")
        if not isinstance(policy_id, str) or policy_id in rows:
            raise ValueError("label rows must have unique non-empty policy_id values")
        rows[policy_id] = dict(row)
    return rows


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _validate_inputs(policy_ids: Sequence[str], embeddings: np.ndarray) -> np.ndarray:
    ids = list(policy_ids)
    if not ids or len(ids) != len(set(ids)) or any(not isinstance(value, str) for value in ids):
        raise ValueError("policy_ids must be unique non-empty strings")
    values = np.asarray(embeddings, dtype=float)
    if values.ndim != 2 or values.shape[0] != len(ids) or values.shape[1] == 0:
        raise ValueError("embeddings must be a two-dimensional array aligned with policy_ids")
    if not np.isfinite(values).all():
        raise ValueError("embeddings must contain only finite values")
    return values


def _bootstrap_metrics(
    labels: np.ndarray,
    scores: np.ndarray,
    predictions: np.ndarray,
    *,
    replicates: int,
    seed: int,
) -> dict[str, tuple[float, float] | None]:
    metric_functions = {
        "precision": lambda y, _s, p: precision_score(y, p, zero_division=0),
        "recall": lambda y, _s, p: recall_score(y, p, zero_division=0),
        "f1": lambda y, _s, p: f1_score(y, p, zero_division=0),
        "pr_auc": lambda y, s, _p: average_precision_score(y, s)
        if len(np.unique(y)) > 1
        else None,
        "roc_auc": lambda y, s, _p: roc_auc_score(y, s) if len(np.unique(y)) > 1 else None,
    }
    return {
        name: bootstrap_confidence_interval(
            labels,
            scores,
            predictions,
            metric,
            replicates=replicates,
            seed=seed,
        )
        for name, metric in metric_functions.items()
    }


def _split_metadata(split: EvaluationSplit) -> dict[str, Any]:
    return {
        "train_normal_count": len(split.train_normal_ids),
        "validation_fold_counts": [len(fold) for fold in split.validation_folds],
        "test_count": len(split.test_ids),
    }


def run_evaluation(
    policy_ids: Sequence[str],
    embeddings: np.ndarray,
    labels: Mapping[str, int] | Sequence[Mapping[str, Any]],
    output_dir: str | Path,
    *,
    detector_name: str = "lof",
    detector_params: Mapping[str, Any] | None = None,
    scale: bool = True,
    threshold_mode: str = "calibrated",
    threshold_percentile: float = 95.0,
    test_fraction: float = 0.1,
    validation_folds: int = 5,
    bootstrap_replicates: int = 2000,
    seed: int = 42,
) -> Path:
    """Fit, evaluate, and persist one detector run without test-set fitting."""
    values = _validate_inputs(policy_ids, embeddings)
    label_rows = _label_rows(labels)
    label_map = _label_mapping(labels)
    if set(label_map) != set(policy_ids):
        raise ValueError("labels must contain exactly one row for every policy ID")
    if threshold_mode not in {"default", "calibrated"}:
        raise ValueError("threshold_mode must be 'default' or 'calibrated'")

    split = make_evaluation_split(
        policy_ids,
        label_map,
        test_fraction=test_fraction,
        validation_folds=validation_folds,
        seed=seed,
    )
    index_by_id = {policy_id: index for index, policy_id in enumerate(policy_ids)}
    train_indices = np.asarray([index_by_id[policy_id] for policy_id in split.train_normal_ids])
    test_indices = np.asarray([index_by_id[policy_id] for policy_id in split.test_ids])
    model = fit_detector(
        detector_name,
        values[train_indices],
        params=detector_params,
        scale=scale,
        seed=seed,
    )
    test_features = values[test_indices]
    scores = model.score(test_features)
    if threshold_mode == "default":
        predictions = model.predict_default(test_features)
        threshold: float | None = None
    else:
        validation_scores = cross_validated_normal_scores(
            split.train_normal_ids,
            values[train_indices],
            split.validation_folds,
            detector_name=detector_name,
            detector_params=detector_params,
            scale=scale,
            seed=seed,
        )
        threshold = calibrate_threshold(validation_scores, percentile=threshold_percentile)
        predictions = predict_with_threshold(scores, threshold)

    test_labels = np.asarray([label_map[policy_id] for policy_id in split.test_ids], dtype=int)
    metrics = evaluate_predictions(test_labels, scores, predictions)
    metrics["bootstrap_ci"] = {
        name: list(interval) if interval is not None else None
        for name, interval in _bootstrap_metrics(
            test_labels,
            scores,
            predictions,
            replicates=bootstrap_replicates,
            seed=seed,
        ).items()
    }
    predictions_rows = [
        {
            "policy_id": policy_id,
            "score": float(score),
            "pred": int(prediction),
            "label": int(label_map[policy_id]),
            "misconfig_type": str(label_rows[policy_id].get("misconfig_type", "")),
        }
        for policy_id, score, prediction in zip(split.test_ids, scores, predictions, strict=True)
    ]
    resolved_config = {
        "seed": seed,
        "detector": {
            "name": detector_name,
            "params": dict(detector_params or {}),
            "scale": scale,
        },
        "split": {
            "protocol": "paper_90_10",
            "test_fraction": test_fraction,
            "validation_folds": validation_folds,
            **_split_metadata(split),
        },
        "threshold": {"mode": threshold_mode, "percentile": threshold_percentile},
        "bootstrap": {"replicates": bootstrap_replicates, "alpha": 0.05},
    }
    metrics["run"] = {"detector": detector_name, "threshold": threshold, **_split_metadata(split)}
    output = Path(output_dir)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing run directory: {output}")
    output.mkdir(parents=True)
    try:
        (output / "config.yaml").write_text(
            yaml.safe_dump(resolved_config, sort_keys=True), encoding="utf-8"
        )
        (output / "metrics.json").write_text(
            json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        with (output / "preds.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle, fieldnames=["policy_id", "score", "pred", "label", "misconfig_type"]
            )
            writer.writeheader()
            writer.writerows(predictions_rows)
        (output / "env.txt").write_text(
            f"platform={platform.platform()}\npython={sys.version.split()[0]}\n", encoding="utf-8"
        )
        (output / "git_sha.txt").write_text(_git_sha() + "\n", encoding="utf-8")
    except Exception:
        for path in output.iterdir():
            path.unlink()
        output.rmdir()
        raise
    return output
