# Run Result Model

## Purpose

An upper-layer coding agent needs a stable summary object for each run so it can report outcomes without scraping verbose terminal output.

## Stable Summary Fields

The repository should expose a `run_summary` shape with:

- `run_id`
- `final_status`
- `success`
- `passed_steps`
- `failed_steps`
- `partial_steps`
- `artifact_dir`

These fields are intended for agent consumption and should stay additive and stable.

## Diagnostic Fields

The broader pipeline payload may still include detailed stage data, parsed goal data, evaluation details, and evidence references. Those are useful for debugging, but the upper-layer agent should prefer `run_summary` first when preparing a user-facing reply.

## Batch Aggregation

For suite execution, aggregate multiple `run_summary` objects rather than attempting to merge full verbose payloads. A batch summary should report which cases succeeded, which failed, and where evidence for each run was written.
