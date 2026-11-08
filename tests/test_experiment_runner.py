import csv
import json

import numpy as np
import pytest

from misdet.experiments import run_evaluation
from misdet.experiments.artifacts import write_run_artifacts
from misdet.experiments.config import resolve_config
from misdet.experiments.runner import (
    OrganizationBenchmark,
    _write_cross_seed_summary,
    run_contamination_for_org,
)


def _make_exp_config(tmp_path, exp_id="exp01", contamination_levels=None):
    return resolve_config(
        {
            "exp_id": exp_id,
            "orgs": ["alpha"],
            "seeds": [0, 1],
            "paths": {
                "input_root": str(tmp_path / "bench"),
                "output_root": str(tmp_path / "runs"),
            },
            "split": {
                "protocol": "paper_90_10",
                "test_fraction": 0.1,
                "validation_folds": 2,
                "misconfigs_in_test": "all",
            },
            "methods": ["node2vec"],
            "detector": "lof",
            "detector_params": {"n_neighbors": 5, "novelty": True},
            "threshold": {},
            "metrics": ["precision", "recall", "f1"],
            "bootstrap_replicates": 20,
            "contamination_levels": contamination_levels or [0, 1],
        }
    )


def _write_fake_run(path, seed):
    preds = [
        {
            "policy_id": f"p{i:02d}",
            "score": float(i),
            "pred": int(i > 3),
            "label": int(i > 3),
            "misconfig_type": "permissive" if i > 3 else "none",
        }
        for i in range(6)
    ]
    metrics = {
        "precision": 0.8,
        "recall": 0.6,
        "f1": 0.7,
        "confusion": {"tp": 3, "fp": 1, "fn": 2, "tn": 4},
    }
    return write_run_artifacts(
        path, config={"seed": seed}, metrics=metrics, predictions=preds
    )


def _make_benchmark(n_normal=25, n_positive=5):
    n = n_normal + n_positive
    policy_ids = [f"p{i:02d}" for i in range(n)]
    label_val = {pid: int(i >= n_normal) for i, pid in enumerate(policy_ids)}
    policies = [
        {
            "policy_id": pid,
            "org": "alpha",
            "source": "synthetic_custom",
            "document": {
                "Statement": [{"Effect": "Allow", "Action": ["s3:*"], "Resource": ["*"]}]
            },
        }
        for pid in policy_ids
    ]
    labels = [
        {
            "policy_id": pid,
            "label": label_val[pid],
            "org": "alpha",
            "misconfig_type": "permissive" if label_val[pid] else "none",
            "operator_id": "",
            "difficulty": "",
            "hard_negative": False,
            "attached_entity_id": "",
            "source": "synthetic_custom",
            "rationale": "",
        }
        for pid in policy_ids
    ]
    return OrganizationBenchmark(tuple(policies), (), (), tuple(labels))


