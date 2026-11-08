"""Generate all analysis figures and tables from experiment run artifacts.

Usage:
    python scripts/generate_figures.py [--results-dir RESULTS_DIR] [--benchmark-dir BENCHMARK_DIR]
"""

from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Ensure src/ is importable when run directly.
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from misdet.eval.plots import (
    ablation_recall_bars,
    comparison_table,
    contamination_curves,
    dataset_stats_table,
    operator_recall_bars,
    pr_curves,
)

# Paper-vs-ours skeleton rows from the detailed plan Appendix D.
_PAPER_VS_OURS_ROWS = [
    {
        "result": "LOF best of 4 detectors",
        "paper_reports": "LOF best F1; OC-SVM higher AUC",
        "ours": "",
        "verdict": "",
        "likely_reason": "",
    },
    {
        "result": "Recall vs. rule-based",
        "paper_reports": "3.7 to 6.4x",
        "ours": "",
        "verdict": "",
        "likely_reason": "",
    },
    {
        "result": "n_neighbors=5 transfers",
        "paper_reports": "yes",
        "ours": "",
        "verdict": "",
        "likely_reason": "",
    },
    {
        "result": "LOF/Robust Cov. tolerant to contamination",
        "paper_reports": "yes",
        "ours": "",
        "verdict": "",
        "likely_reason": "",
    },
    {
        "result": "Incremental update speed-up",
        "paper_reports": "about 1091x",
        "ours": "",
        "verdict": "",
        "likely_reason": "",
    },
]


def _warn(msg: str) -> None:
    warnings.warn(msg, stacklevel=2)
    print(f"[SKIP] {msg}", file=sys.stderr)


def _save_fig(fig: plt.Figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, format="pdf", bbox_inches="tight")
    plt.close(fig)
    print(f"[OK]   {path}")


def _save_table(df: pd.DataFrame, stem: Path) -> None:
    stem.parent.mkdir(parents=True, exist_ok=True)
    csv_path = stem.with_suffix(".csv")
    df.to_csv(csv_path, index=False)
    print(f"[OK]   {csv_path}")
    tex_path = stem.with_suffix(".tex")
    _write_latex(df, tex_path)
    print(f"[OK]   {tex_path}")


