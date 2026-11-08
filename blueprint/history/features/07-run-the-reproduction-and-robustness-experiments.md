# Feature: Run the reproduction and robustness experiments

**From build-plan:** feature 7
**Build attempt:** 1
**Branch:** refs/heads/feature/run-the-reproduction-and-robustness-experiments
**Status:** verified

## Goal

Add a configuration-driven experiment layer that runs the Phase 9 MUST
experiments over the existing leakage-safe graph, embedding, detector, and
baseline APIs. It must reproduce the paper-style comparisons where the open
synthetic benchmark permits, compare Node2Vec with non-graph baselines, and
report robust per-type and per-difficulty results without using the locked test
split for fitting, tuning, thresholding, or embedding selection.

The feature covers EXP-01, EXP-02, EXP-03, EXP-04, EXP-07, and EXP-13. Every
randomized experiment uses seeds 0 through 29, writes independently inspectable
run artifacts, preserves raw confusion counts, and produces deterministic
aggregate summaries for the same inputs and Git revision.

## In scope

- Define one YAML configuration for each MUST experiment under
  `configs/experiments/`.
- Add a shared experiment runner/orchestration layer that resolves one
  experiment configuration, derives seed-specific child runs, refuses to
  overwrite existing runs, and records the resolved configuration and input
  metadata.
- Implement the following experiment protocols:
  - EXP-01: compare LOF, One-Class SVM, Isolation Forest, and Robust
    Covariance on S1 with validation-only tuning and the existing calibrated
    threshold protocol.
  - EXP-02: compare the main detector with random/prevalence, wildcard,
    permissiveness, hand-crafted-feature, bag-of-actions, and the existing
    clearly-labelled offline Cloud Custodian-equivalent baseline on S1, S2,
    and S3 using matching splits.
  - EXP-03: tune on S1 and transfer the resolved detector configuration to S2
    and S3, including cross-organization evaluation and reporting variants
    with and without shared managed policies when the input metadata supports
    that distinction.
  - EXP-04: contaminate training with 0, 1, 5, 10, and percentage-based
    misconfiguration samples while keeping one fixed misconfiguration test set
    for every detector and contamination level.
  - EXP-07: compare Node2Vec plus LOF, hand-crafted features plus LOF, and
    bag-of-actions plus LOF on identical organizations, splits, thresholds,
    and seeds.
  - EXP-13: report recall by injection operator P1 through A3 and by
    easy/medium/hard difficulty, with undefined groups represented explicitly.
- The repository's generated benchmark uses organization IDs `alpha`, `beta`,
  and `gamma`; these are the concrete local equivalents of the detailed plan's
  S1, S2, and S3 labels.
- Add the bag-of-actions representation required by EXP-02 and EXP-07 if it is
  not already present in the baseline layer. It must be derived from policy
  documents without labels and use the same detector/evaluation interface.
- Aggregate each experiment into machine-readable CSV/JSON summaries with
  mean and standard deviation across seeds, seeded 95% bootstrap intervals
  over policies, paired seed-level comparison inputs where applicable, and raw
  TP/FP/FN/TN counts.
- Add focused tests for configuration validation, seed expansion, identical
  split reuse, fixed-test contamination handling, aggregate calculations,
  operator/difficulty grouping, idempotent output refusal, and leakage guards.
- Add `make run-exp` support for one named experiment and a reproducible
  command path for regenerating the experiment summaries.
- Record the implementation decision and observed execution details in
  `docs/experiment_log.md`; generated metrics must come from scripts rather
  than hand-edited documents.

## Out of scope

- New graph schemas, embedding algorithms, detector algorithms, or changes to
  the locked split and threshold semantics already established by Features 4
  through 6.
- EXP-05, EXP-06, EXP-08, EXP-09, EXP-10, EXP-11, or EXP-12. They remain
  SHOULD/COULD follow-up experiments.
- Publication figures, per-policy failure-case interpretation, claims-to-
  evidence records, or paper comparison prose. Those belong to Feature 08.
- Real AWS collection, AWS CLI use, live Cloud Custodian execution, or account
  data. The current offline equivalent remains explicitly labelled as such.
- Manual result entry, notebooks as result sources, or committing generated
  run data that contains sensitive or account-specific inputs.
