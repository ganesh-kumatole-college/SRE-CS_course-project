# Feature: Embed policy nodes with Node2Vec

**From build-plan:** feature 4
**Build attempt:** 1
**Branch:** feature/embed-policy-nodes-with-node2vec

## Goal

Implement the feature-4 embedding layer that converts the existing IAM policy graph into a deterministic 128-dimensional representation for policy nodes, with a repository-native fallback path that preserves the same public interface when Neo4j/GDS is unavailable. The work must support the project’s generator/evaluation pipeline by returning embeddings for policy nodes, storing the chosen graph and walk settings, and keeping all randomness seeded and testable.

## Design reference

No graphical UI reference exists for this backend-only feature. The design follows the project’s canonical graph schema from the overview and the detailed plan: `Entity -> ATTACHED_TO -> Policy -> ALLOWS/DENIES -> Action -> WORKS_ON -> Resource`, with Node2Vec applied to the resulting policy nodes and parameter choices recorded in config rather than hard-coded.

## In scope

- Define the shared embedding contract for policy nodes and its config surface in `configs/`.
- Implement a pure-Python fallback under `src/misdet/embed/` using the repository’s current graph representation and a seeded Node2Vec implementation path.
- Implement the Neo4j/GDS-backed embedding path using Graph Data Science and the project’s compatible graph naming conventions.
- Normalize and validate embedding output: shape `(n_policy_nodes, 128)`, stable ordering, no NaN values, and deterministic behavior with a fixed seed.
- Ensure the embedding layer can run from `build_policy_graph()` output without leaking any test-split data or AWS credentials.
- Record the exact graph and walk settings used for each embedding run and keep parameter values in YAML/config rather than in code.
- Add focused unit tests covering valid output, malformed inputs, deterministic behavior, and ordering/relative-distance checks for policy similarity.

## Out of scope

- Building the anomaly detector pipeline itself (LOF, One-Class SVM, Isolation Forest, Robust Covariance) is a later feature.
- Training or threshold tuning on the locked test split is out of scope for this feature.
- Cloud Custodian or other baselines are outside the feature boundary.
- Hosted deployment, a web UI, and external AWS data collection are out of scope.
- Any broader experiment analysis or paper reporting is for later phases.

## Build loop

- Build one item at a time, with a small review packet at the end of the feature.
- Keep the repository working after each checklist item.
- Use the configured workflow review cadence: `feature` and `checkpointCommits` disabled.
- Run the project’s declared verification command after the feature is in place and when a smaller targeted check cannot isolate the behavior.

## Build steps

- [x] Define the embedding interface and config contract
  - Implement a small shared embedding function or class contract that accepts a canonical policy graph and typed config, returning a policy-vector matrix keyed by policy node IDs.
  - Preserve the project conventions: explicit seeds, no global randomness, policy ids remain stable, and parameter values come from YAML/config files instead of hard-coded defaults.
  - `Done when`: an interface exists in `src/misdet/embed/` and config keys for `embeddingDimension` plus the chosen walk parameters are documented or stored in `configs/default.yaml`; a focused pytest check proves the contract accepts a canonical graph and rejects malformed config/input.

- [x] Implement the fallback Node2Vec path for local execution
  - Build the Python fallback directly against the project’s `PolicyGraph` structure and the canonical policy graph node IDs, while keeping the API consistent with the GDS path.
  - Prefer the smallest repo-native implementation that is deterministic and returns an embedding for each policy node with no NaNs.
  - `Done when`: the fallback yields a matrix with shape `(n_policies, 128)` for a small synthetic graph and the same fixed-seed run is repeatable; `pytest tests/test_embed.py -q` passes for the fallback contract.

- [x] Implement the Neo4j/GDS-backed path and serialization contract
  - Add the Neo4j/GDS embedding backend under `src/misdet/embed/` using the project graph and parameter config, then read the result back into a stable Python structure that matches the fallback API.
  - Record the exact procedure name and documentation reference used for the active GDS version in a source comment so the implementation remains verifiable.
  - `Done when`: the GDS path can be invoked against a small graph in the local Neo4j+GDS setup, returns an embedding matrix aligned to policy IDs, and the smoke check or equivalent integration test passes in the repository’s configured environment.

