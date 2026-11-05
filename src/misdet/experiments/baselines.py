"""Run comparable rule and feature baseline evaluations."""

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

from misdet.baselines import (
    BASELINE_NAMES,
    handcrafted_features,
    prevalence_output,
    random_scores,
    rule_output,
    validate_policies,
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


def _label_rows(
    labels: Mapping[str, int] | Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    if isinstance(labels, Mapping):
        rows = {policy_id: {"label": label} for policy_id, label in labels.items()}
    else:
        rows = {}
        for row in labels:
            policy_id = row.get("policy_id")
            if not isinstance(policy_id, str) or not policy_id or policy_id in rows:
                raise ValueError("label rows must have unique non-empty policy_id values")
            rows[policy_id] = dict(row)
    for policy_id, row in rows.items():
        label = row.get("label")
        if isinstance(label, bool) or label not in (0, 1):
            raise ValueError(f"label for {policy_id!r} must be 0 or 1")
    return rows


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _split_metadata(split: EvaluationSplit) -> dict[str, Any]:
    return {
        "train_normal_count": len(split.train_normal_ids),
        "validation_fold_counts": [len(fold) for fold in split.validation_folds],
        "test_count": len(split.test_ids),
        "test_ids": list(split.test_ids),
    }


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


def _top_k_predictions(scores: np.ndarray, count: int) -> np.ndarray:
    predictions = np.zeros(len(scores), dtype=int)
    if count:
        order = np.argsort(-scores, kind="stable")
        predictions[order[:count]] = 1
    return predictions


def _rule_or_random_output(
    name: str,
    test_policies: Sequence[Mapping[str, Any]],
    *,
    training_labels: Sequence[int],
    seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    if name == "random":
        scores = random_scores(len(test_policies), seed=seed)
        prevalence = float(np.mean(np.asarray(training_labels, dtype=int)))
        count = round(prevalence * len(test_policies))
        return scores, _top_k_predictions(scores, count)
    if name == "prevalence":
        output = prevalence_output(len(test_policies), training_labels)
        return output.scores, output.predictions
    output = rule_output(test_policies, name=name)
    return output.scores, output.predictions


def _write_run(
    output: Path,
    *,
    label_rows: Mapping[str, Mapping[str, Any]],
    test_ids: Sequence[str],
    scores: np.ndarray,
    predictions: np.ndarray,
    metrics: dict[str, Any],
    config: dict[str, Any],
) -> None:
    output.mkdir(parents=True)
    try:
        (output / "config.yaml").write_text(
            yaml.safe_dump(config, sort_keys=True), encoding="utf-8"
        )
        (output / "metrics.json").write_text(
            json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        with (output / "preds.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle, fieldnames=["policy_id", "score", "pred", "label", "misconfig_type"]
            )
            writer.writeheader()
            for policy_id, score, prediction in zip(test_ids, scores, predictions, strict=True):
                writer.writerow(
                    {
                        "policy_id": policy_id,
                        "score": float(score),
                        "pred": int(prediction),
                        "label": int(label_rows[policy_id]["label"]),
                        "misconfig_type": str(label_rows[policy_id].get("misconfig_type", "")),
                    }
                )
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


def run_baseline_comparison(
    policies: Sequence[Mapping[str, Any]],
    labels: Mapping[str, int] | Sequence[Mapping[str, Any]],
    output_dir: str | Path,
    *,
    baseline_names: Sequence[str] = BASELINE_NAMES,
    detector_name: str = "lof",
    detector_params: Mapping[str, Any] | None = None,
    scale: bool = True,
    threshold_percentile: float = 95.0,
    test_fraction: float = 0.1,
    validation_folds: int = 5,
    bootstrap_replicates: int = 2000,
    seed: int = 42,
) -> dict[str, Path]:
    """Evaluate selected baselines on one shared leakage-safe split."""
    records = validate_policies(policies)
    label_rows = _label_rows(labels)
    policy_ids = [policy["policy_id"] for policy in records]
    if set(label_rows) != set(policy_ids):
        raise ValueError("labels must contain exactly one row for every policy ID")
    names = list(baseline_names)
    if not names or len(names) != len(set(names)) or any(
        name not in BASELINE_NAMES for name in names
    ):
        raise ValueError(f"baseline_names must be unique names from {BASELINE_NAMES}")
    label_map = {policy_id: int(row["label"]) for policy_id, row in label_rows.items()}
    split = make_evaluation_split(
        policy_ids,
        label_map,
        test_fraction=test_fraction,
        validation_folds=validation_folds,
        seed=seed,
    )
    index_by_id = {policy_id: index for index, policy_id in enumerate(policy_ids)}
    train_indices = [index_by_id[policy_id] for policy_id in split.train_normal_ids]
    test_indices = [index_by_id[policy_id] for policy_id in split.test_ids]
    training_labels = [label_map[policy_id] for policy_id in split.train_normal_ids]
    test_labels = np.asarray([label_map[policy_id] for policy_id in split.test_ids], dtype=int)
    policy_by_id = {policy["policy_id"]: policy for policy in records}
    test_policies = [policy_by_id[policy_id] for policy_id in split.test_ids]
    all_features = handcrafted_features(records) if "handcrafted_feature" in names else None
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    outputs: dict[str, Path] = {}
    for name in names:
        output = output_root / name
        if output.exists():
            raise FileExistsError(f"refusing to overwrite existing run directory: {output}")
        if name == "handcrafted_feature":
            assert all_features is not None
            train_features = all_features[train_indices]
            model = fit_detector(
                detector_name,
                train_features,
                params=detector_params,
                scale=scale,
                seed=seed,
            )
            validation_scores = cross_validated_normal_scores(
                split.train_normal_ids,
                train_features,
                split.validation_folds,
                detector_name=detector_name,
                detector_params=detector_params,
                scale=scale,
                seed=seed,
            )
            threshold = calibrate_threshold(validation_scores, percentile=threshold_percentile)
            scores = model.score(all_features[test_indices])
            predictions = predict_with_threshold(scores, threshold)
        else:
            scores, predictions = _rule_or_random_output(
                name,
                test_policies,
                training_labels=training_labels,
                seed=seed,
            )
            threshold = None
        metrics = evaluate_predictions(test_labels, scores, predictions)
        metrics["bootstrap_ci"] = {
            metric: list(interval) if interval is not None else None
            for metric, interval in _bootstrap_metrics(
                test_labels,
                scores,
                predictions,
                replicates=bootstrap_replicates,
                seed=seed,
            ).items()
        }
        metrics["run"] = {
            "baseline": name,
            "threshold": threshold,
            **_split_metadata(split),
        }
        config = {
            "baseline": name,
            "seed": seed,
            "split": {
                "protocol": "paper_90_10",
                "test_fraction": test_fraction,
                "validation_folds": validation_folds,
                **_split_metadata(split),
            },
            "detector": {
                "name": detector_name,
                "params": dict(detector_params or {}),
                "scale": scale,
            },
            "threshold": {"mode": "calibrated", "percentile": threshold_percentile},
            "bootstrap": {"replicates": bootstrap_replicates, "alpha": 0.05},
        }
        _write_run(
            output,
            label_rows=label_rows,
            test_ids=split.test_ids,
            scores=scores,
            predictions=predictions,
            metrics=metrics,
            config=config,
        )
        outputs[name] = output
    return outputs