- Adding dependencies. The repository already pins NumPy, pandas, SciPy,
  scikit-learn, PyYAML, matplotlib, and seaborn; use those facilities only.

## Build loop

- **Branch:** `refs/heads/feature/run-the-reproduction-and-robustness-experiments`
- **Step review:** feature review after each build step.
- **Checkpoint commits:** disabled by project configuration.
- **Verification:** run focused tests while implementing, then `make test` and
  `make lint` at the end. Full benchmark runs require the locally prepared
  synthetic benchmark and must not be represented as completed unless they
  actually run.

## Build steps

- [x] **Establish shared experiment contracts and configuration loading.** Add
  typed validation for experiment IDs, organizations, seeds, input paths,
  split protocol, detector/baseline method names, and output locations. Expand
  `seeds: 0..29` deterministically and reject duplicate or malformed configs.
  **Done when:** each six MUST experiment configs loads to a resolved object
  with exactly 30 ordered seeds, and malformed/duplicate configurations fail
  with actionable errors in focused tests.

- [x] **Build reusable run orchestration and artifact persistence.** Add a
  runner that invokes existing evaluation APIs, creates one run directory per
  experiment/org/method/seed, records `config.yaml`, `metrics.json`,
  `preds.csv`, `env.txt`, and `git_sha.txt`, and refuses to overwrite an
  existing run. Include benchmark/input identity and split metadata without
  storing sensitive raw inputs.
  **Done when:** a one-seed smoke configuration creates the complete artifact
  set, rerunning it refuses to overwrite the directory, and tests verify that
  predictions contain policy ID, score, prediction, label, and misconfiguration
  type.

- [x] **Implement the required method adapters and fair shared-split execution.**
  Reuse the detector, threshold, split, metrics, and baseline APIs; add the
  bag-of-actions feature representation if needed; ensure all methods for one
  comparison consume the same locked test IDs and train-only fitting path.
  **Done when:** EXP-02 and EXP-07 smoke runs show identical test IDs across
  compared methods, bag-of-actions is deterministic and label-independent, and
  leakage tests fail if a test row reaches fitting, tuning, scaling, or
  threshold calibration.

- [x] **Implement EXP-01 through EXP-04 protocols.** Add the detector grid and
  validation-only selection for EXP-01, matched baseline execution for EXP-02,
  S1-to-S2/S3 transfer and shared-policy reporting for EXP-03, and fixed-test
  contamination sampling for EXP-04. Keep paper-style weighted metrics only
  as additional comparison fields; headline metrics remain the
  misconfiguration-positive minority-class metrics.
  **Done when:** one-seed smoke fixtures exercise all four protocols, EXP-04
  proves its test IDs are unchanged across contamination levels, and aggregate
  outputs include precision, recall, F1, PR-AUC, ROC-AUC where defined, and
  raw confusion counts.

- [x] **Implement EXP-07 and EXP-13 aggregate analyses.** Run the three
  Node2Vec/feature representations with identical LOF evaluation settings and
  group predictions by operator and difficulty without dropping empty or
  undefined groups silently.
  **Done when:** smoke outputs contain per-method and per-group recall with
  counts and seeded intervals, and repeated execution with the same fixture
  inputs produces byte-equivalent summaries.

- [x] **Add command entry points and experiment logging.** Add `make run-exp`
  for a named config and the repository-native command needed to regenerate
  all selected summaries. Update `docs/experiment_log.md` with the command,
  input snapshot identity, output path, and observations only after execution.
  **Done when:** the command dispatches each selected experiment, rejects
  unknown IDs, and `make test` plus `make lint` pass.

- [x] **Repair review finding F-02.** Wire the EXP-01 detector grid into
  validation-only selection on training-normal folds, persist the selected
  parameters and tuning metadata, and add regression coverage for the path.
  **Done when:** EXP-01 consumes configured candidates without using locked
  test rows and the focused protocol tests pass.

- [x] **Repair review findings F-03 through F-06.** Complete EXP-04 fixed
  contamination splits, EXP-13 grouped recall, EXP-02 Node2Vec comparison,
  and deterministic cross-seed summaries. **Done when:** full test and lint
  gates pass and each configured dispatch emits its required output.

