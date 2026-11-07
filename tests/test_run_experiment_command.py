import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_run_exp_dry_run_dispatches_a_named_config():
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_experiment.py",
            "--experiment",
            "exp07",
            "--dry-run",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert payload["exp_id"] == "exp07"
    assert payload["seeds"] == list(range(30))
