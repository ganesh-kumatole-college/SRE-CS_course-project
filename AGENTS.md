# IAM Misconfiguration Detection

This project is a research reimplementation of graph-embedding anomaly detection
for AWS IAM policy misconfigurations. It is intended for a course project and
uses synthetic organization data plus public AWS-managed policy data.

## Commands

- Setup: `make setup`
- Tests: `make test`
- Lint: `make lint`
- Format: `make format`
- Start local Neo4j: `make neo4j-up`
- Stop local Neo4j: `make neo4j-down`
- Graph Data Science smoke test: `make smoke-gds`

Tests are configured and are a gate for changes that add logic. There is no
application server, production build, combined Verify command, or CI workflow
yet.

## Conventions

- Python 3.10 or newer; use the `src/misdet/` package layout.
- Add type hints, keep functions focused, and use Ruff and Black.
- Store experiment settings in `configs/`; pass an explicit seed to every
  random operation.
- Keep the graph model, embeddings, detectors, baselines, and evaluation code in
  their respective `src/misdet/` packages.
- The positive evaluation class is a misconfiguration. Report minority-class
  precision, recall, and F1, plus PR-AUC and ROC-AUC where defined.
- Pin dependencies in `requirements.txt`. Ask before adding dependencies.

## Research and data safety

- Never put AWS credentials in code, logs, or commits. Do not run AWS CLI
  commands; use local files prepared by the project owner.
- Keep account-specific or otherwise sensitive data out of source control.
  Only synthetic benchmark data and sanitized public data may be committed.
- Never fit, scale, tune, threshold, or select embeddings using the locked test
  split.
- Generate reported metrics and figures from scripts. Do not hand-enter
  experiment results.
- Record assumptions and decisions in `docs/decisions.md`; do not present
  inferred paper parameters as reported paper settings.

## Testing

Test pure logic such as policy normalization, graph construction, split logic,
thresholding, and metric calculations. Cover malformed and empty inputs,
wildcard and `NotAction` cases, and deterministic behavior with a fixed seed.
Run `make test` and `make lint` after changes.
