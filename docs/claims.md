# Claims to Evidence

Each row maps one intended paper claim to its evidence file, figure or table,
and confidence level. Fill in the Evidence and Verdict columns from the
generated outputs before writing the paper.

| Claim | Evidence file | Figure/Table | Confidence | Notes |
| ----- | ------------- | ------------ | ---------- | ----- |
| LOF achieves higher precision than baselines on org alpha | results/smoke/tables/t2_main_comparison.csv, results/smoke/tables/t3_detector_comparison.csv | T2, T3 | | |
| Node2Vec recall exceeds hand-crafted features on hard operators | results/smoke/tables/t4_ablation.csv | T4, F6 | | |
| Easy operators (P1-P2) are detected reliably; hard operators (P4-P6) are missed | results/smoke/exp13/alpha/0/grouped_recall.json | F4, T6 | | |
| Contamination degrades recall for Isolation Forest more than LOF | results/smoke/tables/t4_ablation.csv, results/smoke/exp04/summary.json | F7 | | |
| Paper trend (LOF competitive with other detectors) reproduced / not reproduced | results/smoke/tables/t5_paper_vs_ours.csv | T5 | | |
