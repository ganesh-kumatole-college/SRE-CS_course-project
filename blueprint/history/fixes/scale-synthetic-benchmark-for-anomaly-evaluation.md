# Fix: Scale synthetic benchmark for anomaly evaluation

**Type:** Fix
**Status:** verified
**Branch:** fix/scale-synthetic-benchmark-for-anomaly-evaluation

## The problem

The generator currently creates only 18 policies, with four rows labeled
normal. Worse, `inject_misconfigurations` modifies every generated policy,
including rows labeled normal. This benchmark cannot support the planned
90/10 normal split, validation-only threshold calibration, or 128-dimensional
Robust Covariance detector.

## The fix

Generate 380 policies per organization: 350 normal and 30 misconfigured
policies. This preserves the detailed plan's 5-8% misconfiguration prevalence
and 30-60 positive examples per organization, while leaving 315 normal training
rows after the planned 90/10 split. Five-fold normal-only calibration retains
about 63 validation normals per fold, with enough training samples for the
128-dimensional Robust Covariance detector.

Apply injection operators only to positive rows, and derive labels from the
operator actually applied. P1 and P2 are permissive operators; A3 must also
change the policy attachment to a different entity in the same organization.
Preserve deterministic generation with an explicit seed, the existing
organization/operator constraints, and meaningful variation in normal policy
documents beyond IDs and statement Sids. Keep the existing label schema and
top-level generator interface; add no dependency or configuration surface.

## Build steps

- [x] Update synthetic policy generation, injection, labels, and focused tests.
  **Done when:** a fixed seed reproducibly yields 350 structurally varied
  normal policies and 30 misconfigurations per organization; normal
  policies remain uninjected; P1/P2 are labeled permissive and A3 policies are
  attached to a different same-organization entity; labels match the applied
  operators; P1, P2, and A3 are represented; and `make test` and `make lint`
  pass.

## Files / areas

- `src/misdet/synth/generator.py`
- `src/misdet/synth/templates.py`
- `src/misdet/synth/injector.py`
- `src/misdet/synth/labels.py`
- `tests/test_synth.py`

## Verify

- Run `make test` and `make lint`.
- Test deterministic counts and labels for each organization, positive operator
  coverage, structural diversity, the A3 attachment change, and that normal
  policy documents are not modified by injection.


<!-- blueprint:completion {"schemaVersion":2,"specBytes":2377,"specSha256":"41ce8c64a25f481ea0e3c1c27b4de980f009465f16a191d5bddafa6a54e243be","branch":"refs/heads/fix/scale-synthetic-benchmark-for-anomaly-evaluation","head":"bcdf8316ef14354555a2fc96b0423893b8e2136b","baseRef":"refs/heads/master","baseCommit":"bcdf8316ef14354555a2fc96b0423893b8e2136b","sourceTree":"b853b390ee7bb43fd17b12c53435e9ccdfcaae76","landing":"local-merge","absentOptional":[]} -->

## Try it now

Run or do:

From the repository root with the project environment activated, run:

```bash
python -c 'from collections import Counter; from misdet.synth.generator import generate_benchmark; b = generate_benchmark(seed=42); [(lambda c, org: print(f"{org}: {c[0]} normal, {c[1]} misconfigured"))(Counter(row["label"] for row in b["labels"] if row["org"] == org), org) for org in sorted(b["org_profiles"])]'
```

Expected:

```text
alpha: 350 normal, 30 misconfigured
beta: 350 normal, 30 misconfigured
gamma: 350 normal, 30 misconfigured
```

This proves:

The generator produces deterministic per-organization normal and
misconfiguration counts for the selected seed.
