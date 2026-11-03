# Feature: Acquire and normalize IAM policy data

**From build-plan:** feature 1
**Build attempt:** 1
**Status:** verified
**Branch:** `feature/acquire-and-normalize-iam-policy-data`

## Goal

Normalize a locally supplied, public AWS-managed IAM policy snapshot into a
deterministic policy dataset with documented contracts, source provenance, and
descriptive statistics. This establishes the policy input for the later graph
and synthetic-benchmark features.

## In scope

- Document the canonical policy and statement JSONL schema and the source/run
  manifest.
- Parse a local AWS IAM authorization-details-shaped JSON snapshot, using only
  each policy's default version.
- Preserve IAM statement semantics while normalizing policy documents and
  redacting account IDs in ARNs.
- Emit normalized policy JSONL, provenance, and dataset statistics; report
  malformed or empty inputs explicitly.
- Add focused tests for valid, empty, malformed, wildcard, and negated-policy
  inputs.

## Out of scope

- AWS API calls, AWS CLI use, credentials, or agent-driven network downloads.
- Organization entity or attachment records. Feature 2 generates the synthetic
  entities and attachments.
- Graph construction, embeddings, detectors, or labels.
- Selecting or licensing a particular public snapshot.

## Build loop

Follow `workflow.stepReview: feature`: complete the steps, then provide one
review packet. Checkpoint commits are disabled. `/complete` creates the final
feature commit.

## Build steps

- [x] **Step 1 - Define and document the data contract** - Add the canonical
  policy/statement schema and provenance requirements in `docs/data_schema.md`,
  record the public-snapshot decision and remaining source choice in
  `docs/decisions.md`, and document the local normalization command in
  `README.md`. *Done when:* the schema specifies field names, types, nullability,
  uniqueness, statement ordering, normalization, hash, and manifest behavior;
  documentation makes clear that this feature emits no entity records.
- [x] **Step 2 - Implement policy normalization** - Add typed, focused parser
  functions in `src/misdet/collect/normalize.py` and unit tests in
  `tests/test_normalize.py`. Support statement objects or lists; string or list
  action/resource values; `Action`/`NotAction`, `Resource`/`NotResource`,
  `Principal`, `Condition`, URL-encoded policy documents, and default-version
  selection. Preserve wildcards and IAM fields, lowercase service/action
  patterns, redact account-ID ARN components as documented, and attach a
  deterministic per-statement `raw_hash`. *Done when:* focused tests verify
  semantic preservation, deterministic hashes, and actionable failures for
  malformed structures, missing defaults, duplicate policy IDs, and empty
  snapshots; `make test` passes.
- [x] **Step 3 - Add the local CLI and reproducibility outputs** - Read the
  supplied snapshot, write one sorted policy record per JSONL line to `--out`,
  and produce sibling `source_manifest.json` and `policy_stats.json` files using
  the standard library. Validate the full input before writing outputs so an
  input validation failure leaves existing outputs unchanged. *Done when:* a
  fixture can be normalized end-to-end deterministically; the manifest records
  the source URL, revision, snapshot date, license, input and normalized-output
  hashes, and policy count; statistics report policy/statement counts,
  wildcard-action-pattern share, action patterns per policy, and services;
  malformed input exits nonzero without changing existing outputs. The
  documented invocation is `python -m misdet.collect.normalize --in X --out Y`
  with required source URL, revision, snapshot-date, and license metadata.
- [x] **Step 4 - Preserve non-ARN values during redaction** - Limit account-ID
  redaction to the 12-digit account component of ARN-formatted strings and add
  regression coverage for matching account-like text in condition values.
  Update the schema documentation to match. *Done when:* account IDs are
  redacted in ARN values while strings such as
  `folder:123456789012:private/*` remain byte-for-byte unchanged; focused tests
  and `make test` pass.
- [x] **Step 5 - Refuse symlink output paths** - Open each output directory
  component without following symlinks, create missing components relative to
  the verified directory handle, and open generated files with no-follow
  semantics. *Done when:* symlinks at a directory component or any generated
  output file are rejected before writes; symlink targets and other outputs
  remain unchanged; focused tests and `make test` pass.
