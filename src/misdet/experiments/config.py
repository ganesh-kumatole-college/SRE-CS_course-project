"""Validated configuration contracts for reproducible experiments."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

EXPERIMENT_IDS = ("exp01", "exp02", "exp03", "exp04", "exp07", "exp13")
SUPPORTED_SPLIT_PROTOCOLS = ("paper_90_10",)
SUPPORTED_DETECTORS = ("lof", "one_class_svm", "isolation_forest", "robust_covariance")
SUPPORTED_METHODS = (
    "random",
    "prevalence",
    "wildcard",
    "permissiveness",
    "offline_custodian_equivalent",
    "handcrafted_feature",
    "bag_of_actions",
    "node2vec",
)


@dataclass(frozen=True)
class SplitConfig:
    """The split contract shared by comparable experiment methods."""

    protocol: str
    test_fraction: float
    validation_folds: int
    misconfigs_in_test: str


@dataclass(frozen=True)
class ExperimentConfig:
    """A fully validated experiment configuration."""

    exp_id: str
    orgs: tuple[str, ...]
    seeds: tuple[int, ...]
    input_root: Path
    output_root: Path
    split: SplitConfig
    methods: tuple[str, ...]
    detector: str
    detector_params: dict[str, Any]
    detector_grid: dict[str, tuple[dict[str, Any], ...]]
    threshold: dict[str, Any]
    metrics: tuple[str, ...]
    bootstrap_replicates: int


def _require_mapping(value: Any, *, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a mapping")
    return value


def _require_non_empty_string(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _resolve_seeds(value: Any) -> tuple[int, ...]:
    if value == "0..29":
        return tuple(range(30))
    if not isinstance(value, list) or not value:
        raise ValueError("seeds must be a non-empty list or '0..29'")
    if any(isinstance(seed, bool) or not isinstance(seed, int) for seed in value):
        raise ValueError("seeds must contain only integers")
    resolved = tuple(value)
    if len(set(resolved)) != len(resolved):
        raise ValueError("seeds must not contain duplicates")
    if tuple(sorted(resolved)) != resolved:
        raise ValueError("seeds must be in ascending order")
    return resolved


def _resolve_methods(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError("methods must be a non-empty list")
    methods = tuple(_require_non_empty_string(item, name="method") for item in value)
    if len(set(methods)) != len(methods):
        raise ValueError("methods must not contain duplicates")
    unknown = sorted(set(methods) - set(SUPPORTED_METHODS))
    if unknown:
        raise ValueError(f"unsupported methods: {unknown}")
    return methods


def _resolve_split(value: Any) -> SplitConfig:
    raw = _require_mapping(value, name="split")
    protocol = _require_non_empty_string(raw.get("protocol"), name="split.protocol")
    if protocol not in SUPPORTED_SPLIT_PROTOCOLS:
        raise ValueError(f"unsupported split protocol: {protocol!r}")
    test_fraction = raw.get("test_fraction", 0.1)
    if isinstance(test_fraction, bool) or not isinstance(test_fraction, (float, int)):
        raise ValueError("split.test_fraction must be numeric")
    if not 0 < float(test_fraction) < 1:
        raise ValueError("split.test_fraction must be between 0 and 1")
    validation_folds = raw.get("validation_folds", 5)
    if isinstance(validation_folds, bool) or not isinstance(validation_folds, int):
        raise ValueError("split.validation_folds must be an integer")
    if validation_folds < 2:
        raise ValueError("split.validation_folds must be at least 2")
    misconfigs_in_test = _require_non_empty_string(
        raw.get("misconfigs_in_test", "all"), name="split.misconfigs_in_test"
    )
    return SplitConfig(
        protocol=protocol,
        test_fraction=float(test_fraction),
        validation_folds=validation_folds,
        misconfigs_in_test=misconfigs_in_test,
    )


def resolve_config(raw: dict[str, Any], *, base_dir: str | Path = ".") -> ExperimentConfig:
    """Validate and resolve one decoded YAML experiment configuration."""
    exp_id = _require_non_empty_string(raw.get("exp_id"), name="exp_id")
    if exp_id not in EXPERIMENT_IDS:
        raise ValueError(f"unsupported experiment ID: {exp_id!r}")
    orgs_raw = raw.get("orgs")
    if not isinstance(orgs_raw, list) or not orgs_raw:
        raise ValueError("orgs must be a non-empty list")
    orgs = tuple(_require_non_empty_string(org, name="org") for org in orgs_raw)
    if len(set(orgs)) != len(orgs):
        raise ValueError("orgs must not contain duplicates")
    paths = _require_mapping(raw.get("paths", {}), name="paths")
    input_root = Path(paths.get("input_root", "data/benchmark"))
    output_root = Path(paths.get("output_root", "results/runs"))
    detector = _require_non_empty_string(raw.get("detector", "lof"), name="detector")
    if detector not in SUPPORTED_DETECTORS:
        raise ValueError(f"unsupported detector: {detector!r}")
    detector_params = _require_mapping(raw.get("detector_params", {}), name="detector_params")
    grid_raw = _require_mapping(raw.get("detector_grid", {}), name="detector_grid")
    detector_grid: dict[str, tuple[dict[str, Any], ...]] = {}
    for name, candidates in grid_raw.items():
        if name not in SUPPORTED_DETECTORS:
            raise ValueError(f"unsupported detector in detector_grid: {name!r}")
        if not isinstance(candidates, list) or not candidates:
            raise ValueError(f"detector_grid.{name} must be a non-empty list")
        if any(not isinstance(candidate, dict) for candidate in candidates):
            raise ValueError(f"detector_grid.{name} candidates must be mappings")
        detector_grid[name] = tuple(dict(candidate) for candidate in candidates)
    threshold = _require_mapping(raw.get("threshold", {}), name="threshold")
    metrics_raw = raw.get("metrics", [])
    if not isinstance(metrics_raw, list) or not metrics_raw:
        raise ValueError("metrics must be a non-empty list")
    metrics = tuple(_require_non_empty_string(metric, name="metric") for metric in metrics_raw)
    bootstrap_replicates = raw.get("bootstrap_replicates", 2000)
    if isinstance(bootstrap_replicates, bool) or not isinstance(bootstrap_replicates, int):
        raise ValueError("bootstrap_replicates must be an integer")
    if bootstrap_replicates <= 0:
        raise ValueError("bootstrap_replicates must be positive")
    root = Path(base_dir)
    return ExperimentConfig(
        exp_id=exp_id,
        orgs=orgs,
        seeds=_resolve_seeds(raw.get("seeds")),
        input_root=(root / input_root).resolve() if not input_root.is_absolute() else input_root,
        output_root=(root / output_root).resolve()
        if not output_root.is_absolute()
        else output_root,
        split=_resolve_split(raw.get("split", {})),
        methods=_resolve_methods(raw.get("methods")),
        detector=detector,
        detector_params=dict(detector_params),
        detector_grid=detector_grid,
        threshold=dict(threshold),
        metrics=metrics,
        bootstrap_replicates=bootstrap_replicates,
    )


def load_config(path: str | Path) -> ExperimentConfig:
    """Load and validate an experiment YAML file."""
    config_path = Path(path)
    with config_path.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    if not isinstance(raw, dict):
        raise ValueError(f"configuration {config_path} must contain a mapping")
    return resolve_config(raw, base_dir=config_path.parent.parent.parent)
