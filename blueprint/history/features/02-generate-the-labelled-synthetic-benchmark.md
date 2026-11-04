<!-- blueprint:completion {"schemaVersion":2,"specBytes":7380,"specSha256":"c61a53208a68092c16633fbb3220a1d9e587f76319e431389c71eddba47741c4","branch":"refs/heads/feature/generate-the-labelled-synthetic-benchmark","head":"2bb4730c9829d07c1ffde2b491cc0136ce5b89bd","baseRef":"refs/heads/master","baseCommit":"2bb4730c9829d07c1ffde2b491cc0136ce5b89bd","sourceTree":"4f0b6fe7b897387cc01f3c0622fa81f5a17c8bfc","landing":"local-merge","absentOptional":["blueprint/context/findings.md","blueprint/context/review.md"]} -->

# Feature: Generate the labelled synthetic benchmark

**From build-plan:** feature 2
**Build attempt:** 1
**Status:** verified
**Branch:** `feature/generate-the-labelled-synthetic-benchmark`

## Goal

Create a deterministic, open synthetic IAM benchmark that mirrors the project’s
misconfiguration setting: three organization profiles, custom policy templates,
entities and attachments, hard negatives, and traceable labels for the injected
P1–A3 misconfigurations. This preserves a fixed benchmark for later graph,
embedding, and evaluation work while keeping the data local, sanitized, and
reproducible.

## In scope

- Freeze the benchmark-generation contract and the labeling rubric in the
  project documentation before writing any generated data.
- Implement deterministic synthetic benchmark generation in the
  `src/misdet/synth/` package, using the configured seed and project-wide
  conventions.
- Generate three distinct organization profiles with custom policy templates,
  entity definitions, attachment patterns, and hard negatives.
- Produce policy and attachment records that can be later consumed by the IAM
  graph and detection pipeline without leaking real AWS identity data.
- Emit a traceable label table that records policy ID, org, label, misconfig
  type, operator ID, difficulty, hard-negative flag, attached entity, source,
  and rationale.
- Add focused unit tests for deterministic behavior, malformed inputs, and
  edge-case policies such as wildcards and negated selectors.

## Out of scope

- Neo4j import, graph construction, embeddings, or anomaly-detector code.
- AWS API access, AWS CLI usage, or any cloud-connected data collection.
- Real organization or customer data, or any policy data not explicitly
  approved for local synthetic use.
- Final evaluation metrics, baselines, or paper claims from the benchmark alone.

## Build loop

Follow `workflow.stepReview: feature`: complete the implementation steps, then
provide a single review packet. Checkpoint commits are disabled. Verification is
`make setup` followed by `make test`; in the current workspace this currently
fails until the Python test dependencies are installed because `pytest` is not
available yet.

## Build steps

- [x] **Step 1 - Freeze the benchmark contract and generation inputs** - Define
  the synthetic benchmark schema, canonical policy/entity/attachment objects,
  the labeling rubric, and the deterministic generation inputs in
  `docs/data_schema.md` and `docs/decisions.md`. *Done when:* the docs specify
  the benchmark file layouts, row identity, prevalence denominator, operator
  rubric, and generation seed/organization-profile contract; no later feature
  is forced to reinterpret the labels.
- [x] **Step 2 - Implement the synthetic org/policy generator** - Add
  `src/misdet/synth/generator.py` to build three organization profiles and the
  matching custom policy templates, entity records, and attachments from a
  fixed seed. *Done when:* the generator deterministically creates different
  but plausible org structures, all policy and entity records are uniquely
  keyed, and a direct invocation produces stable output for repeated runs with
  the same seed.
- [x] **Step 3 - Implement misconfiguration injection and label emission** - Add
  `src/misdet/synth/injector.py` and `src/misdet/synth/labels.py` to apply the
  P1–A3 operators, create hard negatives, and write `labels.csv` with the
  required columns and rationale traceability. *Done when:* every generated
  policy has a deterministic label row, each operator is associated with its
  expected difficulty and misconfig type, and the output can be checked for
  both positive and negative examples without ambiguity.
