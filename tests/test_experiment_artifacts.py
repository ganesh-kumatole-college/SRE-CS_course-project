import csv
import json

import pytest

from misdet.experiments.artifacts import REQUIRED_ARTIFACTS, write_run_artifacts


def _prediction(policy_id: str) -> dict[str, object]:
    return {
        "policy_id": policy_id,
        "score": 0.5,
        "pred": 0,
        "label": 0,
        "misconfig_type": "none",
    }


def test_write_run_artifacts_creates_complete_non_overwriting_run(tmp_path):
    output = write_run_artifacts(
        tmp_path / "run",
        config={"exp_id": "exp01", "seed": 0},
        metrics={"recall": 0.0, "confusion": {"tp": 0}},
        predictions=[_prediction("policy-1")],
    )

    assert {path.name for path in output.iterdir()} == set(REQUIRED_ARTIFACTS)
    assert json.loads((output / "metrics.json").read_text()) == {
        "confusion": {"tp": 0},
        "recall": 0.0,
    }
    with (output / "preds.csv").open(newline="") as handle:
        assert list(csv.DictReader(handle))[0]["policy_id"] == "policy-1"
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        write_run_artifacts(
            output,
            config={},
            metrics={},
            predictions=[],
        )


def test_write_run_artifacts_rejects_incomplete_or_duplicate_predictions(tmp_path):
    with pytest.raises(ValueError, match="missing fields"):
        write_run_artifacts(
            tmp_path / "missing",
            config={},
            metrics={},
            predictions=[{"policy_id": "policy-1"}],
        )
    with pytest.raises(ValueError, match="duplicate"):
        write_run_artifacts(
            tmp_path / "duplicate",
            config={},
            metrics={},
            predictions=[_prediction("policy-1"), _prediction("policy-1")],
        )
