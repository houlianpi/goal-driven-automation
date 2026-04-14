# fsq-mac v0.3.0 Compatibility Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Upgrade Goal-Driven Automation to run correctly against `fsq-mac` `v0.3.0`, then adopt the new agent-facing contract for structured execution, classification, repair, and evidence handling.

**Architecture:** Keep the existing GDA pipeline shape (`plan -> compile -> execute -> evaluate -> repair`) and migrate in layers. First restore runtime compatibility at the command-generation boundary. Then consume the new `fsq-mac` machine-readable contract (`docs/agent-contract.json`, `docs/agent-playbook.md`) to replace brittle stderr heuristics with structured command and error handling.

**Tech Stack:** Python 3.13, pytest, argparse-based CLI execution, JSON/YAML registry loading, fsq-mac `v0.3.0` agent contract artifacts.

---

## Implementation Principles

- Treat `fsq-mac/docs/agent-contract.json` as the long-term machine-readable source of truth.
- Do not block basic compatibility on full registry-generation work; restore runtime compatibility first.
- Follow TDD for each slice: write failing tests, run them, implement minimally, run focused tests, then run the broader regression set.
- Keep changes incremental and commit after each task-sized slice.
- Preserve current user-facing GDA concepts: `case`, `suite`, `run result`.

## Phase Overview

### Phase 1: Runtime Compatibility

Restore GDA so existing `run`, `run-case`, and `run-suite` flows can execute against `fsq-mac v0.3.0` without producing invalid commands.

### Phase 2: Structured Contract Adoption

Parse `fsq-mac` JSON envelopes, promote `error.code` and `error.retryable` to first-class orchestration signals, and align retry/repair logic with `docs/agent-playbook.md`.

### Phase 3: Contract-Driven Registry and Rich Evidence

Move GDA away from hand-maintained command assumptions by loading canonical contract metadata from `fsq-mac/docs/agent-contract.json`, then capture richer success payloads such as `resolved_element`, `actionability_used`, and `snapshot`.

## Task 1: Lock in Current Breakages With Compiler Tests

**Files:**
- Modify: `tests/unit/test_compiler.py`
- Reference: `src/compiler/compiler.py`
- Reference: `registry/actions.yaml`
- Reference: `/Users/qunmi/Documents/github/fsq-mac/src/fsq_mac/cli.py`

**Step 1: Write failing tests for v0.3.0 element command syntax**

Add tests that assert the compiler emits these argv shapes:

```python
def test_compile_click_step_uses_locator_flags_for_v030():
    compiler = Compiler()
    step = {
        "step_id": "step_click_context",
        "action": "click",
        "params": {
            "selector": "Submit",
            "locator_text": "Submit",
            "locator_role": "AXButton",
        },
    }

    result = compiler.compile_step(step)

    assert result["argv"] == [
        "mac", "element", "click", "--role", "AXButton", "--name", "Submit"
    ]


def test_compile_type_step_uses_text_then_locator_flags_for_v030():
    compiler = Compiler()
    step = {
        "step_id": "step_type_context",
        "action": "type",
        "params": {
            "text": "hello world",
            "input_target": "Email",
            "locator_role": "AXTextField",
        },
    }

    result = compiler.compile_step(step)

    assert result["argv"] == [
        "mac", "element", "type", "hello world", "--role", "AXTextField", "--name", "Email"
    ]
```

Also add focused tests for:

- `menu click` instead of `menu select`
- `window focus <index>` rather than title-based focus
- `capture screenshot <path>` instead of `--output`

**Step 2: Run focused compiler tests to confirm failures**

Run: `pytest tests/unit/test_compiler.py -q`

Expected: failures showing old argv generation still uses positional locator syntax and stale capture/menu commands.

**Step 3: Commit the failing tests if using strict TDD workflow in a feature branch**

```bash
git add tests/unit/test_compiler.py
git commit -m "test: lock fsq-mac v0.3.0 compiler compatibility expectations"
```

## Task 2: Update the Registry for Known v0.3.0 Command Surface Changes

**Files:**
- Modify: `registry/actions.yaml`
- Test: `tests/unit/test_compiler.py`
- Reference: `/Users/qunmi/Documents/github/fsq-mac/docs/agent-contract.json`
- Reference: `/Users/qunmi/Documents/github/fsq-mac/src/fsq_mac/cli.py`

**Step 1: Update stale command templates in the registry**

Make the minimum compatibility edits:

