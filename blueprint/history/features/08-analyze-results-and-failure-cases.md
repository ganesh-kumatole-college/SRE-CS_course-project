# Feature: Analyze Results and Failure Cases

**From build-plan:** feature 8
**Build attempt:** 1
**Status:** verified
**Branch:** feature/analyze-results-and-failure-cases

<!-- Archive annotation -->
<!-- Spec SHA-256: 730fe50b18839bae2af8adb883f8cb3af06e21d71dc9648e58b98c3b82043afa -->
<!-- Spec bytes: 11732 -->
<!-- Original HEAD: 6243dae5f7ae5012bbf2cdf4b82ea6bf0d5248e6 -->
<!-- Local base (main): 3d8e258b2b38996bbf6e6a19f7d559319ae4a771 -->

## Goal

Convert the experiment run artifacts already in `results/` into a
claims-to-evidence record, per-operator and per-difficulty failure analysis,
paper-comparison verdicts, and reproducible figures and tables that the paper
can cite directly. No new experiment protocols are introduced; this feature
reads existing `summary.json`, `summary.csv`, `preds.csv`, and
`grouped_recall.json` files and writes outputs under `results/figures/`,
`results/tables/`, and `docs/claims.md`.

## What was built

- `src/misdet/eval/plots.py` — 7 pure functions: `operator_recall_bars`,
  `pr_curves`, `ablation_recall_bars`, `contamination_curves`,
  `dataset_stats_table`, `comparison_table`, `top_errors`. Colour-blind-safe
  palette, no `plt.show()` calls, no side effects.
- `scripts/generate_figures.py` — CLI (`--results-dir`, `--benchmark-dir`);
  writes F4–F7 PDFs and T1–T6 CSV+LaTeX; skips gracefully on missing data.
- `Makefile` — `figures` and `tables` targets added to `.PHONY`.
- `docs/claims.md` — skeleton claims-to-evidence table with 5 required rows.
- `tests/test_plots.py` — 15 tests covering all 7 functions, edge cases
  (empty input, null CI, single-class PR curve, missing preds.csv).

## Verify

`make test && make lint` — 107 passed, 0 lint errors.

`python scripts/generate_figures.py --results-dir results/smoke` — all 15
outputs written without error.

## Findings

### 8/F-01 [P2] open — GDS resource cleanup is not asserted by tests

**File:** tests/test_embed.py:156,217
**Found:** 2026-11-04 by /audit (scope: current; lens: quality, security, performance, tests)
**Why it matters:** The feature requires temporary GDS graph and Neo4j data to
be cleaned up on both success and failure. The GDS tests assert result mapping,
failure propagation, and driver closure, but do not assert that the graph-drop
and node-delete cleanup queries ran. A cleanup regression could therefore pass
the current unit tests and leave temporary resources behind.
**Suggested fix:** Assert that the fake session observed both cleanup queries
after successful embedding and after a post-projection failure.
**Resolution:** Carried forward — open at completion of feature 8. Originated
in feature 4 (embed policy nodes with Node2Vec); not in scope for this feature.

## Try it now

Generate all tables and figures from smoke results:

```bash
make figures
# or specifically for smoke results:
python scripts/generate_figures.py --results-dir results/smoke
```

Inspect generated figures in `results/smoke/figures/` (e.g. `fig4_operator_recall.pdf`, `fig5_pr_curves.pdf`) and tables in `results/smoke/tables/` (e.g. `t1_dataset_stats.csv`, `t2_main_comparison.csv`).

