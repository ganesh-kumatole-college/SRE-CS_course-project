# Detecting Anomalous Misconfigurations in AWS IAM Policies

Research scaffold for reimplementing an AWS IAM misconfiguration detector based
on policy graphs, Node2Vec embeddings, and anomaly detection. The repository
scaffold is in place; the data pipeline and experiments are future work.

The approach is evaluated as a reproducibility study with an open, synthetic
benchmark, stronger baselines, and analysis of failure cases. The source paper
uses private enterprise data, so its exact results cannot be reproduced from
the public paper alone.

## Getting started

1. Use Python 3.10 or newer.
2. Install the pinned project dependencies with `make setup`.
3. Run `make test` and `make lint`.
4. To use the optional local Neo4j graph database, copy `.env.example` to `.env`,
   set a local password, and run `make neo4j-up`.
5. Run `make smoke-gds` to verify the local Graph Data Science Node2Vec
   procedure. The script prompts for the Neo4j password if it is not set in the
   environment.

## Commands

- `make setup` - install the project and pinned dependencies.
- `make test` - run the unit tests.
- `make lint` - run Ruff.
- `make format` - format Python files with Black.
- `make neo4j-up` / `make neo4j-down` - start or stop local Neo4j.
- `make smoke-gds` - run a small Node2Vec integration check against Neo4j.
