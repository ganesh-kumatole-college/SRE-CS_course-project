import csv

import numpy as np

from misdet.experiments import run_evaluation


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
