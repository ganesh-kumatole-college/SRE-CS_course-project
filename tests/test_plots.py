"""Tests for misdet.eval.plots."""

from __future__ import annotations

import json
import textwrap

import matplotlib
import matplotlib.pyplot as plt

matplotlib.use("Agg")

from misdet.eval.plots import (  # noqa: E402
    ablation_recall_bars,  # noqa: E402
    comparison_table,  # noqa: E402
    contamination_curves,  # noqa: E402
    dataset_stats_table,  # noqa: E402
    operator_recall_bars,  # noqa: E402
    pr_curves,  # noqa: E402
    top_errors,  # noqa: E402
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MINIMAL_LABELS_CSV = textwrap.dedent("""\
    policy_id,org,label,misconfig_type,operator_id,difficulty,hard_negative
    p1,alpha,0,none,,none,0
    p2,alpha,1,permissive,P1,easy,0
    p3,beta,0,none,,none,0
""")

MINIMAL_SUMMARY_JSON = {
    "alpha/lof": {
        "precision": {"mean": 0.9, "sd": 0.05, "count": 1},
        "recall": {"mean": 0.5, "sd": 0.1, "count": 1},
        "f1": {"mean": 0.65, "sd": 0.05, "count": 1},
        "pr_auc": {"mean": 0.8, "sd": 0.0, "count": 1},
        "roc_auc": {"mean": 0.85, "sd": 0.0, "count": 1},
        "confusion": {"tp": 15, "fp": 1, "fn": 15, "tn": 34},
    },
    "alpha/wildcard": {
        "precision": {"mean": 0.46, "sd": 0.0, "count": 1},
        "recall": {"mean": 1.0, "sd": 0.0, "count": 1},
        "f1": {"mean": 0.63, "sd": 0.0, "count": 1},
        "pr_auc": {"mean": 0.46, "sd": 0.0, "count": 1},
        "roc_auc": {"mean": 0.5, "sd": 0.0, "count": 1},
        "confusion": {"tp": 30, "fp": 35, "fn": 0, "tn": 0},
    },
}

MINIMAL_GROUPED_RECALL = {
    "operator": [
        {
            "group": "P1", "count": 10, "positive_count": 5,
            "recall": 0.8, "bootstrap_ci": [0.6, 1.0],
        },
        {
            "group": "P2", "count": 0, "positive_count": 0,
            "recall": None, "bootstrap_ci": None,
        },
    ],
    "difficulty": [
        {
            "group": "easy", "count": 10, "positive_count": 5,
            "recall": 0.9, "bootstrap_ci": [0.7, 1.0],
        },
    ],
}

MINIMAL_PREDS_CSV = textwrap.dedent("""\
    policy_id,score,pred,label,misconfig_type
    p1,0.9,1,0,none
    p2,0.8,1,0,none
    p3,0.7,0,1,permissive
    p4,0.6,0,1,permissive
    p5,0.3,0,0,none
    p6,0.2,1,1,permissive
""")


# ---------------------------------------------------------------------------
# dataset_stats_table
# ---------------------------------------------------------------------------

def test_dataset_stats_table_columns(tmp_path):
    csv_path = tmp_path / "labels.csv"
    csv_path.write_text(MINIMAL_LABELS_CSV, encoding="utf-8")
    df = dataset_stats_table(csv_path)
    assert list(df.columns) == ["org", "total", "normal", "misconfig", "prevalence_pct"]
    assert set(df["org"]) == {"alpha", "beta"}
    alpha = df[df["org"] == "alpha"].iloc[0]
    assert alpha["total"] == 2
    assert alpha["misconfig"] == 1
    assert alpha["normal"] == 1


def test_dataset_stats_table_single_org(tmp_path):
    csv_path = tmp_path / "labels.csv"
    csv_path.write_text("policy_id,org,label\np1,alpha,0\n", encoding="utf-8")
    df = dataset_stats_table(csv_path)
    assert len(df) == 1
    assert df.iloc[0]["prevalence_pct"] == 0.0


# ---------------------------------------------------------------------------
# comparison_table
# ---------------------------------------------------------------------------

def test_comparison_table_columns(tmp_path):
    path = tmp_path / "summary.json"
    path.write_text(json.dumps(MINIMAL_SUMMARY_JSON), encoding="utf-8")
    df = comparison_table(path)
    expected_cols = [
        "method", "precision", "recall", "f1", "pr_auc", "roc_auc", "tp", "fp", "fn", "tn"
    ]
    assert list(df.columns) == expected_cols
    assert len(df) == 2
    lof_row = df[df["method"] == "alpha/lof"].iloc[0]
    assert abs(lof_row["precision"] - 0.9) < 1e-9


def test_comparison_table_missing_metric(tmp_path):
    data = {"alpha/lof": {"confusion": {"tp": 1, "fp": 0, "fn": 0, "tn": 1}}}
    path = tmp_path / "summary.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    df = comparison_table(path)
    assert df.iloc[0]["precision"] is None


# ---------------------------------------------------------------------------
# operator_recall_bars
# ---------------------------------------------------------------------------

def test_operator_recall_bars_returns_figure_and_df(tmp_path):
    path = tmp_path / "grouped_recall.json"
    path.write_text(json.dumps(MINIMAL_GROUPED_RECALL), encoding="utf-8")
    fig, df = operator_recall_bars(path)
    assert isinstance(fig, plt.Figure)
    assert "group" in df.columns
    assert "recall" in df.columns
    assert len(df) == 2
    plt.close(fig)


def test_operator_recall_bars_null_ci(tmp_path):
    data = {
        "operator": [
            {"group": "P1", "count": 0, "positive_count": 0, "recall": None, "bootstrap_ci": None}
        ],
        "difficulty": [],
    }
    path = tmp_path / "grouped_recall.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    fig, df = operator_recall_bars(path)
    assert df.iloc[0]["recall"] == 0.0
    plt.close(fig)


# ---------------------------------------------------------------------------
# ablation_recall_bars
# ---------------------------------------------------------------------------

def test_ablation_recall_bars_columns(tmp_path):
    path = tmp_path / "summary.json"
    path.write_text(json.dumps(MINIMAL_SUMMARY_JSON), encoding="utf-8")
    fig, df = ablation_recall_bars(path)
    assert isinstance(fig, plt.Figure)
    assert list(df.columns) == ["method", "recall_mean", "recall_sd"]
    assert len(df) == 2
    plt.close(fig)


def test_ablation_recall_bars_empty(tmp_path):
    path = tmp_path / "summary.json"
    path.write_text("{}", encoding="utf-8")
    fig, df = ablation_recall_bars(path)
    assert df.empty
    plt.close(fig)


# ---------------------------------------------------------------------------
# contamination_curves
# ---------------------------------------------------------------------------

def test_contamination_curves_columns(tmp_path):
    data = {
        "alpha/contamination_0": {
            "recall": {"mean": 0.3, "sd": 0.0, "count": 1},
            "confusion": {"tp": 3, "fp": 0, "fn": 7, "tn": 10},
        },
        "alpha/contamination_1": {
            "recall": {"mean": 0.5, "sd": 0.0, "count": 1},
            "confusion": {"tp": 5, "fp": 0, "fn": 5, "tn": 10},
        },
    }
    path = tmp_path / "summary.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    fig, df = contamination_curves(path)
    assert isinstance(fig, plt.Figure)
    assert list(df.columns) == ["contamination", "method", "recall_mean"]
    assert set(df["contamination"]) == {0, 1}
    plt.close(fig)


# ---------------------------------------------------------------------------
# top_errors
# ---------------------------------------------------------------------------

def test_top_errors_returns_fp_and_fn(tmp_path):
    path = tmp_path / "preds.csv"
    path.write_text(MINIMAL_PREDS_CSV, encoding="utf-8")
    df = top_errors(path, n=10)
    # p1, p2 are FP; p3, p4 are FN
    assert set(df["policy_id"]).issuperset({"p1", "p2", "p3", "p4"})


def test_top_errors_respects_n(tmp_path):
    path = tmp_path / "preds.csv"
    path.write_text(MINIMAL_PREDS_CSV, encoding="utf-8")
    df = top_errors(path, n=1)
    # At most 1 FP + 1 FN = 2 rows
    assert len(df) <= 2


def test_top_errors_empty_when_no_errors(tmp_path):
    csv = "policy_id,score,pred,label,misconfig_type\np1,0.9,1,1,permissive\np2,0.1,0,0,none\n"
    path = tmp_path / "preds.csv"
    path.write_text(csv, encoding="utf-8")
    df = top_errors(path)
    assert df.empty


# ---------------------------------------------------------------------------
# pr_curves
# ---------------------------------------------------------------------------

def test_pr_curves_single_run(tmp_path):
    run_dir = tmp_path / "lof"
    run_dir.mkdir()
    (run_dir / "preds.csv").write_text(MINIMAL_PREDS_CSV, encoding="utf-8")
    fig, df = pr_curves([run_dir])
    assert isinstance(fig, plt.Figure)
    assert list(df.columns) == ["method", "threshold", "precision", "recall"]
    assert len(df) > 0
    plt.close(fig)


def test_pr_curves_missing_preds(tmp_path):
    run_dir = tmp_path / "empty_run"
    run_dir.mkdir()
    fig, df = pr_curves([run_dir])
    assert df.empty
    plt.close(fig)


def test_pr_curves_single_class_skipped(tmp_path):
    run_dir = tmp_path / "all_normal"
    run_dir.mkdir()
    csv = "policy_id,score,pred,label,misconfig_type\np1,0.9,1,0,none\np2,0.1,0,0,none\n"
    (run_dir / "preds.csv").write_text(csv, encoding="utf-8")
    fig, df = pr_curves([run_dir])
    assert df.empty
    plt.close(fig)