- `capture_screenshot`: `mac capture screenshot {output}`
- `capture_ui_tree`: remove `--output` assumptions; if registry must still represent capture, use `mac capture ui-tree`
- `menu_select`: replace with `menu_click` and `mac menu click {menu_path}`
- `window_focus`: switch argument semantics to index
- `terminate_app`: append `--allow-dangerous`

Do not attempt full registry generation from `agent-contract.json` in this task.

**Step 2: Run focused compiler tests**

Run: `pytest tests/unit/test_compiler.py -q`

Expected: some tests still fail until compiler mapping logic is updated.

**Step 3: Commit the registry compatibility patch**

```bash
git add registry/actions.yaml
git commit -m "fix: align registry commands with fsq-mac v0.3.0"
```

## Task 3: Rewrite Compiler Mapping for Element Flags, Ref Syntax, and New Menu/Window Semantics

**Files:**
- Modify: `src/compiler/compiler.py`
- Test: `tests/unit/test_compiler.py`
- Reference: `src/pipeline/plan_generator.py`
- Reference: `/Users/qunmi/Documents/github/fsq-mac/docs/agent-contract.json`

**Step 1: Add failing tests for ref-aware and flag-aware compilation**

Extend compiler tests with cases for:

- click by ref: `{"ref": "e0"}` -> `mac element click e0`
- type by ref plus text: `{"ref": "e3", "text": "hello"}` -> `mac element type e3 hello`
- assert visible with locator flags
- direct input `input text` preserving one argv item for spaced text

**Step 2: Run focused compiler tests to confirm failures**

Run: `pytest tests/unit/test_compiler.py -q`

Expected: failures in compiler mapping for `click`, `type`, `assert`, `menu`, and `window`.

**Step 3: Implement minimal compiler helpers for fsq-mac v0.3.0 command generation**

Refactor `src/compiler/compiler.py` to:

- build locator flags from semantic params such as `locator_role`, `locator_text`, `input_target`, `locator_id`, `xpath`
- prefer `ref` when present for element-targeted actions
- emit `element type [ref] <text> [flags]`
- emit `element click [ref] [flags]`
- emit `assert visible/enabled/text/value [ref?] [flags]`
- map semantic menu/window actions to the new command names and positional arguments

Do not over-generalize. Add one small helper for locator flag assembly and one helper for element command argv assembly.

**Step 4: Run compiler tests to verify pass**

Run: `pytest tests/unit/test_compiler.py -q`

Expected: PASS.

**Step 5: Commit the compiler update**

```bash
git add src/compiler/compiler.py tests/unit/test_compiler.py
git commit -m "fix: compile semantic actions for fsq-mac v0.3.0"
```

## Task 4: Repair Evidence Capture Commands for v0.3.0

**Files:**
- Modify: `src/evidence/collector.py`
- Add/Modify: `tests/unit/test_evidence.py`
- Reference: `/Users/qunmi/Documents/github/fsq-mac/src/fsq_mac/cli.py`

**Step 1: Write failing tests for screenshot and ui-tree capture invocation**

Add tests that patch `subprocess.run` and assert:

- screenshot uses `[..., "capture", "screenshot", "<path>"]`
- ui-tree capture no longer passes `--output`

Example:

```python
@patch("src.evidence.collector.subprocess.run")
def test_capture_screenshot_uses_positional_output_path(mock_run, tmp_path):
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
    collector = EvidenceCollector(tmp_path)

    collector.capture_screenshot("s1")

    assert mock_run.call_args.args[0][:3] == ["mac", "capture", "screenshot"]
```

**Step 2: Run focused evidence tests to confirm failures**

Run: `pytest tests/unit/test_evidence.py -q`

Expected: failures showing old `--output` assumptions.

**Step 3: Implement minimal capture command updates**

Update `src/evidence/collector.py` so:

- screenshot uses positional output path
- ui-tree capture reads stdout JSON or plain content and writes the file locally if the CLI no longer writes to a path directly

If `ui-tree` returns JSON envelope, write either the `data` object or raw stdout to the target file in a predictable way. Prefer preserving the existing artifact path semantics inside GDA.

**Step 4: Run evidence tests to verify pass**

Run: `pytest tests/unit/test_evidence.py -q`

Expected: PASS.

**Step 5: Commit the evidence capture fix**

```bash
git add src/evidence/collector.py tests/unit/test_evidence.py
git commit -m "fix: update evidence capture for fsq-mac v0.3.0"
```

## Task 5: Validate Phase 1 End-to-End Compatibility

