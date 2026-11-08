# Findings

> **Generated file.** The findings ledger: review findings raised by `/audit`
> against the work in progress, each with a durable ID, severity (P0-P3), and
> status. `/implement` marks repaired findings `fixed`, a later `/audit` pass
> moves them to `closed`, and `/complete` refuses to land while any P0 or P1
> finding is `open` or `fixed`, then archives resolved findings with the work
> and resets this file.

### F-01 [P2] open - GDS resource cleanup is not asserted by tests

**File:** tests/test_embed.py:156,217
**Found:** 2026-11-04 by /audit (scope: current; lens: quality, security, performance, tests)
**Why it matters:** The feature requires temporary GDS graph and Neo4j data to be cleaned up on both success and failure. The GDS tests assert result mapping, failure propagation, and driver closure, but do not assert that the graph-drop and node-delete cleanup queries ran. A cleanup regression could therefore pass the current unit tests and leave temporary resources behind.
**Suggested fix:** Assert that the fake session observed both cleanup queries after successful embedding and after a post-projection failure.
**Resolution:**

### F-02 [P1] closed - EXP-01 ignores its detector grid and configured parameters

**File:** src/misdet/experiments/runner.py:163
**Found:** 2026-11-08 by /audit (scope: current; lens: quality, security, performance, tests)
**Why it matters:** The EXP-01 configuration declares detector-specific candidate grids and the feature contract requires validation-only tuning. The runner passes the flat `detector_params` mapping to `run_detector_comparison`, which expects a mapping keyed by detector name, and never reads `detector_grid` or calls `select_detector_params`. Consequently EXP-01 runs default detector settings instead of the configured candidates and does not perform the required validation-only selection, so its reported comparison does not implement the experiment it claims to run.
**Suggested fix:** Wire `detector_grid` into an explicit validation-only selection path for each detector, or remove the unused grid only if the EXP-01 requirement is explicitly reduced. Preserve the locked test split and ensure selected parameters are recorded in each run artifact.
**Resolution:** Closed by independent review on 2026-11-08. EXP-01 now selects
configured candidates from a training-normal validation fold, refits the
selected parameters on the full training-normal pool, and records tuning
metadata in the run artifact. The configured runner passes `detector_grid`
through to this path; the focused protocol tests and full test suite pass.

### F-03 [P1] closed - EXP-04 bypasses its configured split and contamination levels

**File:** src/misdet/experiments/runner.py:258
**Found:** 2026-11-08 by /audit (scope: current; lens: quality, security, performance, tests)
**Why it matters:** The EXP-04 runner ignores the configured `paper_90_10`
split and `contamination_levels`. It constructs a test set from the first 80%
of positive IDs only, omitting the locked normal test rows, and hard-codes
`(0, 1, 5, 10)` instead of resolving the configured levels, including the
percentage level. The resulting experiment does not implement the declared
fixed-test contamination protocol and can reject valid small contamination
pools at level 10.
**Suggested fix:** Derive one deterministic locked test set from the configured
split, keep its normal and misconfiguration IDs fixed for every level, resolve
all configured absolute and percentage contamination levels, and validate the
available contamination pool before execution.
**Resolution:** Closed by /audit on 2026-11-08. `run_contamination_for_org` now sorts positives deterministically, reserves the first half as the contamination pool before calling `make_evaluation_split`, and derives the locked test from the remaining policies (normals + remaining positives). `"percent"` resolves against the actual pool size; absolute counts exceeding the pool raise a clear error. Three regression tests cover fixed-test identity across levels, percent resolution, and pool-overflow rejection. 92 tests pass, lint clean.

### F-04 [P1] closed - EXP-13 dispatch never produces grouped recall results

**File:** src/misdet/experiments/runner.py:210
**Found:** 2026-11-08 by /audit (scope: current; lens: quality, security, performance, tests)
**Why it matters:** The EXP-13 dispatch calls `run_detector_comparison` and
persists ordinary detector-run artifacts, but never calls the implemented
`grouped_recall` aggregation or writes operator/difficulty group summaries.
Thus the configured experiment omits its required recall-by-operator and
recall-by-difficulty outputs, including explicit empty/undefined groups.
**Suggested fix:** Load each run's predictions, invoke `grouped_recall` for the
configured P1-A3 and easy/medium/hard groups, and persist the grouped rows with
counts and seeded intervals alongside the run summary.
**Resolution:** Closed by independent review on 2026-11-08. The EXP-13 dispatch reads detector predictions, calls `grouped_recall` for P1–P3/A1–A3 and easy/medium/hard, and writes `grouped_recall.json` with counts and null values for empty groups.

### F-05 [P1] closed - EXP-02 omits the configured Node2Vec comparison

**File:** src/misdet/experiments/runner.py:237
**Found:** 2026-11-08 by /audit (scope: current; lens: quality, security, performance, tests)
**Why it matters:** EXP-02 declares `node2vec` plus the baseline methods, but
`run_baselines_for_org` removes `node2vec` before calling
`run_baseline_comparison`. The configured experiment therefore emits only the
baselines and does not compare the main graph detector against them as required.
**Suggested fix:** Add the Node2Vec detector path to the EXP-02 dispatch using
the same split, threshold, artifact, and metric contracts as the baseline runs,
while retaining the existing baseline-only adapter for the other methods.
**Resolution:** Closed by independent review on 2026-11-08. The EXP-02 dispatch writes a Node2Vec detector run and the configured baseline runs using the same seed-derived split.

### F-06 [P1] closed - Experiment runner does not generate valid cross-seed summaries

**File:** src/misdet/experiments/runner.py:102
**Found:** 2026-11-08 by /audit (scope: current; lens: quality, security, performance, tests)
**Why it matters:** Feature 07 requires every experiment to produce machine-readable aggregate summaries with mean and standard deviation across the 30 seeds, seeded 95% bootstrap intervals over policies, and raw TP/FP/FN/TN counts. The runner writes only per-seed run directories. `aggregate_seed_metrics` and `grouped_recall` exist as isolated helpers, but no dispatch path reads the per-seed metrics or writes the required experiment-level summaries, so `make run-exp` cannot produce the required evidence for EXP-01 through EXP-04 and EXP-07.
**Suggested fix:** After all configured seed runs complete, load their recorded metrics and predictions, call the existing aggregation helpers (or a focused equivalent), and write deterministic CSV/JSON summaries under the configured results path, including configured bootstrap intervals and raw confusion counts. Preserve the existing no-overwrite behavior.
**Resolution:** Closed by /audit on 2026-11-08. `_write_cross_seed_summary` now groups by `output.relative_to(summary_root).parts` with the seed component (index 1) dropped, so all seeds for a method aggregate into one row. It pools `preds.csv` rows across seeds and computes seeded 95% bootstrap recall intervals written as `bootstrap_recall_ci` in `summary.json`. Three regression tests cover aggregation correctness, CI presence, and absence of seed components in keys. Smoke outputs for all 6 experiments verified correct.
