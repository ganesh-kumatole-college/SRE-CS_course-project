# Project Decisions

## Scaffold decisions

- **Project name:** Detecting Anomalous Misconfigurations in AWS IAM Policies.
- **Runtime:** Python 3.10 and newer, with the source package under `src/misdet/`.
- **Graph backend:** Neo4j with Graph Data Science is the planned primary path;
  NetworkX plus a Python Node2Vec implementation remains the documented
  fallback.
- **Local database:** Neo4j `2026.10.0`; its Docker plugin utility installs
  Graph Data Science. The compatibility matrix maps this server to GDS
  `2026.10`, but the utility does not pin the plugin artifact. Pin that artifact
  before recording experiments.
- **Embedding dimensions:** 128, as reported by the paper.
- **Initial walk settings:** `walk_length=80`, `walks_per_node=10`,
  `return_factor=1`, `in_out_factor=1`, and `window_size=10` are provisional
  Graph Data Science defaults, not values reported by the paper. Confirm and
  record the chosen values before experiments.
- **Dependencies:** direct dependencies are pinned in `requirements.txt`.
  Capture a fully resolved lock before publishing experiment results.
- **Results:** generated from scripts and stored with their configurations;
  never hand-enter metrics.

## Research protocol constraints

- Train detectors on verified normal policies. Keep the final test split locked
  away from fitting, embedding selection, tuning, and threshold calibration.
- Fit Node2Vec on training-normal policies and their connected graph context
  only. Infer a held-out policy vector by averaging the learned vectors of its
  adjacent non-policy context nodes that appeared during training; ignore
  unknown contexts and fail explicitly if none are available. This is a
  project-defined out-of-sample extension, not native inductive Node2Vec.
- Derive synthetic labels from documented templates and injection operators.
- Treat findings from synthetic organizations as a benchmark study, not as
  evidence of production AWS detection performance.
- The paper's parameters and results must be separated from project choices and
  inferred settings.

## Feature 5 evaluation protocol

- The main split is the paper-style 90/10 normal split: 90 percent of normal
  policies form the training pool, 10 percent of normals are locked in the test
  set, and all labelled misconfigurations are in the test set.
- Validation folds partition the training-normal pool. Each validation fold is
  scored by a detector fitted on the other training normals, so calibration
  does not score rows with the model that fitted them.
- The default threshold mode is calibrated at the 95th percentile of those
  held-out normal validation scores. The model's native prediction is retained
  as the paper-style alternative.
- Anomaly scores are normalized so larger values mean more anomalous for all
  four detectors: LOF, One-Class SVM, Isolation Forest, and Elliptic Envelope.
- Reported headline metrics treat `misconfiguration` as the positive class and
  include minority-class precision, recall, F1, PR-AUC, and ROC-AUC. Bootstrap
  intervals use a seeded 2,000-resample percentile procedure and skip invalid
  one-class resamples.

## To resolve before experiments

- Choose the public AWS-managed policy snapshot and record its source, date,
  commit or release, and license.
- Freeze the synthetic organization profiles and labeling rubric before
  generating evaluation labels.
- Confirm Node2Vec parameters and the faithful graph schema against the paper
  and the selected implementation.
- Select the data-split protocol, prevalence variants, validation threshold
  method, and locked test-set construction.
- Confirm the course's AI-use and source-code reuse rules with the instructor.

## Data acquisition

- **Policy source class:** use a public AWS-managed policy snapshot supplied as
  a local file. Do not use AWS credentials, AWS CLI commands, or agent-driven
  downloads.
- **Entity scope:** the public snapshot does not contain organization entity
  attachments. Feature 1 emits only normalized policy records; Feature 2
  generates the synthetic entities and attachments.
- **Exact source:** repository/URL, immutable revision, snapshot date, and
  license remain to be selected before acquiring or validating a real snapshot.