- [x] **Step 6 - Reject overflowing JSON numbers** - Reject floating-point
  tokens that decode to non-finite values in snapshots and embedded policy
  documents, and report parser conversion errors through the normal
  `NormalizationError` CLI path. *Done when:* an input containing `1e9999`
  exits nonzero with a concise diagnostic and leaves existing outputs
  unchanged; the focused and full test suites pass.
- [x] **Step 7 - Reject hard-linked output aliases** - Compare each existing
  output's device/inode identity with the input and other outputs before any
  truncation, then verify open output descriptors still match the checked
  identities. *Done when:* hard links to the input or between generated outputs
  are rejected without changing any contents; tests pass.

## Files / areas

- `src/misdet/collect/normalize.py`
- `tests/test_normalize.py`
- `docs/data_schema.md`
- `docs/decisions.md`
- `README.md`
- Local generated outputs under `data/interim/`; do not commit raw input.

## Data / contracts

- Input is a local JSON snapshot shaped like AWS
  `get-account-authorization-details`, containing AWS-managed policies and
  their version lists. Select exactly the default policy version and accept its
  document as either a JSON object or URL-encoded JSON.
- Output is UTF-8 JSONL with one record per policy, sorted by unique
  `PolicyArn`. The exact record keys are `policy_id` (non-empty string, equal
  to `PolicyArn`), `org` (null), `source` (the string `"aws_managed"`), and
  `document` (JSON object). Preserve all other top-level policy-document fields;
  `Statement` is a non-empty array, with source statement order retained.
- Each statement is a JSON object with `Effect` (`"Allow"` or `"Deny"`), exactly
  one non-empty string-array selector from `Action`/`NotAction`, exactly one
  non-empty string-array selector from `Resource`/`NotResource`, and
  `raw_hash` (64-character lowercase SHA-256 hex). `Action` and `NotAction`
  values are lowercase; wildcards are not expanded. Preserve `Principal`,
  `Condition`, `Sid`, and other source statement fields as JSON values without
  rewriting their structure. Policy ARNs must be unique.
- Redact a 12-digit account-ID ARN component with the fixed string
  `REDACTED`; document that normalized output is for analysis and is not an
  executable policy document. Compute `raw_hash` as lowercase SHA-256 over the
  redacted source statement serialized as UTF-8 JSON with sorted keys and
  compact separators, before action normalization.
- Write the normalized JSONL to the requested `--out` path and sibling
  `source_manifest.json` and `policy_stats.json` files in its directory. Require
  `--source-url`, `--revision`, `--snapshot-date`, and `--license`. The manifest
  has `schema_version` (integer, value 1), `source_url`, `source_revision`,
  `snapshot_date` (ISO `YYYY-MM-DD` string), `license`, `input_sha256`,
  `policies_sha256` (lowercase 64-character SHA-256 hex), and `policy_count`
  (integer). No generation timestamp is needed; identical inputs and metadata
  must produce identical outputs.
- Statistics count action patterns from both `Action` and `NotAction`; wildcard
  share is the count containing `*` divided by the total action-pattern count.
  `policy_stats.json` contains `policy_count`, `statement_count`,
  `action_pattern_count`, `wildcard_action_pattern_count`,
  `wildcard_action_pattern_share`, `action_patterns_per_policy` with
  `min`/`median`/`mean`/`max`, and `services` mapping service prefixes to
  pattern counts. A global `*` pattern has no service prefix. Do not expand
  patterns.
- Reject missing/ambiguous default versions, invalid documents, duplicate
  policy IDs, and snapshots with no policies. Do not silently drop records.
  Validate the complete input before writing outputs; validation failure exits
  nonzero and leaves existing outputs unchanged. No entity JSONL is emitted in
  this feature.

## Testing

- Add unit coverage for dict/list statements, string/list values, URL-encoded
  documents, default versions, conditions/principals, wildcards, negated
  fields, account-ID redaction, stable hashes and output, empty input, malformed
  input, duplicates, and CLI failure behavior.