## Files / areas

- `configs/experiments/exp01.yaml`, `exp02.yaml`, `exp03.yaml`, `exp04.yaml`,
  `exp07.yaml`, and `exp13.yaml` for resolved experiment inputs and the 30
  seeds.
- `src/misdet/experiments/` for configuration loading, orchestration, method
  dispatch, contamination/transfer protocols, and aggregate summaries; keep
  the existing `evaluate.py` and `baselines.py` APIs compatible.
- `src/misdet/baselines/` for the label-independent bag-of-actions
  representation and adapter needed by the selected comparisons.
- `tests/` for focused contract, determinism, split-reuse, leakage, and
  aggregation tests, extending existing experiment and baseline tests where
  appropriate.
- `Makefile` for `run-exp` and the reproducible summary command.
- `docs/experiment_log.md` and `docs/decisions.md` for observed runs and any
  project-specific protocol decisions.
- `results/runs/` and `results/tables/` as generated, local output locations;
  do not commit sensitive or unreviewed generated data.

## Data / contracts

- Input labels retain the existing schema, including `policy_id`, `label`,
  `misconfig_type`, `operator_id`, `difficulty`, and organization metadata when
  available. The positive label is `1` for misconfiguration.
- The primary split is `paper_90_10`: 90% of normal policies form the training
  pool, 10% of normals plus all selected misconfigurations form the locked
  test set, and validation folds come only from training normals. A comparison
  must reuse the same resolved split rather than independently reshuffling.
- Every randomized protocol uses integer seeds `0` through `29`. Derived
  random streams must be explicit and stable per experiment, organization,
  method, and seed.
- Every run records resolved configuration, split IDs or a non-sensitive split
  digest, metrics, locked-test predictions, environment, and Git revision.
  Existing artifact names are `config.yaml`, `metrics.json`, `preds.csv`,
  `env.txt`, and `git_sha.txt`.
- Metrics include minority-class precision, recall, F1, PR-AUC, ROC-AUC when
  both classes exist, alert-budget metrics when configured, confusion counts,
  mean/standard deviation across seeds, and seeded 95% bootstrap intervals.
  Undefined AUCs and empty operator/difficulty groups are represented as null
  with counts, not fabricated zeros.
- EXP-04 keeps the misconfiguration test set fixed while adding only the
  configured contamination examples to training. Test labels are never used
  to choose contamination, detector parameters, scalers, embeddings, or
  thresholds.
- EXP-03 reports whether shared managed policies are included or excluded
  only when that distinction is derivable from the prepared benchmark; it must
  not infer ownership from policy names alone.

## Testing

- Unit-test config parsing, seed expansion, method names, output path safety,
  deterministic feature construction, aggregate statistics, undefined metric
  handling, and operator/difficulty grouping.
- Test that all methods in a comparison receive the same split and that every
  contamination level in EXP-04 receives the same locked test IDs.
- Add explicit leakage tests for fitting, scaling, embedding selection,
  threshold calibration, hyper-parameter selection, and test-label access.
- Add a small fixture smoke run for each selected experiment. Do not claim the
  30-seed benchmark execution from unit tests.
- Run `make test` and `make lint`; the current environment previously lacked
  `pytest` and `ruff`, so setup may be required before those gates can pass.

## Notes for the AI

- Treat [detailed-plan.md](/home/ganesh-kumatole/programming/college/cloud-and-SRE/course-project/detailed-plan.md)
  Phase 9 and [docs/decisions.md](/home/ganesh-kumatole/programming/college/cloud-and-SRE/course-project/docs/decisions.md)
  as the experiment protocol references. Do not convert paper hypotheses into
  reported results.
- The existing offline Cloud Custodian-equivalent baseline is not actual
  Cloud Custodian output. Preserve that name and limitation in every config
  and summary.
- Use the existing Feature 5/6 run artifact conventions and positive-class
  metric semantics. Prefer small pure aggregation functions over a new
  framework.
- Keep generated outputs out of source control unless they are explicitly
  sanitized and required as benchmark deliverables. Never use AWS CLI or AWS
  credentials.
- Feature 08 owns publication figures and failure-case interpretation; this
  feature should expose machine-readable evidence for it.