**Files:**
- Modify: `tests/integration/test_pipeline_runtime.py`
- Modify: `tests/integration/test_batch_cli.py`
- Reference: `src/cli.py`
- Reference: `src/pipeline/pipeline.py`

**Step 1: Add or update integration tests to assert v0.3.0-compatible argv**

Cover at least:

- a goal that produces `launch + shortcut + assert`
- a batch asset flow (`run-case` / `run-suite`) that still works after compiler changes

Prefer mocking execution and asserting compiled argv or pipeline success path rather than relying on a real `fsq-mac` install.

**Step 2: Run integration tests**

Run: `pytest tests/integration/test_pipeline_runtime.py tests/integration/test_batch_cli.py -q`

Expected: PASS.

**Step 3: Run the full test suite as the Phase 1 gate**

Run: `pytest -q`

Expected: PASS.

**Step 4: Commit Phase 1 completion**

```bash
git add tests/integration/test_pipeline_runtime.py tests/integration/test_batch_cli.py
git commit -m "test: verify fsq-mac v0.3.0 phase 1 compatibility"
```

## Task 6: Add Contract Loader for fsq-mac Agent Artifacts

**Files:**
- Add: `src/contracts/__init__.py`
- Add: `src/contracts/fsq_mac_contract.py`
- Modify: `pyproject.toml`
- Add: `tests/unit/test_fsq_mac_contract.py`
- Reference: `/Users/qunmi/Documents/github/fsq-mac/docs/agent-contract.json`
- Reference: `/Users/qunmi/Documents/github/fsq-mac/docs/agent-playbook.md`

**Step 1: Write failing tests for loading agent-contract metadata**

Add tests for:

- loading error codes and retryable flags from a fixture JSON
- exposing a lookup like `contract.error_code("ELEMENT_NOT_FOUND")`
- ignoring reserved codes for branching helpers unless explicitly requested

**Step 2: Run focused contract tests to confirm failures**

Run: `pytest tests/unit/test_fsq_mac_contract.py -q`

Expected: FAIL because the loader module does not exist yet.

**Step 3: Implement minimal contract loader**

Create a small loader that reads a configured contract path and exposes:

- version
- domain/action metadata
- emitted error-code metadata
- response-contract metadata

Keep this read-only. Do not wire it into the compiler yet.

**Step 4: Run focused tests to verify pass**

Run: `pytest tests/unit/test_fsq_mac_contract.py -q`

Expected: PASS.

**Step 5: Commit the contract loader**

```bash
git add src/contracts/__init__.py src/contracts/fsq_mac_contract.py tests/unit/test_fsq_mac_contract.py pyproject.toml
git commit -m "feat: load fsq-mac agent contract metadata"
```

## Task 7: Parse fsq-mac JSON Envelopes in the Executor

**Files:**
- Modify: `src/executor/executor.py`
- Modify: `src/evidence/types.py`
- Modify: `tests/unit/test_executor.py`
- Reference: `/Users/qunmi/Documents/github/fsq-mac/docs/agent-contract.json`

**Step 1: Add failing executor tests for JSON envelope parsing**

Add tests that simulate stdout such as:

```json
{"ok": false, "error": {"code": "ELEMENT_NOT_FOUND", "retryable": true, "message": "..."}, "data": null}
```

Assert that executor step results preserve parsed envelope fields separately from raw stdout.

Also add a success case that captures:

- `data`
- `session_id`
- `meta.duration_ms`

**Step 2: Run executor tests to confirm failures**

Run: `pytest tests/unit/test_executor.py -q`

Expected: FAIL because current executor only tracks stdout/stderr/return code.

**Step 3: Implement minimal parsed-response support**

Update executor data structures to retain:

- `parsed_response`
- `error_code`
- `retryable`
- `response_data`

Use JSON parsing only when stdout is valid JSON with top-level `ok` and `command`. Preserve raw stdout regardless.

Special-case `trace.codegen` later; do not solve it in this task unless tests cover it.

**Step 4: Run executor tests to verify pass**

Run: `pytest tests/unit/test_executor.py -q`

Expected: PASS.

**Step 5: Commit the executor response parsing update**

```bash
git add src/executor/executor.py src/evidence/types.py tests/unit/test_executor.py
git commit -m "feat: parse fsq-mac json envelopes in executor"
```

## Task 8: Replace Regex-First Failure Classification With error.code-First Mapping

**Files:**
- Modify: `src/evaluator/classifier.py`
- Modify: `src/evaluator/evaluator.py`
- Modify: `tests/unit/test_evaluator.py`
- Reference: `/Users/qunmi/Documents/github/fsq-mac/docs/agent-contract.json`
- Reference: `/Users/qunmi/Documents/github/fsq-mac/docs/agent-playbook.md`

