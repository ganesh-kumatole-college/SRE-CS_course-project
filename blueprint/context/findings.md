# Findings

> **Generated file.** The findings ledger: review findings raised by `/audit`
> against the work in progress, each with a durable ID, severity (P0-P3), and
> status. `/implement` marks repaired findings `fixed`, a later `/audit` pass
> moves them to `closed`, and `/complete` refuses to land while any P0 or P1
> finding is `open` or `fixed`, then archives resolved findings with the work
> and resets this file.

### F-01 [P2] open - GDS resource cleanup is not asserted by tests

**File:** tests/test_embed.py:156,217
**Found:** 2026-11-04 by /audit (scope: current; lens: quality, security, performance, tests)
**Why it matters:** The feature requires temporary GDS graph and Neo4j data to be cleaned up on both success and failure. The GDS tests assert result mapping, failure propagation, and driver closure, but do not assert that the graph-drop and node-delete cleanup queries ran. A cleanup regression could therefore pass the current unit tests and leave temporary resources behind.
**Suggested fix:** Assert that the fake session observed both cleanup queries after successful embedding and after a post-projection failure.
**Resolution:**
