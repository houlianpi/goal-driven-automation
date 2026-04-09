# Goal-Driven Automation Remediation Roadmap

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Restore the repository to a coherent, executable, and testable state by fixing the broken runtime path, unifying the plan contract, removing command-injection risks, and re-establishing trustworthy regression coverage.

**Architecture:** Treat the current failures as one system problem rather than isolated bugs. The target execution chain is `Goal -> Plan -> CompiledPlan -> RunEvidence`, with one authoritative `Plan IR` contract, one executor interface, and one safe command execution model. Security and contract consistency come before feature expansion.

**Tech Stack:** Python 3.13, pytest, JSON Schema, YAML registry, `fsq-mac` CLI, shell scripts.

## Execution Outcome

Execution of this roadmap was completed on 2026-04-09.

- Decision `D0` landed on `Option A`: semantic `Plan IR` actions remain authoritative and compile into registry-level capability actions.
- `WS1` through `WS7` were completed on the main remediation path.
- `P2` hygiene follow-up was partially completed for dependency management and script correctness.
- Final validation result: `pytest -q` -> `111 passed`.
- The previous `pytest-asyncio` warning was removed by adding explicit test configuration.

Key delivered outcomes:

- The duplicate `Pipeline` definition was removed, and the runtime path now executes compiled plans.
- `Executor` and `MockExecutor` now satisfy one runtime entrypoint contract through `execute(plan, run_id=None) -> RunEvidence`.
- `Plan IR` contract was unified across generator, compiler, schema, examples, docs, and tests.
- Shell-string execution was removed from the main execution path in favor of structured `argv` plus `shell=False`.
- Evaluator, repair-loop, and evidence state semantics were aligned around `SUCCESS`, `FAILURE`, `REPAIRED`, and `SKIPPED`.
- Evidence cloning and artifact serialization were fixed to avoid lossy copies and duplicate-artifact overwrite.
- `datetime.utcnow()` usage was replaced with timezone-aware UTC handling across the codebase.
- Integration coverage now includes a runtime pipeline regression test for success and repaired execution paths.

---

## Pre-P0 Decision Gate

This roadmap has one architectural decision that must be made before implementation starts.

### Decision D0: What is the authoritative `Plan IR` vocabulary?

- Option A: Keep schema-level semantic actions such as `launch`, `shortcut`, `click`, `assert`, and let the compiler map them to capability-layer actions.
- Option B: Expose registry-level actions such as `launch_app`, `hotkey`, and `assert_visible` directly in `Plan IR`.

**Recommended direction:**

- Choose Option A.
- Rationale: it preserves a clean separation between intent and capability execution, keeps `Plan IR` stable even if the registry evolves, and makes schema examples easier to review.

**Decision output required before implementation:**

- Record the chosen direction in this document or a short ADR.
- Do not begin `P0 Workstream 3` or `P0 Workstream 4` until D0 is settled.

**Decision status:**

- Approved on 2026-04-09.
- Selected direction: Option A.

---

## Context Summary

The current codebase has four structural blockers:

- `Pipeline` is defined twice in the same module, and the second definition silently overrides the first.
- The real execution path is broken: `Pipeline` calls a non-existent executor method and does not pass the compiled plan into execution.
- `Plan IR` is fragmented across generator, registry, schema, examples, and tests.
- Command execution uses string interpolation plus `shell=True`, which creates a command-injection surface.

Secondary issues are real but should follow after the main path is restored:

- Evaluator and repair-loop state semantics are inconsistent.
- Evidence cloning and artifact serialization are lossy.
- `datetime.utcnow()` is deprecated and produces naive UTC timestamps.
- Supporting scripts contain correctness and resilience problems.
- Dependency management and integration test coverage are under-defined.

Current observed validation baseline:

- `pytest -q` returns `5 failed, 80 passed, 107 warnings`
- The failures are concentrated in `tests/unit/test_pipeline.py` and `tests/unit/test_schema.py`

## Baseline Snapshot

Capture the pre-remediation baseline before changing code.

```bash
mkdir -p docs/plans/artifacts
pytest -q > docs/plans/artifacts/baseline-before-remediation.txt 2>&1
```