**Step 1: Add failing classifier tests for structured error-code mapping**

Cover at least:

- `ELEMENT_NOT_FOUND` -> observation issue + retry/reinspect recommendation
- `ELEMENT_REFERENCE_STALE` -> re-inspect + locator retry
- `BACKEND_UNAVAILABLE` -> environment failure + doctor/backend recovery path
- `ACTION_BLOCKED` -> abort or human review, not retry

Keep one regex fallback test to preserve behavior when parsed JSON is absent.

**Step 2: Run evaluator tests to confirm failures**

Run: `pytest tests/unit/test_evaluator.py -q`

Expected: FAIL because current classification is stderr-driven.

**Step 3: Implement error.code-first classification logic**

Update classifier to:

- consult structured executor/evidence fields first
- use contract retryability where available
- keep regex matching as fallback only

Align recommended strategies with `agent-playbook.md` guidance.

**Step 4: Run evaluator tests to verify pass**

Run: `pytest tests/unit/test_evaluator.py -q`

Expected: PASS.

**Step 5: Commit the classifier rewrite**

```bash
git add src/evaluator/classifier.py src/evaluator/evaluator.py tests/unit/test_evaluator.py
git commit -m "feat: classify fsq-mac failures by error code"
```

## Task 9: Align Repair and Retry Logic With the Agent Playbook

**Files:**
- Modify: `src/repair/repair_loop.py`
- Modify: `src/repair/strategies.py`
- Modify: `tests/unit/test_repair.py`
- Reference: `/Users/qunmi/Documents/github/fsq-mac/docs/agent-playbook.md`

**Step 1: Add failing repair tests for playbook-guided recovery**

Cover these rules:

- on `ELEMENT_NOT_FOUND`, re-inspect before retry
- on `ELEMENT_REFERENCE_STALE`, do not reuse stale ref; prefer locator retry
- on `BACKEND_UNAVAILABLE`, prefer backend diagnostics/session restart flow
- cap retries at 2-3 per logical step

**Step 2: Run repair tests to confirm failures**

Run: `pytest tests/unit/test_repair.py -q`

Expected: FAIL because current repair behavior is less contract-aware.

**Step 3: Implement minimal playbook alignment**

Keep scope tight:

- add a fresh inspect step or inspect recommendation before element retries
- honor `retryable=false` to short-circuit retries
- prevent stale-ref flows from reusing refs blindly

**Step 4: Run repair tests to verify pass**

Run: `pytest tests/unit/test_repair.py -q`

Expected: PASS.

**Step 5: Commit the repair logic update**

```bash
git add src/repair/repair_loop.py src/repair/strategies.py tests/unit/test_repair.py
git commit -m "feat: align repair strategies with fsq-mac agent playbook"
```

## Task 10: Capture Rich Success Payloads in Evidence Artifacts

**Files:**
- Modify: `src/evidence/types.py`
- Modify: `src/evidence/storage.py`
- Modify: `src/executor/executor.py`
- Modify: `tests/unit/test_evidence.py`
- Reference: `/Users/qunmi/Documents/github/fsq-mac/CHANGELOG.md`

**Step 1: Add failing evidence tests for rich response fields**

Cover persistence of:

- `resolved_element`
- `actionability_used`
- `snapshot_status`
- `snapshot`
- `element_bounds` / `center`

**Step 2: Run evidence tests to confirm failures**

Run: `pytest tests/unit/test_evidence.py -q`

Expected: FAIL because current evidence only stores raw command details and simple artifacts.

**Step 3: Implement minimal rich-response persistence**

Store these fields under a stable sub-dictionary such as `command_response` on step evidence. Do not flatten everything onto the top level.

**Step 4: Run evidence tests to verify pass**

Run: `pytest tests/unit/test_evidence.py -q`

Expected: PASS.

**Step 5: Commit the evidence enrichment**

```bash
git add src/evidence/types.py src/evidence/storage.py src/executor/executor.py tests/unit/test_evidence.py
git commit -m "feat: persist rich fsq-mac action responses in evidence"
```

## Task 11: Replace Hand-Written Registry Assumptions With Contract-Driven Metadata

**Files:**
- Modify: `src/compiler/compiler.py`
- Add: `src/contracts/fsq_mac_registry.py`
- Modify: `registry/actions.yaml`
- Modify: `tests/unit/test_compiler.py`
- Modify: `tests/unit/test_fsq_mac_contract.py`
- Reference: `/Users/qunmi/Documents/github/fsq-mac/docs/agent-contract.json`