- [x] **Step 4 - Add validation and CLI coverage** - Add focused tests in
  `tests/` for deterministic generation, wildcard and `NotAction` handling,
  malformed policy/attachment inputs, and edge cases such as empty profiles,
  duplicate IDs, and repeated seeds. *Done when:* the new validation tests run
  successfully under the project’s configured verification command after the
  Python dependencies are installed, and the benchmark output remains stable for
  repeated runs.

## Files / areas

- `src/misdet/synth/__init__.py`
- `src/misdet/synth/generator.py`
- `src/misdet/synth/injector.py`
- `src/misdet/synth/labels.py`
- `tests/test_synth.py` or the equivalent focused validation module
- `docs/data_schema.md`
- `docs/decisions.md`
- `configs/` for deterministic benchmark settings and seeds
- Local generated benchmark outputs under `data/` or the project’s approved
  synthetic-data directory

## Data / contracts

- Input is a local approved AWS-managed policy snapshot plus three synthetic
  organization profiles and explicitly seeded generation configuration.
- Output formats remain local and deterministic: one record per policy,
  entity, attachment, and label row, with a traceable source for every injected
  misconfiguration.
- Each benchmark row must preserve the identity and provenance required by the
  later graph and evaluation pipeline: `policy_id`, `org`, `label`,
  `misconfig_type`, `operator_id`, `difficulty`, `hard_negative`,
  `attached_entity_id`, `source`, and `rationale` for label rows.
- Policy attachments and entity memberships must be unique and deterministic,
  and hard negatives must be marked so the later evaluation can separate
  genuinely difficult negatives from trivial ones.
- Do not use live AWS identities, AWS CLI output, or a network-derived dataset
  in this feature; only owner-prepared local files or sanitized public data are
  permitted.

## Testing

- The configured verification gate is `make test`; the current workspace needs
  `make setup` first because `pytest` is not installed yet.
- Focused tests should cover deterministic generation, empty and malformed
  inputs, wildcard and negated-policy cases, duplicate IDs, and fixed-seed
  output stability.
- Each in-scope logic-bearing step must ship tests so the synthetic benchmark is
  validated before it is consumed by later graph and evaluation features.

## Notes for the AI

- Keep the generator deterministic by using explicit seeds and fixed ordering.
- Prefer the existing project layout and standard library patterns over
  introducing new dependencies or a heavier framework.
- Treat the benchmark as synthetic and local-only; do not commit sensitive or
  account-specific data.
- Ensure the generator produces the same output for the same input and seed,
  but still includes human-readable rationale in label records for later
  analyses.
- Respect the existing contract for policy normalization and avoid changing the
  schema implicitly in later phases.

## Open questions

- Freeze the exact organization profiles, entity sizes, and custom policy
  templates for the three synthetic organizations before emitting the final
  benchmark.
- Decide the exact attachment-label row identity and the benchmark prevalence
  denominator so later evaluation metrics and per-type analysis use the same
  population definition.
- Confirm the final output file naming and whether the benchmark version is
  stored as JSONL, CSV, or both to match the downstream graph and experiments.
- Confirm how the approved AWS-managed snapshot revision and licensing metadata
  are recorded alongside the synthetic benchmark generation run.

## Findings

_No findings recorded. `/audit` appends findings here when it finds them._

## Independent review

_No independent review requested. Run `/audit independent current` to prepare one._

## Try it now

- Run `make setup` in a Python virtual environment.
- Run `PATH=.venv/bin:$PATH make test` and `PATH=.venv/bin:$PATH make lint`.
- Inspect the generated synthetic benchmark while it remains local-only and
  deterministic, then use the resulting policy/entity/attachment/label files as
  the input to the next graph-building feature.