def _write_latex(df: pd.DataFrame, path: Path) -> None:
    """Write a minimal LaTeX tabular without requiring tabulate."""
    cols = list(df.columns)
    col_spec = "l" + "r" * (len(cols) - 1)
    lines = [
        "\\begin{tabular}{" + col_spec + "}",
        "\\hline",
        " & ".join(str(c) for c in cols) + " \\\\",
        "\\hline",
    ]
    for _, row in df.iterrows():
        lines.append(" & ".join(str(v) if v is not None else "" for v in row) + " \\\\")
    lines += ["\\hline", "\\end{tabular}", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def generate(results_dir: Path, benchmark_dir: Path) -> None:
    figures_dir = results_dir / "figures"
    tables_dir = results_dir / "tables"

    # ------------------------------------------------------------------
    # T1 - Dataset statistics
    # ------------------------------------------------------------------
    labels_csv = benchmark_dir / "labels.csv"
    if labels_csv.is_file():
        df = dataset_stats_table(labels_csv)
        _save_table(df, tables_dir / "t1_dataset_stats")
    else:
        _warn(f"T1 skipped: {labels_csv} not found")

    # ------------------------------------------------------------------
    # T2 - Main comparison (exp02)
    # ------------------------------------------------------------------
    exp02_summary = results_dir / "exp02" / "summary.json"
    if exp02_summary.is_file():
        df = comparison_table(exp02_summary)
        _save_table(df, tables_dir / "t2_main_comparison")
    else:
        _warn(f"T2 skipped: {exp02_summary} not found")

    # ------------------------------------------------------------------
    # T3 - Detector comparison (exp01)
    # ------------------------------------------------------------------
    exp01_summary = results_dir / "exp01" / "summary.json"
    if exp01_summary.is_file():
        df = comparison_table(exp01_summary)
        _save_table(df, tables_dir / "t3_detector_comparison")
    else:
        _warn(f"T3 skipped: {exp01_summary} not found")

    # ------------------------------------------------------------------
    # T4 - Ablation (exp07)
    # ------------------------------------------------------------------
    exp07_summary = results_dir / "exp07" / "summary.json"
    if exp07_summary.is_file():
        df = comparison_table(exp07_summary)
        _save_table(df, tables_dir / "t4_ablation")
    else:
        _warn(f"T4 skipped: {exp07_summary} not found")

    # ------------------------------------------------------------------
    # T5 - Paper vs. Ours skeleton (always written)
    # ------------------------------------------------------------------
    t5_path = tables_dir / "t5_paper_vs_ours.csv"
    tables_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(_PAPER_VS_OURS_ROWS).to_csv(t5_path, index=False)
    print(f"[OK]   {t5_path}")

    # ------------------------------------------------------------------
    # T6 - Per-operator and per-difficulty recall (exp13)
    # ------------------------------------------------------------------
    exp13_dir = results_dir / "exp13"
    grouped_recall_files = (
        sorted(exp13_dir.glob("**/grouped_recall.json")) if exp13_dir.is_dir() else []
    )
    if grouped_recall_files:
        # Use the first available file (single-seed smoke) or aggregate across seeds.
        all_operator_rows: list[dict] = []
        all_difficulty_rows: list[dict] = []
        import json
        for grp_path in grouped_recall_files:
            data = json.loads(grp_path.read_text(encoding="utf-8"))
            all_operator_rows.extend(data.get("operator", []))
            all_difficulty_rows.extend(data.get("difficulty", []))

        def _aggregate_groups(rows: list[dict]) -> pd.DataFrame:
            import numpy as np
            result = []
            groups: dict[str, list] = {}
            for row in rows:
                groups.setdefault(row["group"], []).append(row.get("recall") or 0.0)
            for group, recalls in groups.items():
                result.append(
                    {
                        "group": group,
                        "recall_mean": float(np.mean(recalls)),
                        "recall_sd": float(np.std(recalls, ddof=0)),
                    }
                )
            return pd.DataFrame(result)

        df_op = _aggregate_groups(all_operator_rows)
        df_diff = _aggregate_groups(all_difficulty_rows)
        df_t6 = pd.concat(
            [df_op.assign(dimension="operator"), df_diff.assign(dimension="difficulty")],
            ignore_index=True,
        )
        _save_table(df_t6, tables_dir / "t6_per_operator_recall")

        # F4 - operator recall bars (use first grouped_recall.json)
        try:
            fig, _ = operator_recall_bars(grouped_recall_files[0])
            _save_fig(fig, figures_dir / "fig4_operator_recall.pdf")
        except Exception as exc:
            _warn(f"F4 skipped: {exc}")
    else:
        _warn(f"T6/F4 skipped: no grouped_recall.json found under {exp13_dir}")

    # ------------------------------------------------------------------
    # F5 - PR curves (exp02 run dirs)
    # ------------------------------------------------------------------
    exp02_dir = results_dir / "exp02"
    if exp02_dir.is_dir():
        run_dirs = [p.parent for p in exp02_dir.glob("**/preds.csv")]
        if run_dirs:
            try:
                fig, _ = pr_curves(run_dirs)
                _save_fig(fig, figures_dir / "fig5_pr_curves.pdf")
            except Exception as exc:
                _warn(f"F5 skipped: {exc}")
        else:
            _warn(f"F5 skipped: no preds.csv found under {exp02_dir}")
    else:
        _warn(f"F5 skipped: {exp02_dir} not found")

    # ------------------------------------------------------------------
    # F6 - Ablation recall bars (exp07)
    # ------------------------------------------------------------------
    if exp07_summary.is_file():
        try:
            fig, _ = ablation_recall_bars(exp07_summary)
            _save_fig(fig, figures_dir / "fig6_ablation_recall.pdf")
        except Exception as exc:
            _warn(f"F6 skipped: {exc}")
    else:
        _warn(f"F6 skipped: {exp07_summary} not found")

    # ------------------------------------------------------------------
    # F7 - Contamination curves (exp04)
    # ------------------------------------------------------------------
    exp04_summary = results_dir / "exp04" / "summary.json"
    if exp04_summary.is_file():
        try:
            fig, _ = contamination_curves(exp04_summary)
            _save_fig(fig, figures_dir / "fig7_contamination_curves.pdf")
        except Exception as exc:
            _warn(f"F7 skipped: {exc}")
    else:
        _warn(f"F7 skipped: {exp04_summary} not found")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate analysis figures and tables.")
    parser.add_argument("--results-dir", default="results", type=Path)
    parser.add_argument("--benchmark-dir", default="data/benchmark", type=Path)
    args = parser.parse_args()
    generate(args.results_dir, args.benchmark_dir)


if __name__ == "__main__":
    main()
