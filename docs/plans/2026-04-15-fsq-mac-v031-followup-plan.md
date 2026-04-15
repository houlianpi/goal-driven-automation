# fsq-mac v0.3.1 Follow-Up Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Complete the remaining post-compatibility work so GDA not only runs against `fsq-mac` `v0.3.x`, but also repairs failures according to the upstream playbook, validates its registry against the upstream contract in CI, and captures richer structured execution evidence.

**Architecture:** Keep the current `plan -> compile -> execute -> evaluate -> repair` pipeline intact. Implement the highest-value missing behavior first in the repair layer, then tighten registry drift controls around `docs/agent-contract.json`, then enrich executor evidence so future repair logic can consume stable structured success payloads instead of raw stdout blobs.

**Tech Stack:** Python 3.13, pytest, YAML registry, JSON envelope parsing, fsq-mac `docs/agent-contract.json`, fsq-mac `docs/agent-playbook.md`.

---

## Scope and Current Baseline

Already complete enough to build on:

- Runtime command compatibility for `fsq-mac v0.3.x`
- Structured `ok` / `error.code` envelope parsing in the executor
- Initial registry validation helper
- Unit coverage for compiler, executor, evaluator, and pipeline compatibility paths

Still missing or only partially implemented:

- Full playbook-aligned repair behavior for `ELEMENT_NOT_FOUND`, `ELEMENT_REFERENCE_STALE`, and backend failures
- Registry governance that treats upstream contract drift as a validation failure in CI
- Structured extraction of success payload fields such as `resolved_element`, `snapshot`, `actionability_used`, and upstream duration metadata
- Focused tests proving these behaviors end-to-end inside GDA abstractions

## Phase 1: Repair Layer Alignment With `agent-playbook.md`

### Task 1: Lock the Playbook Rules Into Unit Tests

**Files:**
- Modify: `tests/unit/test_repair.py`
- Reference: `src/repair/strategies.py`
- Reference: `src/repair/repair_loop.py`
- Reference: `/Users/qunmi/Documents/github/fsq-mac/docs/agent-playbook.md`

**Step 1: Write failing tests for retryability and inspect-before-retry behavior**

Add focused tests for these rules:

```python
def test_retry_strategy_honors_fsq_retryable_false():
    step = build_failed_step(
        classification=FailureClassification.OBSERVATION_INSUFFICIENT,
        fsq_error_code="ELEMENT_NOT_FOUND",
        fsq_retryable=False,
    )

    strategy = RetryStrategy(max_retries=2)

    assert strategy.can_handle(step) is False


@patch("src.repair.strategies.subprocess.run")
def test_restart_strategy_reinspects_before_retry_for_stale_refs(mock_run):
    step = build_failed_step(
        action="element_click",
        command=["mac", "element", "click", "e3"],
        classification=FailureClassification.OBSERVATION_INSUFFICIENT,
        fsq_error_code="ELEMENT_REFERENCE_STALE",
        fsq_retryable=True,
    )

    strategy = RestartStrategy(mac_cli="mac")
    strategy.apply(step, {})

    commands = [call.args[0] for call in mock_run.call_args_list]
    assert ["mac", "element", "inspect"] in commands
```

Also add tests for:

- `ELEMENT_NOT_FOUND` causes an `element inspect` before retry
- stale ref retry does not re-run the original `e3` command unchanged
- `BACKEND_UNAVAILABLE` runs `mac doctor backend` before session restart
- repair loop never exceeds `2` to `3` retries for the same logical step

**Step 2: Run the focused repair tests to confirm failure**

Run: `pytest tests/unit/test_repair.py -q`

Expected: FAIL, because current strategies do not yet implement the upstream playbook.

**Step 3: Commit the failing tests if using strict TDD**

```bash
git add tests/unit/test_repair.py
git commit -m "test: capture fsq-mac playbook repair expectations"
```

### Task 2: Implement Playbook-Aligned Recovery Rules

