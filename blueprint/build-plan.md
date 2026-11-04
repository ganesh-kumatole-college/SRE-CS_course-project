# Build Plan

Detailed phase tasks, experiment definitions, risks, and paper guidance are in
the local [`detailed-plan.md`](../detailed-plan.md). Feature IDs and order below
remain stable; Feature 1 maps to completed Phase 3 and Features 2–10 map to
Phases 4–12. Each `/feature` spec selects the bounded scope for its next item.
MUST scope is expected; SHOULD/COULD work is optional and requires explicit
inclusion in the relevant feature spec.

## Your features

- [x] 1. **Acquire and normalize IAM policy data** - Phase 3: define the canonical policy contract, normalize a locally supplied approved AWS-managed snapshot, preserve provenance, and report deterministic statistics. No AWS CLI or agent-driven downloads.
- [x] 2. **Generate the labelled synthetic benchmark** - Phase 4: freeze a labeling rubric; generate three distinct organization profiles, custom policy templates, entities/attachments, hard negatives, and traceable P1–A3 injection labels deterministically. MUST.
- [ ] 3. **Build the IAM policy graph** - Phase 5: implement the faithful Entity–Policy–Action–Resource graph, idempotent Neo4j loading and NetworkX fallback, incremental updates, validation/export, and example graph. Statement-scoped graph is SHOULD.
- [ ] 4. **Embed policy nodes with Node2Vec** - Phase 6: produce configured 128-dimensional policy embeddings through GDS or the Python fallback, with seeded sanity, stability, timing, and visualization checks. Parameter sensitivity is SHOULD.
- [ ] 5. **Implement anomaly detectors and evaluation** - Phase 7: implement LOF, One-Class SVM, Isolation Forest, and Robust Covariance; leakage-safe splits, train-only fitting/tuning/calibration, metrics, bootstrap intervals, and run records. MUST.
- [ ] 6. **Compare rule-based and feature-based baselines** - Phase 8: evaluate random/prevalence, wildcard, permissiveness, hand-crafted-feature, and offline Cloud Custodian or clearly labelled equivalent baselines on matching splits. Bag-of-actions is SHOULD; extra tools/embeddings are COULD.
- [ ] 7. **Run the reproduction and robustness experiments** - Phase 9: script the paper analogues, Node2Vec ablation, and per-type/difficulty analyses with locked tests, 30 seeded repetitions, raw counts, intervals, and reproducible run artifacts. EXP-01–04, 07, and 13 are MUST; remaining experiments follow the detailed plan's SHOULD/COULD priorities.
- [ ] 8. **Analyze results and failure cases** - Phase 10: create claims-to-evidence records, per-organization false-positive/negative analysis, workload views, paper-comparison verdicts, and reproducible figures/tables.
- [ ] 9. **Write the research paper** - Phase 11 (parallel where evidence permits): document method, benchmark, evaluation, results, threats to validity, limitations, and verified references; use generated results only and follow confirmed course requirements.
- [ ] 10. **Package the reproducible deliverables** - Phase 12: verify clean-environment reproduction, document data/licensing and AI use, remove sensitive material, and prepare required release, paper, slides, demo, or viva artifacts.
