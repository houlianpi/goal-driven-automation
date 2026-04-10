---
name: goal-driven-automation-test-authoring
description: Use when a coding agent needs to create or update user-facing case and suite assets for this repository.
---

# Goal-Driven Automation Test Authoring

## Goal

Create reviewable, user-facing automation assets that match the repository contract.

## Case Authoring Rules

Create `case` assets under `data/cases/` using the `schemas/test-case.schema.json` contract.

Required fields:

- `id`
- `title`
- `goal`
- `tags`
- `apps`

Guidelines:

- Use stable ids such as `case-open-edge`
- Keep `goal` in natural language at the user-intent level
- Use `tags` for grouping and filtering
- Set `apps` explicitly when the app is known

## Suite Authoring Rules

Create `suite` assets under `data/suites/` using the `schemas/test-suite.schema.json` contract.

Guidelines:

- Prefer explicit `cases` membership in the first version
- Use suites to group related cases for smoke or batch runs
- Keep suite metadata simple and reviewable

## What To Avoid

- Do not leak low-level engine commands into user-facing `goal` fields
- Do not model repository unit tests as user-facing cases
- Do not promise unsupported execution policy inside suite assets

## Validation

- Validate new assets against the repository schema contract
- Keep examples under `data/cases/examples/` and `data/suites/examples/` when adding reference assets