def test_run_evaluation_writes_complete_artifacts(tmp_path):
    policy_ids = [f"policy-{index:02d}" for index in range(20)]
    labels = [
        {
            "policy_id": policy_id,
            "label": int(index >= 16),
            "misconfig_type": "permissive" if index >= 16 else "none",
        }
        for index, policy_id in enumerate(policy_ids)
    ]
    embeddings = np.arange(80, dtype=float).reshape(20, 4)

    output = run_evaluation(
        policy_ids,
        embeddings,
        labels,
        tmp_path / "run",
        detector_name="one_class_svm",
        detector_params={"nu": 0.2},
        validation_folds=4,
        bootstrap_replicates=20,
        seed=3,
    )

    assert {path.name for path in output.iterdir()} == {
        "config.yaml",
        "metrics.json",
        "preds.csv",
        "env.txt",
        "git_sha.txt",
    }
    with (output / "preds.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 6
    assert [row["policy_id"] for row in rows] == sorted(row["policy_id"] for row in rows)


# --- F-06 regression: cross-seed summary aggregates across seeds ---

def test_cross_seed_summary_aggregates_across_seeds(tmp_path):
    config = _make_exp_config(tmp_path)
    summary_root = config.output_root / config.exp_id
    out0 = _write_fake_run(summary_root / "alpha" / "0" / "lof", seed=0)
    out1 = _write_fake_run(summary_root / "alpha" / "1" / "lof", seed=1)
    _write_cross_seed_summary(config, [out0, out1])
    summary = json.loads((summary_root / "summary.json").read_text())
    assert "alpha/lof" in summary
    assert summary["alpha/lof"]["seed_count"] == 2


def test_cross_seed_summary_includes_bootstrap_recall_ci(tmp_path):
    config = _make_exp_config(tmp_path)
    summary_root = config.output_root / config.exp_id
    out0 = _write_fake_run(summary_root / "alpha" / "0" / "lof", seed=0)
    out1 = _write_fake_run(summary_root / "alpha" / "1" / "lof", seed=1)
    _write_cross_seed_summary(config, [out0, out1])
    summary = json.loads((summary_root / "summary.json").read_text())
    assert "bootstrap_recall_ci" in summary["alpha/lof"]
    ci = summary["alpha/lof"]["bootstrap_recall_ci"]
    assert ci is None or (isinstance(ci, list) and len(ci) == 2)


def test_cross_seed_summary_does_not_group_by_seed(tmp_path):
    """Each method must appear once with seed_count == number of seeds, not once per seed."""
    config = _make_exp_config(tmp_path)
    summary_root = config.output_root / config.exp_id
    out0 = _write_fake_run(summary_root / "alpha" / "0" / "lof", seed=0)
    out1 = _write_fake_run(summary_root / "alpha" / "1" / "lof", seed=1)
    _write_cross_seed_summary(config, [out0, out1])
    summary = json.loads((summary_root / "summary.json").read_text())
    # Must not have seed-specific keys like "alpha/0" or "0/lof".
    for key in summary:
        parts = key.split("/")
        assert not any(part.isdigit() for part in parts), (
            f"summary key {key!r} contains a seed component"
        )


# --- F-03 regression: EXP-04 fixed test contains normals and positives ---

def test_contamination_fixed_test_contains_normals_and_positives(tmp_path):
    # Need enough positives so some remain outside the locked test set.
    benchmark = _make_benchmark(n_normal=50, n_positive=20)
    config = _make_exp_config(tmp_path, exp_id="exp04", contamination_levels=[0, 1])
    n = len(benchmark.policies)
    embeddings = np.arange(n * 4, dtype=float).reshape(n, 4)
    output_root = config.output_root / config.exp_id / "alpha" / "0"
    paths = run_contamination_for_org(config, benchmark, embeddings, output_root, seed=0)
    assert len(paths) == 2
    test_id_sets = []
    for path in paths:
        with (path / "preds.csv").open(newline="", encoding="utf-8") as fh:
            test_id_sets.append({row["policy_id"] for row in csv.DictReader(fh)})
    # Fixed test IDs must be identical across contamination levels.
    assert test_id_sets[0] == test_id_sets[1]
    # Test set must contain at least one positive and one normal.
    assert any(benchmark.label_map[pid] == 1 for pid in test_id_sets[0])
    assert any(benchmark.label_map[pid] == 0 for pid in test_id_sets[0])


def test_contamination_percent_level_resolves_against_pool(tmp_path):
    benchmark = _make_benchmark(n_normal=50, n_positive=20)
    config = _make_exp_config(tmp_path, exp_id="exp04", contamination_levels=[0, "percent"])
    n = len(benchmark.policies)
    embeddings = np.arange(n * 4, dtype=float).reshape(n, 4)
    output_root = config.output_root / config.exp_id / "alpha" / "0"
    # Should not raise; percent resolves to max(1, pool_size * 10 // 100).
    paths = run_contamination_for_org(config, benchmark, embeddings, output_root, seed=0)
    assert len(paths) == 2


def test_contamination_absolute_count_exceeding_pool_raises(tmp_path):
    # 3 positives: all go into the locked test set, leaving pool empty -> different error.
    # Use enough positives that some remain in pool, then request more than pool size.
    benchmark = _make_benchmark(n_normal=50, n_positive=20)
    # contamination_levels=[0, 1000] — 1000 exceeds any realistic pool.
    config = _make_exp_config(tmp_path, exp_id="exp04", contamination_levels=[0, 1000])
    n = len(benchmark.policies)
    embeddings = np.arange(n * 4, dtype=float).reshape(n, 4)
    output_root = config.output_root / config.exp_id / "alpha" / "0"
    with pytest.raises(ValueError, match="exceeds pool size"):
        run_contamination_for_org(config, benchmark, embeddings, output_root, seed=0)
