# Batch Execution

## Purpose

Batch execution lets an upper-layer coding agent run one `case` or expand a `suite` into multiple case runs while keeping the repository focused on execution and evidence.

## Commands

- `python3 -m src.cli run-case <path>` runs one case asset.
- `python3 -m src.cli run-suite <path>` resolves suite membership and runs each referenced case.

## Agent Workflow

- Choose a `case` when the user asks for one concrete automation scenario.
- Choose a `suite` when the user asks for a grouped smoke run or a tagged batch.
- Summarize results back to the user in terms of case ids, run status, and evidence location.

## Evidence Location

Each case run still writes evidence through the normal pipeline under `data/runs/`. A suite command is a thin orchestration layer over multiple case runs, not a separate execution engine.

## Current Contract

The first version supports explicit suite membership through `cases`. It does not add a job queue, cross-case retry policy, or advanced scheduling.