After each workstream, rerun the relevant test command and compare it with the baseline to confirm that failures only move in the expected direction.

## Delivery Principles

- Fix the runtime path before adding features.
- Define one source of truth for `Plan IR`.
- Replace shell-string execution with structured argument execution.
- Prefer small, reviewable commits per task.
- Add regression tests for every repaired contract.

## Phase Overview

### P0: Runtime and Contract Recovery

Objective:
Make the core pipeline executable and remove the highest-risk design flaws.

### P1: State Model and Evidence Reliability

Objective:
Make evaluation, repair, and evidence behavior internally consistent and reviewable.

### P2: Tooling, Hygiene, and Maintainability

Objective:
Remove avoidable operational debt once the product path is sound.

## Dependency Graph

Use these dependencies when sequencing or parallelizing work.

- `WS1 -> WS2`
  Reason: the retained `Pipeline` implementation determines the executor integration point.
- `D0 -> WS3`
  Reason: `Plan IR` vocabulary must be decided before contract repair starts.
- `WS2 + D0 + WS3 -> WS4`
  Reason: safe command execution depends on both executor interface shape and compiled plan structure.
- `WS2 -> WS5`
  Reason: state semantics depend on the unified executor return contract.
- `WS5 -> WS6`
  Reason: repair and evidence-copy behavior should follow the finalized state model.
- `WS1-WS6 -> WS7`
  Reason: integration and contract tests should validate the repaired design, not drive unresolved architecture decisions.

## Parallelization Guidance

- `WS1` and `WS3` may proceed in parallel after `D0`, as long as `WS3` does not depend on the duplicate `Pipeline` cleanup.
- `WS2` should follow `WS1`.
- `WS4` should wait for both `WS2` and `WS3`.
- `WS5` can begin after `WS2`.
- `WS6` should wait for `WS5`.
- `WS7` should be treated as integration and contract-test expansion, not as the first point where unit tests are updated.

---

## P0 Workstream 1: Recover a Single Pipeline Implementation

**Outcome:** Only one `Pipeline` class exists, and it uses one coherent execution path.

**Files:**
- Modify: `src/pipeline/pipeline.py`
- Test: `tests/unit/test_pipeline.py`

**Required changes:**

1. Delete the duplicate `Pipeline` class definition and keep one implementation only.
2. Make the retained implementation explicit about stage inputs and outputs.
3. Ensure `run()` passes `compiled` output, not raw `plan`, into the execute stage.
4. Fail loudly if a compiled plan is missing required execution fields.

**Acceptance criteria:**

- `src/pipeline/pipeline.py` contains one `Pipeline` class.
- `dry_run=False` no longer fails with `AttributeError` because of `Executor.execute()`.
- Pipeline stage results reflect the actual artifact flowing between stages.

**Validation commands:**

```bash
pytest tests/unit/test_pipeline.py -v
```

---

## P0 Workstream 2: Unify Executor Interface and Runtime Types

**Outcome:** Real and mock execution share one interface and one return contract.

**Files:**
- Modify: `src/executor/executor.py`
- Modify: `src/executor/mock_executor.py`
- Modify: `src/pipeline/pipeline.py`
- Modify: `src/evidence/storage.py`
- Modify: `src/demo.py`
- Test: `tests/unit/test_executor.py`
- Test: `tests/unit/test_pipeline.py`

**Required changes:**

1. Introduce one executor entrypoint, preferably `execute(plan, run_id=None) -> RunEvidence`.
2. Decide whether `PlanResult` survives as an internal helper or is removed.
3. Make `Executor` and `MockExecutor` interchangeable from the pipeline's point of view.
4. Align saved artifacts and run directories with the returned `RunEvidence` object.

**Design note:**

- If an abstract base class is introduced, keep it minimal: one method for plan execution and one stable return type.
- Avoid dual contracts where tests exercise a mock-only path that real execution cannot satisfy.
- `PlanResult` may remain as an internal execution artifact behind `execute_plan()`, but the current `execute()` adapter drops fields such as `failure_reason` when converting to `RunEvidence`. Treat that loss as an explicit temporary tradeoff and record it until the evidence model is expanded.

**Acceptance criteria:**

