# Test Suite Model

## What A Suite Is

A `suite` is a batchable collection of test cases. It exists so an upper-layer coding agent can run a meaningful group of cases and summarize the result as one run-oriented workflow.

## Required Fields

- `id`: stable identifier such as `suite-smoke-core`
- `title`: short human-readable name
- `cases`: explicit list of case ids included in the suite

## Optional Fields

- `tags`: suite-level labels for discovery and reporting
- `selection`: future-facing tag-based selection metadata
- `enabled`: whether the suite should be available for execution

## Case Vs Suite

- A `case` defines one user-facing test intent.
- A `suite` groups multiple cases for batch execution and reporting.

In this pass, suites are intentionally simple and center on explicit case references. More advanced execution policy should stay out until the batch execution contract is in place.