<!-- blueprint:completion {"schemaVersion":2,"specBytes":13569,"specSha256":"6577b3e17a8b466b5c3bb7da90695eff3da9f7fb66796aed646177556b214ce7","branch":"refs/heads/feature/run-the-reproduction-and-robustness-experiments","head":"14bfe42b4b9dd9b1f567145a279dc2f2eead41a9","baseRef":"refs/heads/master","baseCommit":"dec7418ff972b7da3f399490a8bbc94c10b306fc","sourceTree":"457c561bdb746098e7559ee4a3c40c5e60ef38c2","landing":"local-merge","absentOptional":[]} -->

## Findings

- 7/F-01 [P2] open — GDS resource cleanup is not asserted by tests. Found 2026-11-04 by /audit. Does not block landing; carried forward for follow-up.

## Independent review

**Status:** approved
**Target commit:** 2bed1ba (working-tree repairs, pre-commit)
**Base commit:** dec7418ff972b7da3f399490a8bbc94c10b306fc
**Base ref:** master
**Spec hash:** 6577b3e17a8b466b5c3bb7da90695eff3da9f7fb66796aed646177556b214ce7
**Prepared by:** codex
**Builder model:** unknown (runtime did not expose exact model)
**Requested reviewer:** codex
**Requested model:** runtime default (exact model not known until reviewer starts)
**Requested execution:** automatic
**Requested at:** 2026-11-08T00:54:10+05:30
**Workflow:** regular
**Check required:** no
**Reviewer adapter:** codex
**Reviewer model:** unknown (runtime did not expose exact model)
**Reviewer context:** fresh session
**Actual execution:** manual
**Reviewed at:** 2026-11-08T01:00:01+05:30
**Scope:** current
**Lenses:** quality, security, performance, tests
**Verdict:** changes-requested

**Follow-up audit (working-tree repairs)**
**Actual execution:** manual
**Reviewed at:** 2026-11-08T02:00:00+05:30
**Scope:** current
**Lenses:** quality, security, performance, tests
**Verdict:** approved
**Check result:** not-required

**Commands (original review)**
- `make PYTHON=$PWD/.venv/bin/python test`: pass — 86 tests passed, one environment warning.
- `make PYTHON=$PWD/.venv/bin/python lint`: pass — Ruff reported all checks passed.

**Commands (follow-up audit)**
- `make test`: pass — 92 tests passed.
- `make lint`: pass — all checks passed.

**Findings (original review)**
- F-03 [P1] open, F-06 [P1] open, F-01 [P2] open

**Findings (follow-up audit)**
- F-03 [P1] closed — `run_contamination_for_org` now carves pool before split, resolves percent/absolute levels, validates pool size. 3 regression tests added.
- F-06 [P1] closed — `_write_cross_seed_summary` groups by seed-stripped path, pools preds across seeds, writes `bootstrap_recall_ci`. 3 regression tests added.
- F-01 [P2] open — GDS cleanup assertions still absent from `tests/test_embed.py`. Does not block landing.

**Remaining risk**
- F-01 remains an open P2 test-coverage gap for GDS cleanup assertions.

## Try it now

```bash
# Run one experiment (smoke, one seed) against the prepared benchmark
make PYTHON=$PWD/.venv/bin/python run-exp EXP=configs/experiments/smoke/exp01.yaml

# Inspect the summary
cat results/smoke/exp01/summary.json
```

To verify all six experiments dispatch and produce summaries:
```bash
for cfg in configs/experiments/smoke/exp01.yaml configs/experiments/smoke/exp02.yaml \
           configs/experiments/smoke/exp03.yaml configs/experiments/smoke/exp04.yaml \
           configs/experiments/smoke/exp07.yaml configs/experiments/smoke/exp13.yaml; do
  make PYTHON=$PWD/.venv/bin/python run-exp EXP=$cfg
done
```

Each run writes `config.yaml`, `metrics.json`, `preds.csv`, `env.txt`, and
`git_sha.txt` under `results/smoke/<exp>/<org>/<seed>/<method>/`. The
`summary.json` and `summary.csv` files aggregate across seeds with bootstrap
recall CIs. Unknown experiment IDs are rejected with an actionable error.
