"""Pure analysis functions that produce matplotlib Figures and pandas DataFrames."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import precision_recall_curve

matplotlib.use("Agg")

_PALETTE = [
    "#0072B2",
    "#E69F00",
    "#009E73",
    "#CC79A7",
    "#56B4E9",
    "#D55E00",
    "#F0E442",
    "#000000",
]


def _load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _load_csv(path: str | Path) -> pd.DataFrame:
    return pd.read_csv(Path(path))


def dataset_stats_table(labels_csv_path: str | Path) -> pd.DataFrame:
    """Return per-org policy counts and misconfig prevalence from labels.csv."""
    df = _load_csv(labels_csv_path)
    rows = []
    for org, group in df.groupby("org"):
        total = len(group)
        misconfig = int((group["label"].astype(int) == 1).sum())
        normal = total - misconfig
        rows.append(
            {
                "org": org,
                "total": total,
                "normal": normal,
                "misconfig": misconfig,
                "prevalence_pct": round(100.0 * misconfig / total, 2) if total else 0.0,
            }
        )
    return pd.DataFrame(rows, columns=["org", "total", "normal", "misconfig", "prevalence_pct"])


def comparison_table(summary_json_path: str | Path) -> pd.DataFrame:
    """Return a tidy comparison DataFrame from a summary.json file."""
    data = _load_json(summary_json_path)
    rows = []
    for method, summary in data.items():
        row: dict[str, Any] = {"method": method}
        for metric in ("precision", "recall", "f1", "pr_auc", "roc_auc"):
            entry = summary.get(metric)
            row[metric] = entry["mean"] if isinstance(entry, dict) else None
        confusion = summary.get("confusion", {})
        for key in ("tp", "fp", "fn", "tn"):
            row[key] = confusion.get(key)
        rows.append(row)
    cols = ["method", "precision", "recall", "f1", "pr_auc", "roc_auc", "tp", "fp", "fn", "tn"]
    return pd.DataFrame(rows, columns=cols)


def operator_recall_bars(grouped_recall_path: str | Path) -> tuple[plt.Figure, pd.DataFrame]:
    """Bar chart of per-operator recall with 95% CI error bars."""
    data = _load_json(grouped_recall_path)
    operator_rows = data.get("operator", [])
    rows = []
    for entry in operator_rows:
        ci = entry.get("bootstrap_ci") or [None, None]
        recall = entry.get("recall")
        rows.append(
            {
                "group": entry["group"],
                "recall": recall if recall is not None else 0.0,
                "ci_lo": ci[0] if ci[0] is not None else 0.0,
                "ci_hi": ci[1] if ci[1] is not None else 0.0,
                "positive_count": entry.get("positive_count", 0),
            }
        )
    df = pd.DataFrame(rows)
    fig, ax = plt.subplots(figsize=(7, 4))
    if not df.empty:
        x = np.arange(len(df))
        recalls = df["recall"].to_numpy(dtype=float)
        yerr_lo = np.clip(recalls - df["ci_lo"].to_numpy(dtype=float), 0, None)
        yerr_hi = np.clip(df["ci_hi"].to_numpy(dtype=float) - recalls, 0, None)
        ax.bar(
            x, recalls, color=_PALETTE[0],
            yerr=[yerr_lo, yerr_hi], capsize=4, error_kw={"elinewidth": 1},
        )
        ax.set_xticks(x)
        ax.set_xticklabels(df["group"].tolist(), rotation=0)
    ax.set_ylim(0, 1.05)
    ax.set_xlabel("Operator")
    ax.set_ylabel("Recall")
    ax.set_title("Per-operator recall with 95% CI")
    fig.tight_layout()
    return fig, df


def pr_curves(run_dirs: list[Path | str]) -> tuple[plt.Figure, pd.DataFrame]:
    """Precision-recall curves for a list of run directories containing preds.csv."""
    fig, ax = plt.subplots(figsize=(6, 5))
    all_rows: list[dict[str, Any]] = []
    for i, run_dir in enumerate(run_dirs):
        preds_path = Path(run_dir) / "preds.csv"
        if not preds_path.is_file():
            continue
        df = _load_csv(preds_path)
        if "label" not in df.columns or "score" not in df.columns:
            continue
        labels = df["label"].astype(int).to_numpy()
        scores = df["score"].astype(float).to_numpy()
        if len(np.unique(labels)) < 2:
            continue
        precision, recall, thresholds = precision_recall_curve(labels, scores)
        method = Path(run_dir).name
        color = _PALETTE[i % len(_PALETTE)]
        ax.plot(recall, precision, label=method, color=color)
        for p, r, t in zip(precision[:-1], recall[:-1], thresholds, strict=False):
            all_rows.append(
                {"method": method, "threshold": float(t), "precision": float(p), "recall": float(r)}
            )
    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.set_title("Precision-Recall curves")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.05)
    if all_rows:
        ax.legend(fontsize=8)
    fig.tight_layout()
    return fig, pd.DataFrame(all_rows, columns=["method", "threshold", "precision", "recall"])


def ablation_recall_bars(summary_json_path: str | Path) -> tuple[plt.Figure, pd.DataFrame]:
    """Bar chart comparing recall across feature representations from exp07 summary.json."""
    data = _load_json(summary_json_path)
    rows = []
    for method, summary in data.items():
        entry = summary.get("recall")
        rows.append(
            {
                "method": method,
                "recall_mean": entry["mean"] if isinstance(entry, dict) else 0.0,
                "recall_sd": entry["sd"] if isinstance(entry, dict) else 0.0,
            }
        )
    df = pd.DataFrame(rows, columns=["method", "recall_mean", "recall_sd"])
    fig, ax = plt.subplots(figsize=(7, 4))
    if not df.empty:
        x = np.arange(len(df))
        ax.bar(
            x, df["recall_mean"], yerr=df["recall_sd"],
            color=_PALETTE[: len(df)], capsize=4, error_kw={"elinewidth": 1},
        )
        ax.set_xticks(x)
        labels = [m.split("/")[-1] for m in df["method"].tolist()]
        ax.set_xticklabels(labels, rotation=15, ha="right")
    ax.set_ylim(0, 1.05)
    ax.set_xlabel("Method")
    ax.set_ylabel("Recall (mean +/- sd)")
    ax.set_title("Ablation: recall by feature representation")
    fig.tight_layout()
    return fig, df


def contamination_curves(summary_json_path: str | Path) -> tuple[plt.Figure, pd.DataFrame]:
    """Line chart of recall vs. contamination count from exp04 summary.json."""
    data = _load_json(summary_json_path)
    # Keys look like "alpha/contamination_0" or "alpha/contamination_1".
    rows = []
    for key, summary in data.items():
        parts = key.split("/")
        contamination_part = parts[-1] if parts else key
        try:
            count = int(contamination_part.split("_")[-1])
        except ValueError:
            count = 0
        method = "/".join(parts[:-1]) if len(parts) > 1 else key
        entry = summary.get("recall")
        rows.append(
            {
                "contamination": count,
                "method": method,
                "recall_mean": entry["mean"] if isinstance(entry, dict) else 0.0,
            }
        )
    df = pd.DataFrame(rows, columns=["contamination", "method", "recall_mean"])
    fig, ax = plt.subplots(figsize=(6, 4))
    for i, (method, group) in enumerate(df.groupby("method")):
        group_sorted = group.sort_values("contamination")
        ax.plot(
            group_sorted["contamination"], group_sorted["recall_mean"],
            marker="o", label=method, color=_PALETTE[i % len(_PALETTE)],
        )
    ax.set_xlabel("Contamination count")
    ax.set_ylabel("Recall")
    ax.set_title("Recall vs. training contamination")
    if not df.empty:
        ax.legend(fontsize=8)
    fig.tight_layout()
    return fig, df


def top_errors(preds_csv_path: str | Path, n: int = 10) -> pd.DataFrame:
    """Return the top-n false positives and top-n false negatives by anomaly score."""
    df = _load_csv(preds_csv_path)
    df["label"] = df["label"].astype(int)
    df["pred"] = df["pred"].astype(int)
    df["score"] = df["score"].astype(float)
    fp = df[(df["label"] == 0) & (df["pred"] == 1)].sort_values("score", ascending=False).head(n)
    fn = df[(df["label"] == 1) & (df["pred"] == 0)].sort_values("score", ascending=False).head(n)
    result = pd.concat([fp, fn], ignore_index=True)
    return result
