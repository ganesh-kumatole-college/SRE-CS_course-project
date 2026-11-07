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

### F-02 [P1] fixed - EXP-01 ignores its detector grid and configured parameters

**File:** src/misdet/experiments/runner.py:163
**Found:** 2026-11-08 by /audit (scope: current; lens: quality, security, performance, tests)
**Why it matters:** The EXP-01 configuration declares detector-specific candidate grids and the feature contract requires validation-only tuning. The runner passes the flat `detector_params` mapping to `run_detector_comparison`, which expects a mapping keyed by detector name, and never reads `detector_grid` or calls `select_detector_params`. Consequently EXP-01 runs default detector settings instead of the configured candidates and does not perform the required validation-only selection, so its reported comparison does not implement the experiment it claims to run.
**Suggested fix:** Wire `detector_grid` into an explicit validation-only selection path for each detector, or remove the unused grid only if the EXP-01 requirement is explicitly reduced. Preserve the locked test split and ensure selected parameters are recorded in each run artifact.
**Resolution:** EXP-01 now selects configured candidates from a training-normal
validation fold, refits the selected parameters on the full training-normal
pool, and records tuning metadata in the run artifact. Focused protocol tests
pass; an independent audit must re-review and close this finding.