- [x] Add unit and determinism tests for the embedding layer
  - Use small synthetic graphs with known policy relationships, fixed seeds, and malformed inputs to cover happy path, empty/invalid graph cases, stability, and a similarity rule: two policies with identical statements should be closer together than two random policies.
  - `Done when`: `make test` passes, or the focused embedding test target passes if the repository’s full suite is not configured yet; the tests demonstrate the required shape, no-NaN constraint, and reproducibility behavior.

## Files / areas

- `src/misdet/graph/builder.py` — canonical policy graph input and stable node identifiers.
- `src/misdet/embed/__init__.py` — shared public interface for embedding backends.
- `src/misdet/embed/gds_node2vec.py` — Neo4j/GDS-backed Node2Vec implementation.
- `src/misdet/embed/py_node2vec.py` — Python fallback implementation matching the same interface.
- `configs/default.yaml` — graph and Node2Vec configuration values, including the explicit seed and 128-dimensional embedding size.
- `tests/test_embed.py` — embedding correctness and determinism tests.
- `scripts/smoke_gds.py` or equivalent local validation entry points — GDS smoke verification when the Neo4j/GDS stack is available.

## Data / contracts

- Input graph contract: canonical IAM `PolicyGraph` built from normalized policy rows, entity attachments, and the `Action`/`Resource` edges described in the overview.
- Output contract: a policy embedding matrix of shape `(n_policy_nodes, 128)` with one row per policy node; ordering must remain stable and aligned to policy IDs.
- Parameter contract: all Node2Vec settings (embedding dimension, walk length, walks per node, p, q, update policy, directed/undirected mode, and seed) are explicit in config and not hard-coded in the core logic.
- Persistence contract: embedding metadata must record the graph snapshot, walk configuration, seed, and backend used, so later detector and experiment code can reproduce the same settings without guessing.
- Security contract: no AWS credentials, no live AWS CLI data collection, and no test-split leakage into embedding or tuning.

## Testing

- Targeted tests for the embedding contract: valid graph shape, invalid config/input behavior, deterministic output with fixed seed, no NaN values, and policy-similarity ordering on a toy graph.
- Use the repository’s existing pytest suite (`make test`) after the feature lands; if the environment is not yet configured for Neo4j/GDS, the Python fallback tests remain the minimum verification gate.
- When the local Neo4j stack is active, run the GDS smoke check to confirm the backend is reachable and that procedure names match the installed version.

## Notes for the AI

- Preserve the project’s research requirements: no AWS credentials, explicit seeds for all random behavior, and a clear split between graph construction and later anomaly scoring.
- Treat the graph builder in `src/misdet/graph/builder.py` as the authoritative input; this feature should consume the existing canonical representation rather than inventing a second policy-graph model.
- The implementation need not guess the final paper-backed Node2Vec hyperparameters. The feature should freeze a default configuration in `configs/default.yaml`, keep the values parameterized, and document the decision in decisions/log text when the protocol is chosen.
- Keep the fallback path and GDS path behind the same interface so the detector feature can consume either backend without additional branching.

## Open questions

- Confirm the exact default Node2Vec walk parameters (`walkLength`, `walksPerNode`, `p`, `q`, directed vs. undirected, and seed policy) and where they live in the repo—`configs/default.yaml` or a feature-specific config file.
- Confirm whether the project prefers the pure-Python fallback as the default local path or treats the GDS path as the primary backend while retaining the fallback for resilience.
- Verify the active Neo4j/GDS procedure names for the local environment before locking the GDS implementation to a specific call signature.



<!-- blueprint:completion {"schemaVersion":2,"specBytes":8968,"specSha256":"0a1b980650388473055504940c8c6c181ccc7ec530f8d52aa42b4e3591daa2c7","branch":"refs/heads/feature/embed-policy-nodes-with-node2vec","head":"98999767963b952734e63c0d768fc93acfab3e3a","baseRef":"refs/heads/master","baseCommit":"98999767963b952734e63c0d768fc93acfab3e3a","sourceTree":"0966e675330b818ada063962036bd593f7f38be8","landing":"local-merge","absentOptional":[]} -->


## Verification

- `make lint && make test`
- Result: passed (`33 passed` and Ruff checks passed)

## Findings

_No findings recorded. `/audit` appends findings here when it finds them._

## Independent review

_No independent review requested. Run `/audit independent current` to prepare one._
