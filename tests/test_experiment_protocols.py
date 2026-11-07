import numpy as np
import yaml

from misdet.experiments.protocols import (
    contaminated_training_ids,
    run_contamination_evaluation,
    run_detector_comparison,
    run_feature_ablation,
    run_transfer_evaluation,
    select_detector_params,
)


def test_detector_comparison_reuses_one_locked_test_set(tmp_path):
    policy_ids = [f"policy-{index:02d}" for index in range(20)]
    labels = {policy_id: int(index >= 16) for index, policy_id in enumerate(policy_ids)}
    features = np.arange(80, dtype=float).reshape(20, 4)

    outputs = run_detector_comparison(
        policy_ids,
        features,
        labels,
        tmp_path / "runs",
        detectors=("lof", "one_class_svm"),
        detector_params={"lof": {"n_neighbors": 5}, "one_class_svm": {"nu": 0.2}},
        detector_grid={
            "lof": (
                {"n_neighbors": 3, "novelty": True},
                {"n_neighbors": 5, "novelty": True},
            )
        },
        validation_folds=4,
        seed=3,
    )

    first_config = yaml.safe_load((outputs["lof"] / "config.yaml").read_text())
    second_config = yaml.safe_load((outputs["one_class_svm"] / "config.yaml").read_text())
    assert "policy-16" in first_config["split"]["test_ids"]
    assert first_config["split"]["test_ids"] == second_config["split"]["test_ids"]
    assert first_config["tuning"]["mode"] == "validation_normal_fold"
    assert first_config["tuning"]["candidate_count"] == 2


def test_contamination_selection_is_seeded_and_does_not_change_locked_test_ids():
    train = ("normal-1", "normal-2")
    contamination_pool = ("misconfig-1", "misconfig-2", "misconfig-3")

    first = contaminated_training_ids(train, contamination_pool, count=2, seed=7)
    second = contaminated_training_ids(train, contamination_pool, count=2, seed=7)

    assert first == second
    assert first[:2] == train
    assert set(first[2:]).issubset(contamination_pool)


def test_feature_ablation_uses_identical_test_ids_for_each_representation(tmp_path):
    policy_ids = [f"policy-{index:02d}" for index in range(20)]
    labels = {policy_id: int(index >= 16) for index, policy_id in enumerate(policy_ids)}
    feature_sets = {
        "handcrafted_feature": np.arange(80, dtype=float).reshape(20, 4),
        "bag_of_actions": np.arange(60, dtype=float).reshape(20, 3),
    }

    outputs = run_feature_ablation(
        policy_ids,
        feature_sets,
        labels,
        tmp_path / "runs",
        detector_params={"n_neighbors": 5},
        validation_folds=4,
        seed=3,
    )

    configs = [(path / "config.yaml").read_text() for path in outputs.values()]
    assert configs[0].split("test_ids:")[1] == configs[1].split("test_ids:")[1]


def test_transfer_evaluation_scores_target_with_source_threshold():
    source_ids = [f"source-{index:02d}" for index in range(12)]
    target_ids = [f"target-{index:02d}" for index in range(12)]
    labels = {policy_id: int(index >= 10) for index, policy_id in enumerate(source_ids)}
    target_labels = {policy_id: int(index >= 10) for index, policy_id in enumerate(target_ids)}
    source_features = np.arange(36, dtype=float).reshape(12, 3)
    target_features = source_features.copy()

    result = run_transfer_evaluation(
        source_ids,
        source_features,
        labels,
        target_ids,
        target_features,
        target_labels,
        detector_params={"n_neighbors": 3},
        validation_folds=2,
        seed=3,
    )

    assert set(result["test_ids"]) >= {"target-10", "target-11"}
    assert len(result["test_ids"]) == 3
    assert result["threshold"] == result["threshold"]


def test_contamination_evaluation_keeps_fixed_test_ids():
    policy_ids = [f"policy-{index:02d}" for index in range(16)]
    labels = {policy_id: int(index >= 12) for index, policy_id in enumerate(policy_ids)}
    features = np.arange(48, dtype=float).reshape(16, 3)
    fixed_test = tuple(policy_ids[12:])
    contamination_pool = tuple(policy_ids[8:12])

    results = run_contamination_evaluation(
        policy_ids,
        features,
        labels,
        fixed_test_ids=fixed_test,
        contamination_pool=contamination_pool,
        contamination_counts=(0, 1, 2),
        detector_params={"n_neighbors": 3},
        validation_folds=2,
        seed=3,
    )

    assert all(result["test_ids"] == fixed_test for result in results.values())


def test_detector_parameter_selection_uses_validation_rows():
    train_features = np.arange(30, dtype=float).reshape(10, 3)
    validation_features = np.arange(12, dtype=float).reshape(4, 3)
    validation_labels = [0, 0, 1, 1]

    selected = select_detector_params(
        "one_class_svm",
        train_features,
        validation_features,
        validation_labels,
        ({"nu": 0.1}, {"nu": 0.5}),
        seed=3,
    )

    assert selected in ({"nu": 0.1}, {"nu": 0.5})
