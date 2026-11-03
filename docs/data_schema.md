# Data Schema

## Feature 1: normalized AWS-managed policies

Feature 1 reads a local JSON snapshot shaped like the `Policies` portion of
`get-account-authorization-details`. It uses each policy's default version and
does not call AWS or fetch data. The project owner supplies the source URL,
immutable revision, snapshot date, and license as CLI metadata.

The normalized dataset is UTF-8 JSON Lines: one record per policy, sorted by
`policy_id`. Duplicate IDs are rejected. No entity or attachment records are
produced; the synthetic benchmark feature supplies those later.

### Policy record

| Field | Type | Nullability | Contract |
|---|---|---|---|
| `policy_id` | string | non-null | Redacted `PolicyArn`; non-empty and unique. |
| `org` | null | always null | AWS-managed source policies are not assigned to a synthetic organization. |
| `source` | string | non-null | Always `aws_managed`. |
| `document` | object | non-null | Default-version document, preserving top-level fields such as `Version`. |

`document.Statement` is a non-empty array. Source statement ordering is
preserved. Policy documents may be JSON objects or URL-encoded JSON strings.

### Statement

Each statement is an object containing:

| Field | Type | Contract |
|---|---|---|
| `Effect` | string | Exactly `Allow` or `Deny`. |
| `Action` or `NotAction` | non-empty array of strings | Exactly one selector is present; values are lowercased and wildcards are not expanded. |
| `Resource` or `NotResource` | non-empty array of strings | Exactly one selector is present; values and wildcard semantics are preserved. |
| `raw_hash` | string | Lowercase SHA-256 hex of the redacted source statement before action normalization. |

`Principal`, `Condition`, `Sid`, and other source statement fields are
preserved as JSON values. In ARN-formatted strings, a 12-digit account-ID ARN
component is replaced with `REDACTED` throughout the policy identifier and
document. Other strings are preserved unchanged, including condition values
that happen to contain 12-digit text between colons. The normalized form is for
analysis and is not an executable IAM policy document.

For `raw_hash`, serialize the redacted source statement as UTF-8 JSON with
sorted keys, compact separators `,` and `:`, `ensure_ascii=False`, and no
non-finite numbers, then compute SHA-256. The `raw_hash` field is added after
hashing.

### Source manifest

Write `source_manifest.json` beside the JSONL output. It is deterministic JSON
with sorted keys, indentation of two spaces, and a final newline.

| Field | Type | Contract |
|---|---|---|
| `schema_version` | integer | Always `1`. |
| `source_url` | string | Required CLI provenance value. |
| `source_revision` | string | Required immutable source revision. |
| `snapshot_date` | string | Required ISO date in `YYYY-MM-DD` form. |
| `license` | string | Required license identifier or description. |
| `input_sha256` | string | Lowercase SHA-256 of the exact input file bytes. |
| `policies_sha256` | string | Lowercase SHA-256 of the exact normalized JSONL bytes. |
| `policy_count` | integer | Number of emitted policy records. |

No run timestamp is included, so identical input and metadata produce identical
outputs.

### Policy statistics

Write `policy_stats.json` beside the JSONL output, using the same deterministic
JSON formatting as the source manifest. It contains:

- `policy_count` and `statement_count` (integers).
- `action_pattern_count` (integer) and `wildcard_action_pattern_count`
  (integer), counting values from both `Action` and `NotAction`.
- `wildcard_action_pattern_share` (number), wildcard count divided by action
  pattern count.
- `action_patterns_per_policy` with numeric `min`, `median`, `mean`, and `max`.
- `services`, a mapping from lowercased service prefixes to integer pattern
  counts. Patterns without a service prefix, such as `*`, are omitted.

## Synthetic benchmark entities

Feature 2 defines and emits synthetic organization entity and attachment
records. Feature 1 intentionally does not create placeholder or empty entity
files.