**Files:**
- Modify: `src/repair/strategies.py`
- Modify: `src/repair/repair_loop.py`
- Reference: `src/evidence/types.py`
- Test: `tests/unit/test_repair.py`

**Step 1: Add minimal helpers to inspect structured fsq error details**

In `src/repair/strategies.py`, add one small helper that extracts:

- `fsq_error_code`
- `fsq_retryable`
- whether the failed command was ref-based

Do not add broad abstraction layers.

**Step 2: Tighten `RetryStrategy.can_handle()`**

Implement these rules:

- `fsq_retryable is True` => retry allowed
- `fsq_retryable is False` => retry not allowed
- otherwise fall back to coarse `FailureClassification`

**Step 3: Implement pre-retry inspection for element failures**

For `ELEMENT_NOT_FOUND`, `ELEMENT_REFERENCE_STALE`, and `BACKEND_RPC_TIMEOUT` / `TIMEOUT` on element commands:

- run `mac element inspect`
- then attempt the retry

Keep the implementation local to the repair strategy layer.

**Step 4: Handle stale refs without reusing them**

When the original failed command targets a ref like `e3` and the error code is `ELEMENT_REFERENCE_STALE`:

- do not simply rerun the same argv
- return a repair result that indicates replan is required unless locator metadata is available in context
- prefer locator-based fallback when present in `context`

If the current codebase has no durable way to reconstruct locator flags from evidence, stop at explicit non-retry + replan recommendation rather than faking correctness.

**Step 5: Implement backend recovery ordering**

For `BACKEND_UNAVAILABLE`:

- run `mac doctor backend`
- only if that succeeds, end and restart session
- retry the failed command afterwards

**Step 6: Enforce retry caps**

Ensure strategy-level retries plus repair-loop iterations do not cause more than three attempts for the same logical failed step.

Prefer encoding the cap inside `RetryStrategy(max_retries=2)` plus a guard in the repair loop using `step.retry_count`.

**Step 7: Run repair tests to verify pass**

Run: `pytest tests/unit/test_repair.py -q`

Expected: PASS.

**Step 8: Commit the repair implementation**

```bash
git add src/repair/strategies.py src/repair/repair_loop.py tests/unit/test_repair.py
git commit -m "fix: align repair logic with fsq-mac playbook"
```

### Task 3: Verify Repair Behavior Through Pipeline-Level Tests

**Files:**
- Modify: `tests/unit/test_pipeline.py`
- Reference: `src/pipeline/pipeline.py`
- Test: `tests/unit/test_repair.py`

**Step 1: Add focused pipeline tests for structured repair flow**

Add tests that simulate:

- an element failure with `ELEMENT_NOT_FOUND` and `retryable=true`
- a backend failure with `BACKEND_UNAVAILABLE`

Assert the pipeline reaches the repair layer and records repair attempts instead of only failing immediately.

**Step 2: Run focused pipeline tests**

Run: `pytest tests/unit/test_pipeline.py -q`

Expected: PASS after implementation.

**Step 3: Commit the pipeline regression tests**

```bash
git add tests/unit/test_pipeline.py
git commit -m "test: cover playbook-aligned repair through pipeline"
```

## Phase 2: Contract Governance and CI Guardrails

### Task 4: Lock Contract Validation Expectations in Tests

**Files:**
- Create: `tests/unit/test_validate_registry.py`
- Reference: `scripts/validate_registry.py`
- Reference: `/Users/qunmi/Documents/github/fsq-mac/docs/agent-contract.json`

**Step 1: Write failing tests for registry validation behavior**

Cover at least:

- missing upstream action returns exit code `1`
- full coverage returns exit code `0`
- builtins like `sleep` are excluded from contract comparison
- unknown custom actions are reported as extras

Example:

```python
def test_validate_registry_fails_when_contract_action_missing(tmp_path):
    contract = tmp_path / "agent-contract.json"
    registry = tmp_path / "actions.yaml"
    contract.write_text(json.dumps({"domains": [{"name": "menu", "actions": ["click"]}]}))
    registry.write_text("actions: {}\n")

    result = run_validate_registry(contract=contract, registry=registry)

    assert result.exit_code == 1
    assert "menu.click" in result.stdout
```

**Step 2: Run focused tests to confirm failure if helpers are missing**

Run: `pytest tests/unit/test_validate_registry.py -q`

Expected: FAIL until test harness helpers exist.

**Step 3: Commit the failing tests if following strict TDD**

```bash
git add tests/unit/test_validate_registry.py
git commit -m "test: define registry contract validation behavior"
```

### Task 5: Make Contract Validation Script CI-Friendly

**Files:**
- Modify: `scripts/validate_registry.py`
- Modify: `.github/workflows/` relevant workflow file if one already runs tests
- Test: `tests/unit/test_validate_registry.py`

**Step 1: Refactor the script into testable functions**

Keep the CLI, but extract:

- `validate_registry_against_contract(...) -> ValidationResult`
- a small renderer for human-readable output

**Step 2: Preserve current local defaults but improve portability**

Support these inputs in order:

- explicit `--contract`
- `FSQ_MAC_CONTRACT_PATH` env var
- repo-relative fallback to `../fsq-mac/docs/agent-contract.json`

This lets CI pin the upstream file path instead of depending on a sibling checkout layout.

**Step 3: Fail CI on drift**

Add a workflow step to run:

```bash
python3 scripts/validate_registry.py --contract "$FSQ_MAC_CONTRACT_PATH"
```

Only modify an existing workflow if the repository already has a compatible test/lint job. If there is no suitable workflow, create one narrow job rather than reshaping unrelated CI.

**Step 4: Run validation tests**

Run: `pytest tests/unit/test_validate_registry.py -q`

Expected: PASS.

**Step 5: Commit the validation hardening**

```bash
git add scripts/validate_registry.py tests/unit/test_validate_registry.py .github/workflows
git commit -m "chore: enforce fsq-mac registry contract validation"
```

## Phase 3: Rich Structured Evidence Extraction

### Task 6: Lock Success-Payload Evidence Expectations Into Tests

**Files:**
- Modify: `tests/unit/test_executor.py`
- Modify: `tests/unit/test_evidence.py`
- Reference: `src/executor/executor.py`
- Reference: `src/evidence/types.py`

**Step 1: Add failing executor tests for structured success payload extraction**

Cover success envelopes containing:

- `data.resolved_element`
- `data.snapshot`
- `data.actionability_used`
- `meta.duration_ms`
- `session_id`

Example:

```python
def test_execute_step_extracts_resolved_element_and_snapshot(mock_run):
    envelope = {
        "ok": True,
        "command": "element.click",
        "session_id": "s1",
        "data": {
            "resolved_element": {"ref": "e7", "role": "AXButton", "name": "OK"},
            "snapshot": {"snapshot_id": "snap-1", "elements": [{"ref": "e7"}]},
            "actionability_used": {"actionable": True, "checks": {"visible": True}},
        },
        "error": None,
        "meta": {"duration_ms": 321},
    }
```

Assert the resulting `StepEvidence` exposes those fields structurally, not only inside opaque stdout.

**Step 2: Add evidence serialization tests**

Extend `tests/unit/test_evidence.py` to assert the new structured fields survive `to_dict()` and storage round-trips.

**Step 3: Run focused tests to confirm failure**

Run: `pytest tests/unit/test_executor.py tests/unit/test_evidence.py -q`

Expected: FAIL until the model types and extraction logic are updated.

### Task 7: Extend Evidence Types and Executor Extraction

**Files:**
- Modify: `src/evidence/types.py`
- Modify: `src/executor/executor.py`
- Optionally modify: `src/evidence/storage.py`
- Test: `tests/unit/test_executor.py`
- Test: `tests/unit/test_evidence.py`

**Step 1: Add minimal structured evidence fields**

