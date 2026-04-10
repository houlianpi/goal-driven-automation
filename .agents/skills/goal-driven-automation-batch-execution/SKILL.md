---
name: goal-driven-automation-batch-execution
description: Use when a coding agent needs to choose between case and suite execution, run them, and summarize evidence-backed results for users.
---

# Goal-Driven Automation Batch Execution

## Choose The Right Entry Point

- Use `run-case` for one concrete automation scenario
- Use `run-suite` for a grouped smoke or batch workflow
- Use plain `run` only when there is no persisted `case` asset yet

## Commands

- `python3 -m src.cli run-case <path>`
- `python3 -m src.cli run-suite <path>`

## How To Summarize Results

When replying to users, summarize in terms of:

- case id or suite id
- run result status
- run id
- artifact location

For suite runs, list failed cases directly instead of dumping raw console output.

## Evidence Paths

Per-run evidence is stored under `data/runs/<run_id>/`.

Important files:

- `evidence.json`
- `input_plan.json`

## Reporting Guidance

- Prefer short summaries with concrete case ids and statuses
- Reference evidence paths when the user needs follow-up debugging
- Distinguish a failed `case` from a failed `suite` aggregate