- `Pipeline` can be configured with either executor implementation without interface branching.
- Unit tests cover both success and failure paths using the shared contract.

**Validation commands:**

```bash
pytest tests/unit/test_executor.py tests/unit/test_pipeline.py -v
```

---

## P0 Workstream 3: Re-establish a Single `Plan IR` Contract

**Outcome:** Generator, schema, examples, registry, and tests all agree on one plan shape.

**Files:**
- Modify: `src/pipeline/plan_generator.py`
- Modify: `src/compiler/compiler.py`
- Modify: `src/schema/validator.py`
- Modify: `schemas/plan-ir.schema.json`
- Modify: `schemas/examples/edge-new-tab.plan.json`
- Modify: `schemas/examples/safari-navigate.plan.json`
- Modify: `registry/actions.yaml`
- Modify: `tests/unit/test_pipeline.py`
- Modify: `tests/unit/test_schema.py`
- Modify: `tests/unit/test_compiler.py`
- Modify: `docs/PLAN.md`
- Modify: `docs/SCHEMAS.md`

**Precondition:**

- `Decision D0` must be complete before this workstream starts.

**Required changes:**

1. Pick one vocabulary and encode it in schema, generator, compiler, examples, and tests.
2. Fix schema ambiguity in `params.oneOf`, which currently allows overlapping objects.
3. Make plan examples validate under the chosen contract.
4. Update tests to verify the chosen contract instead of stale action names.

**Acceptance criteria:**

- All plan examples validate.
- Generator output validates without ad hoc mutation.
- Compiler accepts only valid plan actions and fails clearly on invalid inputs.

**Validation commands:**

```bash
pytest tests/unit/test_schema.py tests/unit/test_compiler.py tests/unit/test_pipeline.py -v
```

---

## P0 Workstream 4: Remove Command-Injection Risk

**Outcome:** User-controlled text cannot alter shell structure during execution.

**Files:**
- Modify: `src/compiler/compiler.py`
- Modify: `src/executor/executor.py`
- Modify: `src/evidence/collector.py`
- Modify: `src/repair/strategies.py`
- Modify: `src/e2e_test.py`
- Modify: `src/demo.py`
- Test: `tests/unit/test_executor.py`
- Test: `tests/unit/test_evidence.py`
- Test: `tests/unit/test_repair.py`

**Required changes:**

1. Stop compiling steps into shell command strings as the execution primitive.
2. Compile into structured argv arrays, for example `['mac', 'app', 'launch', bundle_id]`.
3. Execute commands with `subprocess.run(argv, shell=False, ...)`.
4. Preserve a display-only rendered command if needed for logs and debugging.
5. Detect unresolved placeholders during compile and raise `CompilerError` immediately.

**Design note:**

- `shlex.quote()` is an acceptable short-term patch only if a full argv refactor is temporarily too large.
- The desired end state is `shell=False` everywhere on the main execution path.

**Acceptance criteria:**

- No production execution path relies on `shell=True` for compiled automation commands.
- Compiler rejects unresolved template placeholders.
- Tests include malicious-looking text payloads as regression coverage.

**Validation commands:**

```bash
pytest tests/unit/test_executor.py tests/unit/test_evidence.py tests/unit/test_repair.py -v
```

---

## P1 Workstream 5: Fix Evaluator and Repair State Semantics

**Outcome:** `SUCCESS`, `FAILURE`, `SKIPPED`, and `REPAIRED` have consistent meaning across evidence, evaluation, and repair.

**Files:**
- Modify: `src/evidence/types.py`
- Modify: `src/evaluator/evaluator.py`
- Modify: `src/evaluator/classifier.py`
- Modify: `src/repair/repair_loop.py`
- Modify: `src/repair/strategies.py`
- Test: `tests/unit/test_evaluator.py`
- Test: `tests/unit/test_repair.py`
- Test: `tests/unit/test_evidence.py`

**Required changes:**

1. Define whether `SKIPPED` counts as pass, fail, or separate outcome.
2. Define whether `REPAIRED` is a terminal success state or a subtype of pass.
3. Update evaluator summary logic to follow those semantics.
4. Ensure repair-loop outcomes and final evidence status cannot contradict evaluator output.
5. Remove placeholder classification behavior for successful steps.

