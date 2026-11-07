"""Reproducible experiment entry points and configuration contracts."""

from .aggregate import aggregate_seed_metrics, grouped_recall
from .artifacts import write_run_artifacts
from .baselines import run_baseline_comparison
from .config import EXPERIMENT_IDS, ExperimentConfig, load_config, resolve_config
from .evaluate import run_evaluation
from .protocols import (
    contaminated_training_ids,
    run_contamination_evaluation,
    run_detector_comparison,
    run_feature_ablation,
    run_transfer_evaluation,
    select_detector_params,
)
from .runner import load_organization, node2vec_features, run_configured_experiment

__all__ = [
    "EXPERIMENT_IDS",
    "ExperimentConfig",
    "load_config",
    "resolve_config",
    "write_run_artifacts",
    "aggregate_seed_metrics",
    "grouped_recall",
    "contaminated_training_ids",
    "run_detector_comparison",
    "run_feature_ablation",
    "run_transfer_evaluation",
    "run_contamination_evaluation",
    "select_detector_params",
    "load_organization",
    "node2vec_features",
    "run_configured_experiment",
    "run_baseline_comparison",
    "run_evaluation",
]
