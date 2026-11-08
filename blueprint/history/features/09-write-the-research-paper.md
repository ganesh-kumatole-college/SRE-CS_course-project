# Feature: Write the Research Paper

**From build-plan:** feature 9
**Build attempt:** 1
**Status:** verified
**Branch:** feature/write-the-research-paper

<!-- Archive annotation -->
<!-- Original HEAD: 982f603a11976a1ee5c3f9a764d84f880a221f7e -->
<!-- Local base (main): 982f603a11976a1ee5c3f9a764d84f880a221f7e -->

## Goal

Produce a complete, publication-quality research paper in `paper/` conforming to
the Phase 11 specification in `detailed-plan.md`. The paper documents the open
IAM misconfiguration benchmark, independent reproduction of the graph-embedding
anomaly detection method, baseline comparisons, ablation findings, and
per-operator failure analysis. All empirical claims, numbers, tables, and figures
are derived strictly from generated artifacts (`results/smoke/`, `docs/claims.md`,
and `docs/decisions.md`).

## What was built

- `paper/main.tex` — Master two-column IEEEtran LaTeX document assembling all modular sections.
- `paper/sections/` — 9 structured section files:
  - `01_introduction.tex` — Motivation, cloud IAM security challenges, limitations of static analysis, and 4 contributions.
  - `02_background.tex` — AWS IAM policy JSON grammar, Node2Vec random walk mechanics, and LOF outlier density equations.
  - `03_related_work.tex` — Static linters (Cloud Custodian), formal SMT provers (Zelkova), reactive auditing (CloudTrail), and graph learning for access control.
  - `04_approach.tex` — Heterogeneous Entity-Policy-Action-Resource graph schema, leak-free out-of-sample projection, and validation-calibrated thresholding.
  - `05_benchmark.tex` — Organization profiles (`alpha`, `beta`, `gamma`), P1–A3 mutation operators, hard negatives, and dataset statistics.
  - `06_evaluation_setup.tex` — RQ1–RQ4 definitions, baselines, minority-class metrics (positive = misconfiguration), and locked test split protocol.
  - `07_results.tex` — Empirical results embedding generated tables (T2, T3, T4, T6) and referencing vector figures (F4–F7).
  - `08_discussion.tex` — Condition-block blindness, operational alert fatigue mitigation in DevSecOps/SRE, and threats to validity.
  - `09_conclusion.tex` — Summary of takeaways, hybrid posture guidance, and future directions.
- `paper/references.bib` — 12 authentic, verified BibTeX citations for foundational literature.
- `paper/paper.md` — Full-length standalone Markdown paper with all sections, tables, equations, and references.
- `tests/test_paper.py` — 4 automated consistency tests validating BibTeX key uniqueness, citation integrity, asset existence, and document completeness.

## Verify

`make test && make lint` — 111 passed, 0 lint errors.

## Findings

### 9/F-01 [P2] open — GDS resource cleanup is not asserted by tests

**File:** tests/test_embed.py:156,217
**Found:** 2026-11-04 by /audit (scope: current; lens: quality, security, performance, tests)
**Why it matters:** The feature requires temporary GDS graph and Neo4j data to
be cleaned up on both success and failure. The GDS tests assert result mapping,
failure propagation, and driver closure, but do not assert that the graph-drop
and node-delete cleanup queries ran. A cleanup regression could therefore pass
the current unit tests and leave temporary resources behind.
**Suggested fix:** Assert that the fake session observed both cleanup queries
after successful embedding and after a post-projection failure.
**Resolution:** Carried forward — open at completion of feature 9. Originated
in feature 4; not in scope for this feature.

## Try it now

```bash
# Read the complete standalone Markdown paper:
cat paper/paper.md

# Verify paper consistency and all test suites:
make test && make lint
```
