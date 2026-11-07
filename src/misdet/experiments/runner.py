"""Load the local synthetic benchmark and dispatch configured experiment work."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from misdet.baselines import fit_bag_of_actions, handcrafted_features, transform_bag_of_actions
from misdet.embed import embed_policy_nodes
from misdet.eval.splits import make_evaluation_split
from misdet.graph import build_policy_graph

from .aggregate import aggregate_seed_metrics, grouped_recall
from .artifacts import write_run_artifacts
from .config import ExperimentConfig
from .protocols import (
    run_contamination_evaluation,
    run_detector_comparison,
    run_feature_ablation,
    run_transfer_evaluation,
)


@dataclass(frozen=True)
class OrganizationBenchmark:
    """Policies and labels for one concrete generated organization."""

    policies: tuple[dict[str, Any], ...]
    entities: tuple[dict[str, Any], ...]
    attachments: tuple[dict[str, Any], ...]
    labels: tuple[dict[str, Any], ...]

    @property
    def label_map(self) -> dict[str, int]:
        return {row["policy_id"]: int(row["label"]) for row in self.labels}

    @property
    def label_rows(self) -> dict[str, dict[str, Any]]:
        return {row["policy_id"]: dict(row) for row in self.labels}


def _jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def load_organization(root: str | Path, org: str) -> OrganizationBenchmark:
    """Load and filter the approved local benchmark for one organization."""
    directory = Path(root)
    required = tuple(
        directory / name
        for name in ("policies.jsonl", "entities.jsonl", "attachments.jsonl", "labels.csv")
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "prepared benchmark is incomplete; missing files: " + ", ".join(missing)
        )
    policies = [row for row in _jsonl(directory / "policies.jsonl") if row.get("org") == org]
    entities = [row for row in _jsonl(directory / "entities.jsonl") if row.get("org") == org]
    attachments = [row for row in _jsonl(directory / "attachments.jsonl") if row.get("org") == org]
    with (directory / "labels.csv").open(newline="", encoding="utf-8") as handle:
        labels = [dict(row) for row in csv.DictReader(handle) if row.get("org") == org]
    if not policies or not labels:
        raise ValueError(f"benchmark contains no policy and label rows for organization {org!r}")
    if {row["policy_id"] for row in policies} != {row["policy_id"] for row in labels}:
        raise ValueError(f"policy and label IDs do not match for organization {org!r}")
    for row in labels:
        row["label"] = int(row["label"])
    return OrganizationBenchmark(
        tuple(policies), tuple(entities), tuple(attachments), tuple(labels)
    )


def node2vec_features(
    benchmark: OrganizationBenchmark, *, seed: int, dimensions: int = 128
) -> tuple[list[str], np.ndarray]:
    """Build leakage-safe Python Node2Vec features for one organization."""
    graph = build_policy_graph(
        benchmark.policies,
        entities=benchmark.entities,
        attachments=benchmark.attachments,
    )
    policy_ids = [policy["policy_id"] for policy in benchmark.policies]
    training_ids = [
        f"Policy:{policy_id.lower()}"
        for policy_id in policy_ids
        if benchmark.label_map[policy_id] == 0
    ]
    vectors, graph_policy_ids = embed_policy_nodes(
        graph,
        training_policy_ids=training_ids,
        config={"dimensions": dimensions},
        seed=seed,
    )
    graph_ids = [node_id.split(":", 1)[1] for node_id in graph_policy_ids]
    index_by_id = {policy_id: index for index, policy_id in enumerate(graph_ids)}
    indices = [index_by_id[policy_id.lower()] for policy_id in policy_ids]
    return policy_ids, vectors[indices]


def _labels(benchmark: OrganizationBenchmark) -> dict[str, int]:
    return benchmark.label_map


def run_configured_experiment(config: ExperimentConfig) -> list[Path]:
    """Execute the supported configured experiment protocols for all seeds."""
    outputs: list[Path] = []
    benchmarks = {org: load_organization(config.input_root, org) for org in config.orgs}
    for seed in config.seeds:
        if config.exp_id == "exp03":
            source = benchmarks[config.orgs[0]]
            source_ids, source_features = node2vec_features(source, seed=seed)
            for target_org in config.orgs[1:]:
                target = benchmarks[target_org]
                target_ids, target_features = node2vec_features(target, seed=seed)
                result = run_transfer_evaluation(
                    source_ids,
                    source_features,
                    _labels(source),
                    target_ids,
                    target_features,
                    _labels(target),
                    detector_params=config.detector_params,
                    validation_folds=config.split.validation_folds,
                    seed=seed,
                )
                output = config.output_root / config.exp_id / target_org / str(seed)
                rows = [
                    {
                        "policy_id": policy_id,
                        "score": float(score),
                        "pred": int(prediction),
                        "label": _labels(target)[policy_id],
                        "misconfig_type": target.label_rows[policy_id]["misconfig_type"],
                    }
                    for policy_id, score, prediction in zip(
                        result["test_ids"], result["scores"], result["predictions"], strict=True
                    )
                ]
                outputs.append(
                    write_run_artifacts(
                        output,
                        config={
                            "exp_id": config.exp_id,
                            "seed": seed,
                            "source_org": config.orgs[0],
                        },
                        metrics=result["metrics"],
                        predictions=rows,
                    )
                )
            continue
        for org in config.orgs:
            benchmark = benchmarks[org]
            policy_ids, embeddings = node2vec_features(benchmark, seed=seed)
            labels = _labels(benchmark)
            output_root = config.output_root / config.exp_id / org / str(seed)
            if config.exp_id == "exp01":
                outputs.extend(
                    run_detector_comparison(
                        policy_ids,
                        embeddings,
                        labels,
                        output_root,
                        detector_params=config.detector_params,
                        detector_grid=config.detector_grid,
                        validation_folds=config.split.validation_folds,
                        seed=seed,
                    ).values()
                )
            elif config.exp_id == "exp02":
                outputs.extend(
                    run_detector_comparison(
                        policy_ids, embeddings, labels, output_root / "node2vec",
                        detectors=(config.detector,),
                        detector_params={config.detector: config.detector_params},
                        validation_folds=config.split.validation_folds, seed=seed,
                        label_rows=benchmark.label_rows,
                    ).values()
                )
                outputs.extend(
                    run_baselines_for_org(config, benchmark, output_root, seed=seed).values()
                )
            elif config.exp_id == "exp04":
                outputs.extend(
                    run_contamination_for_org(config, benchmark, embeddings, output_root, seed=seed)
                )
            elif config.exp_id == "exp07":
                split = make_evaluation_split(
                    policy_ids, labels, validation_folds=config.split.validation_folds, seed=seed
                )
                train_ids = split.train_normal_ids
                train_policies = [
                    policy for policy in benchmark.policies if policy["policy_id"] in train_ids
                ]
                encoder = fit_bag_of_actions(train_policies)
                all_bag_features = transform_bag_of_actions(benchmark.policies, encoder)
                outputs.extend(
                    run_feature_ablation(
                        policy_ids,
                        {
                            "node2vec": embeddings,
                            "handcrafted_feature": handcrafted_features(benchmark.policies),
                            "bag_of_actions": all_bag_features,
                        },
                        labels,
                        output_root,
                        detector_params=config.detector_params,
                        validation_folds=config.split.validation_folds,
                        seed=seed,
                        label_rows=benchmark.label_rows,
                    ).values()
                )
            elif config.exp_id == "exp13":
                detector_outputs = run_detector_comparison(
                        policy_ids,
                        embeddings,
                        labels,
                        output_root,
                        detectors=(config.detector,),
                        detector_params={config.detector: config.detector_params},
                        validation_folds=config.split.validation_folds,
                        seed=seed,
                        label_rows=benchmark.label_rows,
                    )
                outputs.extend(detector_outputs.values())
                prediction_path = next(iter(detector_outputs.values())) / "preds.csv"
                with prediction_path.open(newline="", encoding="utf-8") as handle:
                    rows = list(csv.DictReader(handle))
                for row in rows:
                    row.update(
                        label=int(row["label"]),
                        pred=int(row["pred"]),
                        score=float(row["score"]),
                    )
                grouped = {
                    "operator": grouped_recall(rows, group_field="operator_id",
                        groups=[f"P{i}" for i in range(1, 4)] + [f"A{i}" for i in range(1, 4)],
                        bootstrap_replicates=config.bootstrap_replicates, seed=seed),
                    "difficulty": grouped_recall(rows, group_field="difficulty",
                        groups=["easy", "medium", "hard"],
                        bootstrap_replicates=config.bootstrap_replicates, seed=seed),
                }
                (output_root / "grouped_recall.json").write_text(
                    json.dumps(grouped, indent=2, sort_keys=True) + "\n", encoding="utf-8"
                )
    _write_cross_seed_summary(config, outputs)
    return outputs


def _write_cross_seed_summary(config: ExperimentConfig, outputs: list[Path]) -> None:
    summary_root = config.output_root / config.exp_id
    if (summary_root / "summary.json").exists() or (summary_root / "summary.csv").exists():
        raise FileExistsError(f"refusing to overwrite experiment summary: {summary_root}")
    grouped: dict[str, list[dict[str, Any]]] = {}
    for output in outputs:
        metrics_path = output / "metrics.json"
        if metrics_path.is_file():
            with metrics_path.open(encoding="utf-8") as handle:
                grouped.setdefault("/".join(output.parts[-3:-1]), []).append(json.load(handle))
    summaries = {
        key: aggregate_seed_metrics(rows, config.metrics)
        for key, rows in sorted(grouped.items())
    }
    summary_root.mkdir(parents=True, exist_ok=True)
    (summary_root / "summary.json").write_text(
        json.dumps(summaries, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    with (summary_root / "summary.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = ["method", "seed_count", *config.metrics, "tp", "fp", "fn", "tn"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for key, summary in summaries.items():
            row = {"method": key, "seed_count": summary["seed_count"]}
            row.update({metric: summary.get(metric) for metric in config.metrics})
            row.update(summary["confusion"])
            writer.writerow(row)


def run_baselines_for_org(
    config: ExperimentConfig,
    benchmark: OrganizationBenchmark,
    output_root: Path,
    *,
    seed: int,
) -> dict[str, Path]:
    """Run the configured Feature 6 baselines for one organization."""
    from .baselines import run_baseline_comparison

    names = tuple(method for method in config.methods if method != "node2vec")
    return run_baseline_comparison(
        benchmark.policies,
        benchmark.labels,
        output_root,
        baseline_names=names,
        detector_name=config.detector,
        detector_params=config.detector_params,
        validation_folds=config.split.validation_folds,
        seed=seed,
    )


def run_contamination_for_org(
    config: ExperimentConfig,
    benchmark: OrganizationBenchmark,
    embeddings: np.ndarray,
    output_root: Path,
    *,
    seed: int,
) -> list[Path]:
    """Run EXP-04 with a deterministic fixed-test/contamination partition."""
    policy_ids = [policy["policy_id"] for policy in benchmark.policies]
    positives = [policy_id for policy_id in policy_ids if benchmark.label_map[policy_id] == 1]
    pool = tuple(positives[: max(1, len(positives) // 2)])
    evaluation_ids = [policy_id for policy_id in policy_ids if policy_id not in pool]
    split = make_evaluation_split(
        evaluation_ids, {policy_id: benchmark.label_map[policy_id] for policy_id in evaluation_ids},
        test_fraction=config.split.test_fraction,
        validation_folds=config.split.validation_folds, seed=seed,
    )
    fixed_test = split.test_ids
    counts = tuple(max(1, len(pool) * 10 // 100) if level == "percent" else int(level)
                   for level in config.contamination_levels)
    results = run_contamination_evaluation(
        policy_ids,
        embeddings,
        benchmark.label_map,
        fixed_test_ids=fixed_test,
        contamination_pool=pool,
        contamination_counts=counts,
        detector_name=config.detector,
        detector_params=config.detector_params,
        validation_folds=config.split.validation_folds,
        seed=seed,
    )
    paths: list[Path] = []
    for count, result in results.items():
        rows = [
            {
                "policy_id": policy_id,
                "score": float(score),
                "pred": int(prediction),
                "label": benchmark.label_map[policy_id],
                "misconfig_type": benchmark.label_rows[policy_id]["misconfig_type"],
            }
            for policy_id, score, prediction in zip(
                result["test_ids"], result["scores"], result["predictions"], strict=True
            )
        ]
        paths.append(
            write_run_artifacts(
                output_root / f"contamination_{count}",
                config={"exp_id": config.exp_id, "seed": seed, "contamination": count},
                metrics=result["metrics"],
                predictions=rows,
            )
        )
    return paths
