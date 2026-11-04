# Fix: Leakage-safe Node2Vec embeddings

**Type:** Fix
**Status:** verified
**Branch:** `fix/leakage-safe-out-of-sample-node2vec-embeddings`

## The problem

Both Python and GDS Node2Vec currently fit on every policy in the supplied graph.
That allows held-out policies to influence embeddings used for anomaly evaluation,
contrary to the locked-test protocol.

## The fix

Require an explicit set of training-normal policy IDs for both backends. Fit
Node2Vec only on those policies and the context graph connected to them; exclude
all inference policies from fitting. For each inference policy, calculate its
vector as the arithmetic mean of learned vectors for its adjacent non-policy
context nodes that were present during training. Ignore unknown context nodes and
raise a clear error if no trained context vector is available. Preserve the
existing matrix-and-policy-IDs return shape, deterministic seed behavior, and
Python fallback for GDS when no connection is configured. Record this
out-of-sample method as a project decision; it must not fit or tune on inference
policies.

## Build steps

1. [x] Update both embedding backends and their tests to fit only on explicit
   training-normal IDs and infer held-out vectors using the shared context
   embeddings. Add deterministic and leakage-isolation tests, including
   inference policies with no known context. **Done when** neither backend's
   fitted vectors depend on inference-only policies, both return the expected
   policy IDs and matrix shape, and unsupported inference raises an actionable
   error.
2. [x] Record the chosen out-of-sample method in `docs/decisions.md`.
   **Done when** the decision and its limits are documented.

## Verify

- Run the embedding tests, then `make test` and `make lint`.
- Confirm tests prove inference-only policies are excluded from fitting and
  receive vectors only through the defined context aggregation.


<!-- blueprint:completion {"schemaVersion":2,"specBytes":1914,"specSha256":"01e37b77b29f7a5eb6ae3682e1bb1487089dca416c2c6924d4f1e733572e9c55","branch":"refs/heads/fix/leakage-safe-out-of-sample-node2vec-embeddings","head":"dec7418ff972b7da3f399490a8bbc94c10b306fc","baseRef":"refs/heads/main","baseCommit":"dec7418ff972b7da3f399490a8bbc94c10b306fc","sourceTree":"2d2489009afd5074fd4ce82a6d39da2137d0dc77","landing":"local-merge","absentOptional":[]} -->

## Try it now

Run or do:

```bash
source .venv/bin/activate
python - <<'PY'
from misdet.embed import embed_policy_nodes
from misdet.graph import build_policy_graph

policies = [
    {
        "policy_id": "normal",
        "document": {"Statement": [{"Effect": "Allow", "Action": ["s3:GetObject"], "Resource": ["arn:aws:s3:::example/*"]}]},
    },
    {
        "policy_id": "heldout",
        "document": {"Statement": [{"Effect": "Allow", "Action": ["s3:GetObject"], "Resource": ["arn:aws:s3:::other/*"]}]},
    },
]
graph = build_policy_graph(policies)
vectors, policy_ids = embed_policy_nodes(
    graph,
    training_policy_ids=["Policy:normal"],
    config={"dimensions": 8, "walk_length": 8, "walks_per_node": 2, "seed": 7},
)
print(policy_ids, vectors.shape)
PY
```

Expected:

```text
['Policy:heldout', 'Policy:normal'] (2, 8)
```

This proves a held-out policy can receive an embedding when it shares context with a training policy; it does not verify evaluation-split selection.