- Run `make test` and `make lint` after implementation. During spec creation,
  `make test` was attempted but could not run because `pytest` is not installed;
  do not treat that as passing test evidence.

## Notes for the AI

- The selected data class is a public AWS-managed policy snapshot. Use only a
  local file prepared by the project owner; never use AWS credentials, AWS CLI,
  or network fetching. Keep raw/interim files out of source control unless the
  project owner separately approves sanitized public data and its license.
- Entity and attachment data are intentionally deferred to Feature 2. Do not
  create empty or synthetic entity records here.
- Use the standard library; do not add dependencies. Keep normalization pure
  where practical and surface failures with actionable errors.

## Open questions

- Which reputable public snapshot repository, revision/date, and license should
  supply the end-to-end dataset? This is not needed to implement against local
  fixtures, but must be approved and supplied locally before acquiring data or
  claiming the real-snapshot zero-parse-error/count checks.


<!-- blueprint:completion {"schemaVersion":2,"specBytes":9966,"specSha256":"13e711e5c0da8c6fc8c65b233ff5e7def98caf015c1955e4b9e295e5aa6194ea","branch":"refs/heads/feature/acquire-and-normalize-iam-policy-data","head":"d2527e8d8c71c830e9bcf2441b1411f1a8f705e8","baseRef":"refs/heads/master","baseCommit":"83a371a22477455abbe217442213da8710d9d1f5","sourceTree":"bc9076e9f40d13141dd68c4f56d3085b96b8e66a","landing":"local-merge","absentOptional":[]} -->

## Findings

### F-01 [P2] closed - Redaction alters non-ARN policy values

**File:** src/misdet/collect/normalize.py:43
**Found:** 2026-11-04 by /audit (scope: current; lens: all)
**Why it matters:** `_redact` applies the account-ID pattern to every string, not only ARN strings. A valid condition value such as `folder:123456789012:private/*` is changed to `folder:REDACTED:private/*`, corrupting preserved policy semantics.
**Suggested fix:** Restrict account-ID redaction to ARN strings and preserve unrelated string values. No current requirement would be lost.
**Resolution:** Closed after independent review of the target implementation and regression test. `_redact` replaces only the 12-digit account component in ARN-formatted strings; the test verifies the non-ARN condition value remains unchanged while ARN principals and policy IDs redact. Reconfirmed in the current independent review.



### F-02 [P2] closed - Generated output paths follow pre-existing symlinks

**File:** src/misdet/collect/normalize.py:307-313
**Found:** 2026-11-04 by /audit (scope: current; lens: all)
**Why it matters:** The normalizer rejects symlinks at the three destination leaves, but a symlink in an ancestor directory is followed by `mkdir`, `lstat`, and the later opens. The generated files can therefore still be redirected into and truncate unrelated files in the symlink target directory.
**Suggested fix:** Reject symlinks in every existing output-path directory component or open the verified output directory without following symlinks and create all outputs relative to that directory. No current requirement would be lost.
**Resolution:** Closed after independent review. The implementation opens every output directory component with `O_DIRECTORY | O_NOFOLLOW`, creates missing components relative to the verified directory descriptor, preflights all three output leaves, and writes through the held directory descriptor. `O_NOFOLLOW` and regular-file checks protect each leaf. Tests verify symlinked ancestors and each generated leaf are rejected without changing their targets or writing other outputs.



### F-03 [P2] closed - Overflowing JSON numbers bypass actionable normalization errors

**File:** src/misdet/collect/normalize.py:35,74,415
**Found:** 2026-11-04 by /audit (scope: current; lens: all)
**Why it matters:** Python's JSON parser accepts a numeric token such as `1e9999` but converts it to infinity. Hashing that statement through `_json_bytes` raises a plain `ValueError` because `allow_nan=False`; `main` catches only `NormalizationError` and `OSError`, so the CLI emits an uncaught traceback instead of its normal actionable input error. This violates the malformed-input error contract.
**Suggested fix:** Reject numeric overflow during parsing or translate serialization `ValueError` into `NormalizationError`, then add a CLI regression test asserting a nonzero status and concise diagnostic. No current requirement would be lost.
**Resolution:** Closed after independent review of the target implementation. `_parse_json_float` rejects non-finite values with `NormalizationError`; both snapshot and embedded-document parsing route conversion failures into the normal CLI error handler. Regression tests cover the CLI message, nonzero status, and unchanged outputs.



