import numpy as np
import pytest

from misdet.eval.bootstrap import bootstrap_confidence_interval
from misdet.eval.metrics import evaluate_predictions
from misdet.eval.splits import make_evaluation_split


def _labels(count: int = 20) -> dict[str, int]:
    return {f"policy-{index:02d}": int(index >= count - 4) for index in range(count)}


def test_make_evaluation_split_is_deterministic_and_leakage_safe():
    policy_labels = _labels()
    first = make_evaluation_split(list(policy_labels), policy_labels, seed=9, validation_folds=4)
    second = make_evaluation_split(list(policy_labels), policy_labels, seed=9, validation_folds=4)

    assert first == second
    train = set(first.train_normal_ids)
    validation = {policy_id for fold in first.validation_folds for policy_id in fold}
    test = set(first.test_ids)
    assert not train.intersection(test)
    assert validation == train
    assert all(policy_labels[policy_id] == 0 for policy_id in train | validation)
    positives = {policy_id for policy_id, label in policy_labels.items() if label == 1}
    assert positives.issubset(test)


def test_make_evaluation_split_rejects_malformed_inputs():
    labels = _labels()
    with pytest.raises(ValueError, match="unique"):
        make_evaluation_split(["duplicate", "duplicate"], {"duplicate": 0})
    with pytest.raises(ValueError, match="match"):
        make_evaluation_split(list(labels), {"other": 0})
    with pytest.raises(ValueError, match="at least two"):
        make_evaluation_split(["only"], {"only": 0})


def test_metrics_report_misconfiguration_as_positive():
    result = evaluate_predictions(
        [0, 0, 1, 1],
        [0.1, 0.2, 0.9, 0.8],
        [0, 1, 1, 0],
        alert_budgets=(2, 10),
    )

    assert result["confusion"] == {"tp": 1, "fp": 1, "fn": 1, "tn": 1}
    assert result["precision"] == pytest.approx(0.5)
    assert result["recall"] == pytest.approx(0.5)
    assert result["alert_budgets"]["10"] is None
    assert result["roc_auc"] == pytest.approx(1.0)


def test_metrics_return_none_for_undefined_auc():
    result = evaluate_predictions([0, 0], [0.1, 0.2], [0, 1])
    assert result["pr_auc"] is None
    assert result["roc_auc"] is None


def test_bootstrap_confidence_interval_is_repeatable():
    labels = np.array([0, 0, 1, 1])
    scores = np.array([0.1, 0.2, 0.8, 0.9])
    predictions = np.array([0, 0, 1, 1])

    def metric(y, _scores, pred):
        return float(np.mean(y == pred))

    first = bootstrap_confidence_interval(
        labels, scores, predictions, metric, replicates=100, seed=4
    )
    second = bootstrap_confidence_interval(
        labels, scores, predictions, metric, replicates=100, seed=4
    )
    assert first == second

