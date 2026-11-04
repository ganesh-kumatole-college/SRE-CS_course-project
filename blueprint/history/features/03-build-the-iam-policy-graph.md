<!-- blueprint:completion {"schemaVersion":2,"specBytes":7424,"specSha256":"26304cb1c3e829066ea6321ad8c9803c83b79e0e5f930aafe64aa301c475487a","branch":"refs/heads/feature/build-the-iam-policy-graph","head":"8587f094bafec8bb9644018c5821dd42c73e74b3","baseRef":"refs/heads/master","baseCommit":"8587f094bafec8bb9644018c5821dd42c73e74b3","sourceTree":"2321697bb47369bab3540cb0dea02a510f57e5b0","landing":"local-merge","absentOptional":["blueprint/context/findings.md","blueprint/context/review.md"]} -->

# Feature: Build the IAM policy graph

**From build-plan:** feature 3
**Build attempt:** 1
**Branch:** feature/build-the-iam-policy-graph
**Status:** verified

## Goal
Implement the repo-native graph layer that turns the normalized IAM policies and synthetic benchmark rows into a faithful Entity–Policy–Action–Resource graph. The graph must support deterministic local construction, idempotent Neo4j loading, a NetworkX fallback for CI/local runs, and validation/export utilities so the later embedding and evaluation features consume one stable contract.

## Design reference
- The relevant requirement is the graph description in `blueprint/context/project-overview.md`, which defines the faithful graph edges and the project’s Neo4j/NetworkX stack.
- The repo already contains the graph package skeleton at `src/misdet/graph/__init__.py`; the feature fills that in with concrete graph construction and validation.
- The synthetic benchmark output produced in Feature 2 is the source data contract for policy, attachment, and label rows.

## In scope
- Build a deterministic graph from normalized policy records and synthesized entity attachments.
- Represent the policy graph as:
  - `(Entity)-[:ATTACHED_TO]->(Policy)`
  - `(Policy)-[:ALLOWS|DENIES]->(Action)`
  - `(Action)-[:WORKS_ON]->(Resource)`
- Keep the graph schema explicit and versioned enough for later embedding and detector work.
- Add a Neo4j loading path that is idempotent for repeated runs on the same graph dataset.
- Add a NetworkX fallback path for local development and tests when Neo4j is not available.
- Provide validation/export helpers that confirm required node and edge types, plus stable serialized output.
- Add focused tests for graph construction, edge creation, malformed input handling, and idempotent loading behavior.

## Out of scope
- Training embeddings or anomaly detectors.
- Live AWS data access or production graph deployment.
- Statement-scoped graph ablations beyond the optional documented path; they remain for later work unless required by the later experiment plan.
- Full GDS Node2Vec or experiment tuning; that belongs to Feature 4 and later features.

## Build loop
- Keep each build step small, reviewable, and runnable on the current branch.
- Use checkpoint commits only when a step naturally spans multiple edits or is easier to review in chunks.
- Each step ends with a concrete `Done when` tied to observed behavior and project checks.
- Final validation before completion: `make test` and `make lint`.

## Build steps
- [x] 1. Define the graph schema and data contract.
  - Create the concrete node and edge model for entities, policies, actions, and resources.
  - Freeze stable IDs, normalized action/resource strings, and the exact edge semantics used by the later embedding work.
  - Done when the graph contract is captured in code and tests and matches the `project-overview.md` requirements for `ATTACHED_TO`, `ALLOWS|DENIES`, and `WORKS_ON` edges.

- [x] 2. Implement the deterministic graph builder.
  - Build from the normalized policy snapshot and synthetic benchmark rows without relying on external services or random generation.
  - Ensure entity attachments map cleanly to policy nodes and that duplicate attachments are handled predictably.
  - Done when a sample graph built from fixture data produces the expected entity/policy/action/resource node and edge counts and contains no duplicate node identities.

- [x] 3. Add Neo4j loader and NetworkX fallback.
  - Implement the repo-native path for writing the same graph to Neo4j while preserving a simple fallback for local runs.
  - Keep the loader idempotent: re-running the same graph should not create duplicate graph records beyond the expected deterministic behavior of the target store.
  - Done when both code paths can be exercised in tests and the loader API accepts the same canonical graph object for both backends.

- [x] 4. Add validation and export utilities.
  - Validate required node types, edge labels, empty or malformed inputs, and missing attachment data.
  - Export a clean serialized graph artifact or summary format for later pipeline consumption.
  - Done when validation guards raise clear errors for invalid inputs and exported graph output is stable across repeated runs with the same fixture data.

- [x] 5. Add focused tests and verify the package.
  - Add tests for schema correctness, malformed input handling, duplicate attachments, and idempotent loading.
  - Run the project’s declared verification gates.
  - Done when the graph tests pass and `make test` plus `make lint` succeed.

## Files / areas
- `src/misdet/graph/` — primary implementation area for graph construction, validation, and loaders.
- `src/misdet/synth/` — input data contract and benchmark artifacts that the graph builder consumes.
- `src/misdet/collect/normalize.py` — existing policy normalization logic to keep aligned with the graph builder’s expected policy structure.
- `tests/` — add graph-focused tests for deterministic construction and error handling.
- `configs/` — optional local graph and Neo4j settings if the implementation needs explicit pinned configuration.

## Data / contracts
- All graph construction must be based on local project data only; no AWS CLI or live cloud access is allowed.
- Entity IDs, policy IDs, and attachment records must remain stable across repeated runs.
- Policy action and resource values must be normalized to the same lower-case semantics used by the normalized policy contract.
- Edge labels are fixed to the project contract: `ATTACHED_TO`, `ALLOWS`, `DENIES`, and `WORKS_ON`.
- The loader must treat repeated runs as repeatable, not as a source of extra graph drift.
- If a malformed policy or missing attachment is encountered, the graph builder should fail explicitly rather than silently invent an edge.

## Testing
- Add focused pure-logic tests for graph construction and validation.
- Cover empty input, malformed policy records, duplicate attachments, and missing resource/action values.
- If Neo4j is unavailable in the local environment, keep the test suite green with the NetworkX fallback path and explicit loader contract checks.
- Required verification before completion:
  - `make test`
  - `make lint`

## Notes for the AI
- Keep the implementation deterministic and small enough to reason about: explicit IDs, no hidden randomness, and no cross-feature assumptions beyond the policy contract already established.
- Prefer repository-native Python utilities and the standard library where possible; do not introduce unnecessary dependencies or service complexity.
- Treat the graph as a shared contract for later phases. If a design choice is optional, keep it simple and reproducible rather than over-engineering a solution that later features may not use.
- When Neo4j configuration is not yet pinned, default to a minimal fallback path and make the exact pinning decision explicit in the feature’s notes rather than making a hidden runtime assumption.

## Open questions
- Confirm the exact local Neo4j/GDS version pin and whether the project will primarily validate through the NetworkX fallback in CI when Neo4j is unavailable.
- Decide whether statement-level graph expansion is an optional later ablation or a required intermediate representation; the current project plan allows it to be optional and does not require it in this feature.

