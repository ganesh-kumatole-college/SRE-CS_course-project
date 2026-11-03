# Build Plan

Proposed feature order adapted from Phases 3-12 in the supplied root
`project-plan.md`. The detailed source plan ends during Phase 4, so later
features are provisional high-level milestones, not complete specifications.
Review the scope and order before using `/feature`.

## Your features

- [x] 1. **Acquire and normalize IAM policy data** - define canonical policy and entity inputs, normalize approved AWS-managed policy snapshots, and document their provenance.
- [ ] 2. **Generate the labelled synthetic benchmark** - create three organization profiles, policy templates, misconfiguration injections, and deterministic ground-truth labels.
- [ ] 3. **Build the IAM policy graph** - implement the paper's entity, policy, action, and resource relationships, with a NetworkX fallback; detailed design is **TODO**.
- [ ] 4. **Embed policy nodes with Node2Vec** - produce 128-dimensional policy representations and record chosen graph and walk settings; the implementation protocol is **TODO**.
- [ ] 5. **Implement anomaly detectors and evaluation** - train on normal policies and evaluate held-out cases with leakage-safe splits and documented metrics; exact protocol is **TODO**.
- [ ] 6. **Compare rule-based and feature-based baselines** - evaluate Cloud Custodian or an equivalent rule baseline alongside heuristic and hand-crafted-feature baselines; scope and tooling are **TODO**.
- [ ] 7. **Run the reproduction and robustness experiments** - implement selected paper analogues, ablations, and robustness studies with a locked test set; experiment specifications are **TODO**.
- [ ] 8. **Analyze results and failure cases** - generate result tables and figures, inspect errors by misconfiguration type, and document limitations; analysis requirements are **TODO**.
- [ ] 9. **Write the research paper** - present the reimplementation, benchmark contribution, evaluation, and limitations; course format and acceptance criteria are **TODO**.
- [ ] 10. **Package the reproducible deliverables** - document setup and reproduction, finalize source and data licensing, and prepare any required demo or viva material; submission requirements are **TODO**.