### F-04 [P1] closed - Hard-linked outputs can overwrite the input snapshot

**File:** src/misdet/collect/normalize.py:378-400
**Found:** 2026-11-04 by /audit (scope: current; lens: all)
**Why it matters:** The input/output collision check compares resolved pathnames, which do not identify hard links. If any existing generated output is a hard link to the input snapshot, `_write_output` truncates the shared inode at line 332 and replaces the source snapshot. Distinct hard-linked output files can likewise overwrite each other's contents.
**Suggested fix:** Before truncating destinations, reject existing outputs whose `(st_dev, st_ino)` matches the input or another generated output; add regression tests for hard-linked input and output aliases. No current requirement would be lost.
**Resolution:** Closed after independent Phase B review of the complete target delta. `normalize_file` records each existing output's device/inode identity, rejects identities shared with the input or another output before writing, and passes the expected identity to `_write_output` for descriptor verification (`src/misdet/collect/normalize.py:403-438`). Regression tests confirm hard links to the input and between generated outputs are rejected without changing contents (`tests/test_normalize.py:391-437`). The full test suite and lint passed.

## Independent review

**Status:** passed
**Target commit:** d2527e8d8c71c830e9bcf2441b1411f1a8f705e8
**Base commit:** 83a371a22477455abbe217442213da8710d9d1f5
**Base ref:** master
**Spec hash:** 13e711e5c0da8c6fc8c65b233ff5e7def98caf015c1955e4b9e295e5aa6194ea
**Spec snapshot:** blueprint/.state/review-specs/d2527e8d8c71c830e9bcf2441b1411f1a8f705e8-13e711e5c0da8c6fc8c65b233ff5e7def98caf015c1955e4b9e295e5aa6194ea.md
**Prepared by:** copilot
**Builder model:** unknown (runtime did not expose exact model)
**Requested reviewer:** copilot
**Requested model:** runtime default (exact model not known until reviewer starts)
**Requested execution:** automatic
**Requested at:** 2026-11-04T02:22:12+05:30
**Workflow:** regular
**Check required:** no

## Handoff

Review the active spec and the complete `83a371a22477455abbe217442213da8710d9d1f5..d2527e8d8c71c830e9bcf2441b1411f1a8f705e8` delta in a fresh isolated reviewer context, without the builder conversation. Run all Audit lenses from scratch. Do not edit product code, accept findings, commit, or perform external actions.

**Reviewer adapter:** copilot
**Reviewer model:** unknown (runtime did not expose exact model)
**Reviewer context:** fresh subagent
**Actual execution:** automatic
**Reviewed at:** 2026-11-04T02:25:04+05:30
**Scope:** current
**Lenses:** quality, security, performance, tests
**Verdict:** passed
**Check result:** not-required

## Commands

- `PATH="$PWD/.venv/bin:$PATH" PYTHONPATH=src make test`: pass (22 tests).
- `PATH="$PWD/.venv/bin:$PATH" make lint`: pass.
- `git diff --check master...HEAD`: pass.
- Phase B target, base, dirty-path, and snapshot freshness validation: pass.

## Evidence

- Reviewed all five files in `master...HEAD` at target `d2527e8d8c71c830e9bcf2441b1411f1a8f705e8`, covering implementation, tests, and directly related documentation.
- Verified `master` resolves to base `83a371a22477455abbe217442213da8710d9d1f5`, the recorded merge base; no product paths differ from target.
- The active spec and ignored local snapshot have identical bytes and the recorded SHA-256; both are regular ignored files absent from the index and target tree.
- Re-reviewed the hard-link protection and regression tests; no new issue found across the four lenses.

## Findings

- F-04 closed; no new findings.

## Remaining risk

- Bare `make test` and `make lint` under system Python lack pytest and Ruff; the same declared Make targets passed with the existing project virtual environment. No real AWS snapshot or runtime performance profile was available or required for this local review.
