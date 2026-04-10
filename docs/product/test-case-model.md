# Test Case Model

## What A Case Is

A `case` is the smallest user-facing automation asset in this repository. It describes one intent-level test goal that an upper-layer coding agent can create, edit, run, and report on.

## Required Fields

- `id`: stable identifier such as `case-open-edge`
- `title`: short human-readable name
- `goal`: natural-language goal to send into the execution pipeline
- `tags`: labels for filtering and suite composition
- `apps`: apps touched by the case

## Optional Fields

- `priority`: reporting or scheduling hint
- `owner`: ownership metadata
- `enabled`: whether the case is available for execution

## Agent Guidance

When creating a new case, the coding agent should:

- keep `goal` at user-intent level instead of embedding low-level steps
- choose stable, reviewable ids
- use tags for grouping and reporting, not for core execution semantics
- list the affected apps explicitly when known

This contract intentionally stays small in the first pass. It defines a user-facing asset shape without introducing a step-level DSL.
