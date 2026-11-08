# Detecting Anomalous Misconfigurations in AWS IAM Policies - Project Overview

<!-- blueprint:source-hash 1fdd4fdadb629eda4e9c82cb760417fb33c52e5675f8618912858c9181637653 -->

> A reproducible research pipeline for detecting anomalous AWS IAM policies with graph embeddings.

## Problem

AWS IAM policies change over time, and accidentally permissive, restrictive, or
misattached policies can go unnoticed. This course project independently
implements the graph-embedding anomaly detector from van Ede et al. and
evaluates it on an open synthetic benchmark. The original paper's enterprise
data is private, so exact reproduction of its measurements is not possible.

## Users

- **Student author:** builds and evaluates the method for a course research
  project.
- **Instructors and reviewers:** assess the implementation, benchmark,
  reproducibility, and limitations.
- **Future researchers:** may reuse the documented synthetic benchmark.

This is a research pipeline, not a production AWS security service.

## Usage model

- Experiments are intended for laptop-scale local execution; exact hardware and
  runtime targets are **TODO**.
- Prefer synthetic policy data and sanitized public AWS-managed policy
  snapshots. Account data is sensitive and must stay local unless sanitized and
  approved.
- Never give AWS credentials to agents or commit credentials. AWS collection,
  if used, is performed by the project owner.
- Keep the test split out of fitting, scaling, thresholding, and
  hyper-parameter selection. Use explicit seeds and generate reported results
  from scripts.
- Synthetic results do not establish production AWS detection performance.
  Exact reproduction on the paper's private data is out of scope.
- Course AI-use, code-reuse, deadline, paper-format, page-limit, and viva
  requirements remain **TODO**.

## Features

1. **Acquire and normalize IAM policy data** - define canonical inputs,
   normalize approved AWS-managed policy snapshots, and record provenance.
2. **Generate the labelled synthetic benchmark** - create three organization
   profiles, policy templates, injection operators, and deterministic labels.
   This is the project's main planned data contribution.
3. **Build the IAM policy graph** - represent entities, policies, actions, and
   resources, with a NetworkX fallback; detailed design is **TODO**.
4. **Embed policy nodes with Node2Vec** - produce 128-dimensional policy
   vectors and record graph and walk settings; exact protocol is **TODO**.
5. **Implement anomaly detectors and evaluation** - train on normal policies
   and evaluate held-out cases; exact split and threshold protocol is **TODO**.
6. **Compare rule-based and feature-based baselines** - compare Cloud
   Custodian or an equivalent rule baseline with heuristic and
   hand-crafted-feature baselines; scope and tooling are **TODO**.
7. **Run reproduction and robustness experiments** - implement selected paper
   analogues, ablations, and robustness studies with a locked test set;
   experiment specifications are **TODO**.
8. **Analyze results and failure cases** - generate tables and figures, inspect
   errors by misconfiguration type, and document limitations; analysis
   requirements are **TODO**.
9. **Write the research paper** - present the reimplementation, benchmark,
   evaluation, and limitations; course format and acceptance criteria are
   **TODO**.
10. **Package the reproducible deliverables** - document setup and reproduction,
    finalize source and data licensing, and prepare required demo or viva
    material; submission requirements are **TODO**.

## Data model

### IAM policy

- `policy_id` (string) - identifier referenced by benchmark labels.
- `org` (string) - synthetic organization when applicable.
- `source` (string) - planned values `aws_managed` or `synthetic_custom`.
- `document` (JSON object) - IAM policy document with statements. AWS statement
  concepts include `Effect`, `Action` or `NotAction`, `Resource` or
  `NotResource`, `Principal`, and `Condition`.
- relationship to one or more **statements**, and, when attached, to an
  **entity**.

The canonical normalized fields, nullability, and statement representation are
**TODO**; the supplied root plan refers to a data-schema appendix that is not
present in that file.

### Entity

- `entity_id` (string) - identifier for an organization user, group, or role.
- `entity_type` (string) - user, group, or role.
- relationship to policies through an `ATTACHED_TO` edge.

The canonical entity fields and attachment representation are **TODO**.

### Policy graph

- Node types: entity, policy, action, and resource.
- Relationships: `(Entity)-[ATTACHED_TO]->(Policy)`,
  `(Policy)-[ALLOWS|DENIES]->(Action)`, and
  `(Action)-[WORKS_ON]->(Resource)`.
- This is the paper's faithful schema. A statement-scoped graph is an optional
  planned ablation, not the default.

### Benchmark label

The planned `labels.csv` row contains `policy_id` (string), `org` (string),
`label` (string), `misconfig_type` (string), `operator_id` (string),
`difficulty` (string), `hard_negative` (boolean), `attached_entity_id`
(string, when applicable), `source` (string), and `rationale` (string).
Labels cover normal and permissive/restrictive policy cases, plus
attachment-level misconfigurations. Exact row/nullability semantics are
**TODO**.

### Embedding and experiment run

- Each policy embedding is a 128-dimensional vector; the embedding backend,
  configuration, and persistence format remain **TODO**.
- Planned run artifacts are `config.yaml`, `metrics.json`, `preds.csv`,
  `env.txt`, and `git_sha.txt`. Their internal schemas are **TODO**.

Lock these schemas before implementing the dependent pipeline and benchmark
features.

## Tech stack

- **Python 3.10+ and `src/misdet/`** - research code and scripts.
- **Neo4j with Graph Data Science** - planned primary graph and Node2Vec path.
- **NetworkX and Python Node2Vec** - documented fallback.
- **scikit-learn** - LOF and comparisons with three other anomaly detectors.
- **pytest, Ruff, Black** - tests, lint, and formatting.
- **YAML and explicit random seeds** - experiment configuration and
  reproducibility.

The paper specifies 128 embedding dimensions, but not most Node2Vec walk
parameters. Scaffold defaults are provisional; confirm and record chosen
settings before experiments.

## Monetization

Not applicable; this is a course research project, not a commercial product.

## UI/UX

No graphical interface is planned. The user-facing workflow is local scripts
that produce machine-readable experiment outputs and paper figures. Whether a
demo interface is required by the course is **TODO**.

## Deployment

No hosted deployment is planned. Run experiments locally; Neo4j is optional
local infrastructure managed through Docker Compose. Final outputs are the
source repository, benchmark, reproducible experiment artifacts, and course
paper. Course submission and hosting expectations are **TODO**.

## Open questions

- The supplied root `project-plan.md` stops during Phase 4 even though its
  overview lists Phases 5-12. Add detailed scope and done-when criteria for the
  graph, embedding, detectors, baselines, experiments, analysis, paper, and
  packaging work before specifying those features.
- Define the canonical policy, statement, entity, attachment, graph, embedding,
  split, label-row, and experiment artifact schemas.
- Confirm the public policy snapshot, source, date, and license.
- Freeze the synthetic labeling rubric and organization profiles before
  experiments; settle the split, threshold calibration, seeds, and selected
  reproduction experiments.
- Resolve the course deadline, AI-use and source-reuse policy, paper format,
  page limit, and demo/viva requirements with the instructor.