Extend `CLICommand` or `StepEvidence` with optional fields for:

- `session_id`
- `resolved_element`
- `snapshot`
- `actionability_used`
- `upstream_duration_ms`

Prefer adding them to `CLICommand` if they are direct properties of the executed command response.

**Step 2: Extract fields in the executor**

When `parsed_response.ok == True`:

- read from `parsed_response["data"]`
- populate the new structured fields
- preserve full `parsed_response` as raw context too

**Step 3: Keep behavior tolerant of partial payloads**

Do not assume every successful command returns these fields.

**Step 4: Run focused executor and evidence tests**

Run: `pytest tests/unit/test_executor.py tests/unit/test_evidence.py -q`

Expected: PASS.

**Step 5: Commit the rich evidence work**

```bash
git add src/evidence/types.py src/executor/executor.py src/evidence/storage.py tests/unit/test_executor.py tests/unit/test_evidence.py
git commit -m "feat: capture structured fsq-mac success evidence"
```

## Phase 4: Regression and Delivery Checks

### Task 8: Run Full Relevant Regression Set

**Files:**
- No code changes required unless regressions are found

**Step 1: Run focused suites in dependency order**

Run:

```bash
pytest tests/unit/test_repair.py -q
pytest tests/unit/test_validate_registry.py -q
pytest tests/unit/test_executor.py tests/unit/test_evidence.py tests/unit/test_pipeline.py -q
pytest tests/integration/test_pipeline_runtime.py tests/integration/test_batch_cli.py -q
pytest -q
```

Expected: PASS.

**Step 2: Run the registry validator against the real upstream contract**

Run:

```bash
python3 scripts/validate_registry.py --contract /Users/qunmi/Documents/github/fsq-mac/docs/agent-contract.json
```

Expected: no missing actions for the subset GDA intentionally supports, or an explicit extras/missing report that matches documented intentional gaps.

**Step 3: Smoke-check a real `fsq-mac` path if environment permits**

Prefer one or two narrow goal flows using the existing CLI entrypoint and `FSQ_MAC_CLI` override.

Example:

```bash
FSQ_MAC_CLI=/Users/qunmi/Documents/github/fsq-mac/.venv/bin/mac python3 -m src.cli run "Verify Safari is running" --json
```

Do not broaden into a large E2E batch if the environment is unstable. This is a confidence smoke test, not a product launch rehearsal.

### Task 9: Clean Up Delivery Risks Before Merge

**Files:**
- Review only unless cleanup is needed

**Step 1: Remove unrelated tracked artifact deletions from the compatibility patch**

Specifically review and unstage or restore unrelated `test-results/` deletions before merge.

**Step 2: Summarize intentional remaining gaps**

If GDA still intentionally does not support every upstream contract action, document the exact gap list and rationale in the PR description or release notes.

**Step 3: Final review pass**

Request review with emphasis on:

- stale-ref handling correctness
- CI contract portability
- evidence field naming and backward compatibility

## Suggested Execution Order

1. Task 1
2. Task 2
3. Task 3
4. Task 4
5. Task 5
6. Task 6
7. Task 7
8. Task 8
9. Task 9

## Definition of Done

- Repair behavior follows upstream `agent-playbook.md` for the key emitted failure codes
- Registry drift is caught automatically in tests or CI
- Successful executor responses expose structured evidence fields beyond raw stdout
- Unit and integration tests pass
- Unrelated `test-results/` deletions are not bundled with the compatibility change

## Verification Checklist

1. `pytest tests/unit/test_repair.py -q`
2. `pytest tests/unit/test_validate_registry.py -q`
3. `pytest tests/unit/test_executor.py tests/unit/test_evidence.py tests/unit/test_pipeline.py -q`
4. `pytest tests/integration/test_pipeline_runtime.py tests/integration/test_batch_cli.py -q`
5. `pytest -q`
6. `python3 scripts/validate_registry.py --contract /Users/qunmi/Documents/github/fsq-mac/docs/agent-contract.json`

