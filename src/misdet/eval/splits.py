"""Leakage-safe train, validation, and locked-test split helpers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import ceil

import numpy as np


@dataclass(frozen=True)
class EvaluationSplit:
    """A deterministic split of policy IDs for anomaly evaluation."""

    train_normal_ids: tuple[str, ...]
    validation_folds: tuple[tuple[str, ...], ...]
    test_ids: tuple[str, ...]


def _validate_policy_ids(policy_ids: Sequence[str]) -> list[str]:
    if isinstance(policy_ids, (str, bytes)):
        raise TypeError("policy_ids must be a sequence of strings")
    values = list(policy_ids)
    if not values or any(not isinstance(value, str) or not value for value in values):
        raise ValueError("policy_ids must contain non-empty strings")
    if len(set(values)) != len(values):
        raise ValueError("policy_ids must be unique")
    return values


def _validate_labels(policy_ids: Sequence[str], labels: Mapping[str, int]) -> dict[str, int]:
    if not isinstance(labels, Mapping):
        raise TypeError("labels must map policy IDs to integer labels")
    expected = set(policy_ids)
    if set(labels) != expected:
        missing = sorted(expected - set(labels))
        extra = sorted(set(labels) - expected)
        raise ValueError(f"labels must match policy_ids; missing={missing}, extra={extra}")
    normalized: dict[str, int] = {}
    for policy_id in policy_ids:
        label = labels[policy_id]
        if isinstance(label, bool) or label not in (0, 1):
            raise ValueError(f"label for {policy_id!r} must be 0 or 1")
        normalized[policy_id] = int(label)
    return normalized


def make_evaluation_split(
    policy_ids: Sequence[str],
    labels: Mapping[str, int],
    *,
    test_fraction: float = 0.1,
    validation_folds: int = 5,
    seed: int = 42,
) -> EvaluationSplit:
    """Create the paper-style split with all positives locked in the test set."""
    ids = _validate_policy_ids(policy_ids)
    normalized_labels = _validate_labels(ids, labels)
    if not 0 < test_fraction < 1:
        raise ValueError("test_fraction must be between 0 and 1")
    if not isinstance(validation_folds, int) or isinstance(validation_folds, bool):
        raise TypeError("validation_folds must be an integer")
    if validation_folds < 2:
        raise ValueError("validation_folds must be at least 2")

    normals = sorted(policy_id for policy_id in ids if normalized_labels[policy_id] == 0)
    positives = sorted(policy_id for policy_id in ids if normalized_labels[policy_id] == 1)
    if len(normals) < 2:
        raise ValueError("at least two normal policies are required")

    rng = np.random.default_rng(seed)
    shuffled_normals = np.asarray(normals, dtype=object)
    rng.shuffle(shuffled_normals)
    test_normal_count = max(1, ceil(len(normals) * test_fraction))
    if test_normal_count >= len(normals):
        raise ValueError("test_fraction leaves no normal policies for training")

    test_normals = sorted(str(value) for value in shuffled_normals[:test_normal_count])
    train_normals = sorted(str(value) for value in shuffled_normals[test_normal_count:])
    if validation_folds > len(train_normals):
        raise ValueError("validation_folds cannot exceed the number of training normals")

    fold_arrays = np.array_split(np.asarray(train_normals, dtype=object), validation_folds)
    folds = tuple(tuple(sorted(str(value) for value in fold)) for fold in fold_arrays)
    return EvaluationSplit(
        train_normal_ids=tuple(train_normals),
        validation_folds=folds,
        test_ids=tuple(sorted(test_normals + positives)),
    )