**Step 1: Write failing tests for contract-driven registry lookup**

Add tests that ensure compiler can source authoritative metadata such as:

- valid domains/actions
- usage-error semantics
- safe presence of `app-running` / `app-frontmost`

Do not require generating a full command template language from contract JSON. The goal is to remove duplicated command-surface assumptions, not to build a compiler generator.

**Step 2: Run focused compiler and contract tests to confirm failures**

Run: `pytest tests/unit/test_compiler.py tests/unit/test_fsq_mac_contract.py -q`

Expected: FAIL.

**Step 3: Implement a hybrid contract-driven registry approach**

Recommended minimal architecture:

- keep semantic action lowering inside GDA
- source canonical `fsq-mac` domains/actions/error codes from `agent-contract.json`
- reduce `registry/actions.yaml` to semantic-to-command-shape metadata only, or remove it if the compiler can generate argv directly

Do not build a YAML+JSON dual-source system that can drift silently.

**Step 4: Run focused tests to verify pass**

Run: `pytest tests/unit/test_compiler.py tests/unit/test_fsq_mac_contract.py -q`

Expected: PASS.

**Step 5: Commit the registry architecture update**

```bash
git add src/compiler/compiler.py src/contracts/fsq_mac_registry.py registry/actions.yaml tests/unit/test_compiler.py tests/unit/test_fsq_mac_contract.py
git commit -m "refactor: drive fsq-mac command metadata from agent contract"
```

## Task 12: Final Regression, Docs, and Delivery Check

**Files:**
- Modify: `README.md`
- Modify: `docs/product/agent-first-positioning.md` if needed
- Add/Modify: `docs/plans/2026-04-14-fsq-mac-v030-compatibility-implementation-plan.md`

**Step 1: Update developer docs with the new dependency contract assumptions**

Document:

- minimum expected `fsq-mac` version
- that GDA now consumes structured JSON envelopes
- where contract metadata comes from

**Step 2: Run the full regression suite**

Run: `pytest -q`

Expected: PASS.

**Step 3: Run one manual dry-run smoke check**

Run: `python -m src.cli run "Open Safari" --dry-run --json`

Expected: valid JSON output with a compiled plan and no compilation errors.

**Step 4: Summarize remaining risks before merge**

Capture any still-open items, especially:

- trace codegen raw-text success path
- real `fsq-mac` runtime verification against a live backend
- whether `capture ui-tree` output should store the raw envelope or only `data`

**Step 5: Commit docs and final cleanups**

```bash
git add README.md docs/product/agent-first-positioning.md docs/plans/2026-04-14-fsq-mac-v030-compatibility-implementation-plan.md
git commit -m "docs: record fsq-mac v0.3.0 compatibility plan and contract updates"
```

## Suggested Execution Order

Use this order even if multiple engineers are available:

1. Tasks 1-5
2. Tasks 6-8
3. Task 9
4. Task 10
5. Task 11
6. Task 12

Do not start Task 11 before Tasks 6-8 are complete. The contract-loader and structured-response work establish the data model needed to do registry architecture cleanly.

## Validation Matrix

- Compiler compatibility: `pytest tests/unit/test_compiler.py -q`
- Executor structured parsing: `pytest tests/unit/test_executor.py -q`
- Evaluator/classifier mapping: `pytest tests/unit/test_evaluator.py -q`
- Repair alignment: `pytest tests/unit/test_repair.py -q`
- Evidence handling: `pytest tests/unit/test_evidence.py -q`
- Batch CLI behavior: `pytest tests/integration/test_batch_cli.py -q`
- Pipeline runtime flow: `pytest tests/integration/test_pipeline_runtime.py -q`
- Final gate: `pytest -q`

## Risks and Watchpoints

- `trace codegen` has a documented raw-text success path and must not be parsed as standard JSON success.
- `capture ui-tree` output semantics may require writing files locally from stdout rather than depending on CLI-side file output.
- Existing retry-policy naming drift (`max_attempts` vs `max`) is adjacent technical debt and may surface during executor work; fix it in the same slice if it blocks structured retry adoption.
- Some `agent-contract.json` error codes are marked `reserved`; classification logic must ignore them for control flow unless explicitly emitted.
- Real backend verification is still required after unit/integration green runs because `fsq-mac` behavior depends on Appium Mac2 and macOS accessibility state.