**Acceptance criteria:**

- A repaired run does not later evaluate as failed for the same repaired step.
- A skipped step is reported consistently everywhere.
- Tests cover full-failure, partial-recovery, repaired-success, and skipped-step scenarios.

**Validation commands:**

```bash
pytest tests/unit/test_evaluator.py tests/unit/test_repair.py tests/unit/test_evidence.py -v
```

---

## P1 Workstream 6: Make Evidence Safe to Copy and Serialize

**Outcome:** Evidence snapshots are stable, and serialized artifacts do not lose information.

**Files:**
- Modify: `src/evidence/types.py`
- Modify: `src/repair/repair_loop.py`
- Modify: `src/evidence/storage.py`
- Test: `tests/unit/test_evidence.py`
- Test: `tests/unit/test_repair.py`

**Required changes:**

1. Replace shallow evidence cloning with deep cloning or explicit field-wise cloning.
2. Serialize artifacts as arrays of objects, not type-keyed maps that overwrite duplicates.
3. Rename `AssertionResult` to the correct spelling and update all references.
4. Add regression tests for multiple screenshots and cloned repair attempts.

**Acceptance criteria:**

- Repair attempts do not mutate original evidence objects unexpectedly.
- Multiple artifacts of the same type survive serialization and reload.

**Validation commands:**

```bash
pytest tests/unit/test_evidence.py tests/unit/test_repair.py -v
```

---

## P1 Workstream 7: Restore Trustworthy Test Coverage

**Outcome:** Cross-module integration tests and contract tests validate the repaired system, while unit tests are updated inside the workstreams that change behavior.

**Files:**
- Modify: `tests/unit/test_pipeline.py`
- Modify: `tests/unit/test_compiler.py`
- Modify: `tests/unit/test_executor.py`
- Modify: `tests/unit/test_evidence.py`
- Modify: `tests/unit/test_evaluator.py`
- Modify: `tests/unit/test_repair.py`
- Add: `tests/integration/test_pipeline_runtime.py`

**Required changes:**

1. Keep `WS1-WS6` responsible for updating their own affected unit tests.
2. Use `WS7` for new cross-module integration tests and explicit contract tests.
3. Add non-dry-run tests that exercise the real pipeline with a fake or mock executor under the shared contract.
4. Add contract tests proving generator output validates against schema.
5. Add security regression tests for command argument handling.
6. Add one integration test for `Goal -> Plan -> Compile -> Execute -> Evaluate` with deterministic mock execution.

**Acceptance criteria:**

- Unit tests cover the repaired core contracts.
- At least one integration test covers the full runtime chain without `dry_run=True`.

**Validation commands:**

```bash
pytest tests/unit -v
pytest tests/integration -v
```

---

## P2 Workstream 8: Replace Deprecated Time APIs

**Outcome:** All timestamps are timezone-aware and future-proof for Python 3.13+.

**Files:**
- Modify: `src/**/*.py` where `datetime.utcnow()` is used
- Modify: `scripts/**/*.py` where `datetime.utcnow()` is used
- Test: affected unit tests

**Required changes:**

1. Replace `datetime.utcnow()` with `datetime.now(timezone.utc)`.
2. Ensure serialized timestamps remain valid ISO 8601 strings.
3. Update any tests that assume naive datetimes.

**Validation commands:**

```bash
pytest -q
```

---

## P2 Workstream 9: Fix Supporting Script Correctness

**Outcome:** Developer scripts produce reliable results and fail predictably.

**Files:**
- Modify: `scripts/run_poc.sh`
- Modify: `scripts/annotate_screenshot.py`
- Review: `scripts/generate_report.py`
- Review: `scripts/generate_report_v2.py`
- Review: `scripts/generate_report_v3.py`
- Review: `scripts/generate_html_report.py`

**Required changes:**

1. Fix `run_poc.sh` so counters are updated in the parent shell.
2. Replace bare `except:` in `annotate_screenshot.py` with explicit exception classes.
3. Decide whether multiple report generators are intentional; if not, consolidate them.

**Validation commands:**

