"""Validate and dispatch one configured Phase 9 experiment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from misdet.experiments.config import EXPERIMENT_IDS, load_config
from misdet.experiments.runner import run_configured_experiment


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", required=True, choices=EXPERIMENT_IDS)
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=Path("configs/experiments"),
        help="Experiment config directory",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print the resolved config without running benchmark work",
    )
    args = parser.parse_args()
    config = load_config(args.config_dir / f"{args.experiment}.yaml")
    if args.dry_run:
        print(
            json.dumps(
                {
                    "exp_id": config.exp_id,
                    "orgs": config.orgs,
                    "seeds": config.seeds,
                    "methods": config.methods,
                    "detector": config.detector,
                    "input_root": str(config.input_root),
                    "output_root": str(config.output_root),
                },
                indent=2,
                default=list,
            )
        )
        return 0
    if not config.input_root.exists():
        raise FileNotFoundError(
            f"benchmark input root does not exist: {config.input_root}; "
            "prepare the approved local benchmark before running experiments"
        )
    outputs = run_configured_experiment(config)
    print(json.dumps({"exp_id": config.exp_id, "run_count": len(outputs)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
