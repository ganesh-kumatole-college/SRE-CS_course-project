# Fix: Execute Node2Vec through GDS

**Type:** Fix
**Status:** verified
**Branch:** fix/execute-node2vec-through-gds

## The problem

`embed_policy_nodes_with_gds()` only checks Neo4j connectivity with `RETURN 1`,
then delegates to the Python fallback. Supplying Neo4j credentials therefore
does not run Graph Data Science Node2Vec, and failures can be represented as
successful fallback output instead of exposing a GDS error.

## The fix

Make the configured Neo4j path actually project the supplied `PolicyGraph`,
invoke the supported `gds.node2vec.stream` procedure, and return vectors aligned
to stable policy node IDs through the existing interface. Keep the existing
Python fallback for calls without GDS connection settings; do not silently
substitute it after a configured GDS operation fails. Use the already-selected
settings from `configs/default.yaml` (128 dimensions, walk length 80, 10 walks
per node, return/in-out factor 1, window size 10, seed 42). Keep temporary graph
resources scoped to the run and clean them up on success and failure.

## Build steps

- [x] Implement and test the actual GDS execution path
  - Reuse the repository’s Neo4j driver and GDS procedure pattern shown in
    `scripts/smoke_gds.py`; repair its graph-creation Cypher if needed to make
    the required integration check executable. Avoid adding dependencies or
    changing the selected configuration defaults.
  - Preserve the fallback API and stable policy-ID ordering. Surface connection,
    projection, procedure, and result-shape failures when GDS was requested;
    clean up only temporary graph data owned by this invocation.
  - Add focused tests for result mapping and failure behavior, plus verify the
    real GDS call with the existing smoke command when local Neo4j/GDS is
    available.
  - **Done when:** `embed_policy_nodes_with_gds()` returns actual 128-D GDS
    vectors aligned with policy IDs, a configured GDS failure raises instead of
    returning fallback vectors, `pytest tests/test_embed.py -q` passes, and
    `make smoke-gds` passes against the configured Neo4j/GDS instance.

## Verify

- Run `pytest tests/test_embed.py -q`.
- Run `make smoke-gds` with the local Neo4j/GDS stack.
- Run `make lint` and `make test`.


<!-- blueprint:completion {"schemaVersion":2,"specBytes":2247,"specSha256":"fec37bfb664793873b141a6e70fd343cc1544b105826d99a38653c7ef467c90e","branch":"refs/heads/fix/execute-node2vec-through-gds","head":"8a133e014680fa2a4c1267602145156a3c001c15","baseRef":"refs/heads/master","baseCommit":"98999767963b952734e63c0d768fc93acfab3e3a","sourceTree":"3d55e4aea7bc14ed179164f24b6595d95c235d77","landing":"local-merge","absentOptional":[]} -->

## Verification

- `.venv/bin/python -m ruff check src tests scripts`: passed.
- `.venv/bin/python -m pytest`: passed (35 tests).
- `make smoke-gds`: the project owner reported a pass (5 nodes, 128 dimensions); the command was run locally by the owner after the smoke-query fix. The only output warning was the GDS graph-drop deprecation notice.

## Independent review

**Status:** passed
**Target commit:** 8a133e014680fa2a4c1267602145156a3c001c15
**Base commit:** 98999767963b952734e63c0d768fc93acfab3e3a
**Base ref:** refs/heads/master
**Spec hash:** fec37bfb664793873b141a6e70fd343cc1544b105826d99a38653c7ef467c90e
**Prepared by:** copilot
**Builder model:** gpt-6-luna
**Requested reviewer:** copilot
**Requested model:** runtime default (exact model not known until reviewer starts)
**Requested execution:** automatic
**Requested at:** 2026-11-04T23:06:23+05:30
**Workflow:** regular
**Check required:** no
**Reviewer adapter:** copilot
**Reviewer model:** unknown (runtime did not expose exact model)
**Reviewer context:** fresh subagent
**Actual execution:** automatic
**Reviewed at:** 2026-11-04T23:10:01+05:30
**Scope:** current
**Lenses:** quality, security, performance, tests
**Verdict:** passed
**Check result:** not-required

## Handoff

Review the active spec and the complete `98999767963b952734e63c0d768fc93acfab3e3a..8a133e014680fa2a4c1267602145156a3c001c15` delta in a fresh session or isolated subagent without the builder conversation. Run all Audit lenses from scratch. Run Check when required above. Do not edit product code, accept findings, or reuse the existing findings as the review scope.

## Commands

- `make lint`: unavailable; Ruff is not installed in the reviewer runtime.
- `make test`: unavailable; pytest is not installed in the reviewer runtime.
- `make smoke-gds`: unavailable; not independently run because the Neo4j driver is not installed in the reviewer runtime.

## Evidence

- Verified `HEAD` equals target `8a133e014680fa2a4c1267602145156a3c001c15`, `refs/heads/master` resolves to the recorded base, and its merge base with the target is `98999767963b952734e63c0d768fc93acfab3e3a`.
- Verified the active spec SHA-256 is `fec37bfb664793873b141a6e70fd343cc1544b105826d99a38653c7ef467c90e`; before writing the receipt and ledger, the only worktree difference was the permitted `blueprint/context/review.md` file.
- Reviewed the full target delta, including the GDS backend, Python fallback/export surface, smoke script, embedding tests, active spec, and related plan/history changes.
- The project owner reported `make lint && make test` and `make smoke-gds` passed; these reports were not treated as independently executed results.

## Findings

- F-01 [P2] open - GDS resource cleanup is not asserted by tests.

## Remaining risk

- Ruff and pytest were unavailable, so lint and tests could not be independently run. The local Neo4j/GDS integration was not independently verified; the smoke-test pass is user-provided evidence only.


## Try it now

Run in a terminal where `NEO4J_PASSWORD` is set:

```bash
source .venv/bin/activate
python - <<'PY'
import os
from misdet.embed import embed_policy_nodes_with_gds
from misdet.graph import build_policy_graph

graph = build_policy_graph([{
    "policy_id": "smoke-policy",
    "document": {"Statement": [{
        "Effect": "Allow",
        "Action": ["s3:GetObject"],
        "Resource": ["*"],
    }]},
}])
vectors, policy_ids = embed_policy_nodes_with_gds(
    graph,
    uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
    user=os.getenv("NEO4J_USER", "neo4j"),
    password=os.environ["NEO4J_PASSWORD"],
)
print(vectors.shape, policy_ids)
PY
```

Expected: `(1, 128) ['Policy:smoke-policy']

This directly exercises the configured GDS backend and stable policy-ID output.