```bash
bash -n scripts/run_poc.sh
python3 scripts/annotate_screenshot.py --help
```

---

## P2 Workstream 10: Add Explicit Dependency Management

**Outcome:** The project can be installed and reproduced without guesswork.

**Files:**
- Add: `pyproject.toml`
- Optional: `requirements.txt`
- Modify: `README.md`

**Required changes:**

1. Declare runtime dependencies such as `PyYAML`, `jsonschema`, and `Pillow`.
2. Declare dev dependencies such as `pytest`.
3. Document setup and test commands in `README.md`.

**Acceptance criteria:**

- A new developer can install dependencies and run tests from documented steps alone.

---

## Recommended Execution Order

1. Capture the baseline snapshot.
2. Complete `Decision D0`.
3. `P0 Workstream 1` Recover a single pipeline implementation.
4. `P0 Workstream 2` Unify executor interface and runtime types.
5. `P0 Workstream 3` Re-establish a single `Plan IR` contract.
6. `P0 Workstream 4` Remove command-injection risk.
7. `P1 Workstream 5` Fix evaluator and repair semantics.
8. `P1 Workstream 6` Make evidence safe to copy and serialize.
9. `P1 Workstream 7` Restore trustworthy integration and contract coverage.
10. `P2 Workstream 8` Replace deprecated time APIs.
11. `P2 Workstream 9` Fix supporting script correctness.
12. `P2 Workstream 10` Add explicit dependency management.

## Rollback and Checkpoint Strategy

- Create a checkpoint commit at the end of each completed workstream.
- Create a lightweight tag after each passed gate, for example `remediation/gate-a`, `remediation/gate-b`, `remediation/gate-c`, `remediation/gate-d`.
- Do not begin the next dependent workstream until the current workstream's validation command passes.
- If `WS3` reveals that the selected `Decision D0` direction is not viable, stop and revert to the last successful checkpoint before trying the other option.
- Keep baseline outputs and post-workstream test outputs under `docs/plans/artifacts/` for comparison.

## Milestone Gates

### Gate A: Runtime Recovered

- One `Pipeline` implementation
- One executor interface
- No runtime `AttributeError` on the real pipeline path

### Gate B: Contract Recovered

- Generator output validates against schema
- Examples validate
- Compiler accepts the same action vocabulary that generator emits

### Gate C: Security Recovered

- Core execution path uses `shell=False`
- Placeholder leakage is rejected at compile time

### Gate D: Reviewable Quality Baseline

- `pytest tests/unit -v` passes
- `pytest tests/integration -v` passes
- Warnings reduced or explicitly triaged

## Final Validation Sweep

Run after all workstreams are complete:

```bash
pytest -q
```

If a local `fsq-mac` environment is available, add one manual smoke check:

```bash
python -m src.cli run "Open Edge and create new tab" --dry-run
```

And one non-dry-run scenario using the agreed safe executor path.

## Actual Completion Status

### Completed

- `WS1` Recover a single pipeline implementation.
- `WS2` Unify executor interface and runtime types.
- `WS3` Re-establish a single `Plan IR` contract.
- `WS4` Remove command-injection risk from the core execution path.
- `WS5` Fix evaluator and repair semantics.
- `WS6` Make evidence safe to copy and serialize.
- `WS7` Restore integration and contract coverage.
- `P2 Workstream 8` Replace deprecated time APIs.
- `P2 Workstream 10` Add explicit dependency management via `pyproject.toml`.
- Part of `P2 Workstream 9`: `scripts/annotate_screenshot.py` no longer uses bare `except:`.

### Deferred Or Partial

- `scripts/run_poc.sh` counter-fix was not completed in this remediation pass.
- Report-generator consolidation was intentionally deferred; the multiple report scripts remain in place.
- `README.md` setup documentation was not expanded in this pass.
- The compatibility typo around `AssertionResult` remains intentionally preserved through aliasing rather than a breaking rename.

### Residual Follow-up Candidates

- Consolidate report generation scripts into one supported entrypoint.
- Clean up empty placeholder packages and non-essential `.gitkeep` or empty `__init__.py` files where appropriate.
- Decide whether `README.md` should document installation and test flows now that `pyproject.toml` exists.
