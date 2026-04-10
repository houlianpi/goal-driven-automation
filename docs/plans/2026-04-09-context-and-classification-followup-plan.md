# Context Grounding And Error Classification Follow-Up Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close the next two high-value gaps after mainline remediation: make `type` and `click` goals context-aware enough to be executable in real-user flows, and improve failure classification so structured `fsq-mac` errors are mapped to meaningful evidence and repair decisions.

**Architecture:** Treat these as two related but separate tracks. Context grounding belongs to the `Goal -> Plan -> Compile` pipeline and should improve what the system asks the runtime to do. Structured error classification belongs to the `Execute -> Evidence -> Evaluate` path and should improve how the system explains and responds to runtime failures. Do not mix the two concerns in the same patch unless a shared fixture or test requires it.

**Tech Stack:** Python 3.13, pytest, `fsq-mac` CLI JSON output, YAML registry, real macOS E2E validation.

---

## Problem Statement

Recent real-user E2E validation shows that the runtime path is now fundamentally working, but two product-level gaps remain:

- Unscoped natural-language goals such as `Type 'hello world'` and `Click on 'Submit' button` lack enough app or focus context to be reliably executable.
- `fsq-mac` runtime failures currently collapse into coarse `environment_failure` classifications even when the CLI returns structured machine-readable error codes such as `ELEMENT_NOT_FOUND`.

Observed real examples:

- `Type 'hello world'`
  - The command now compiles correctly to `mac input text ...`, but still fails when no usable focused target exists.
  - Latest evidence: [`evidence.json`](/Users/qunmi/Documents/github/goal-driven-automation/data/runs/run-fb64527d/evidence.json)
- `Click on 'Submit' button`
  - The command now compiles and executes correctly, but the locator is under-specified and fails with `ELEMENT_NOT_FOUND`.
  - Latest evidence: [`evidence.json`](/Users/qunmi/Documents/github/goal-driven-automation/data/runs/run-93f57e70/evidence.json)
- The current classification path maps both of these to `environment_failure`, which obscures the difference between missing context, missing element, and genuine runtime instability.

---

## Scope

This plan covers:

- parser and plan-generator changes needed to represent execution context explicitly for `type` and `click` goals
- compiler and registry changes needed to preserve that context into runtime-capable commands
- executor and classifier changes needed to extract structured `fsq-mac` error codes from JSON stdout/stderr and map them into better `FailureClassification` values
- regression tests for unit and integration coverage
- real E2E re-validation of representative user goals

Out of scope for this pass:

- implementing true app-level semantic assertions in this repo for verification goals
- changing `fsq-mac` itself beyond issue tracking
- redesigning the repair strategy ladder beyond what is required to consume better classifications
- solving fully ambiguous user goals with LLM planning or interactive clarification

---

## Execution Principles

- Improve semantic precision before adding more fallback logic.
- Prefer explicit context fields over hidden heuristics.
- Parse and preserve structured `fsq-mac` errors as data before classifying them.
- Keep each workstream independently verifiable.
- Use real E2E scenarios only after focused unit and integration checks pass.

---

## Workstream A: Context Grounding For `type` And `click`

**Outcome:** The system no longer treats unscoped `type` and `click` goals as if they were self-sufficient. Plans must either carry actionable app/context information or degrade in an explicit, reviewable way.

### Design Direction

Introduce explicit context fields into parsed goals and generated plan steps rather than relying on the runtime to guess intent.

Recommended minimal model:

- `Goal.target_app` continues to represent the primary app when known.
- `Goal.constraints` may also carry context fields such as:
  - `app`
  - `requires_focused_target`
  - `locator_text`
  - `locator_role`
  - `input_target`
- `PlanGenerator` should emit context-bearing steps rather than raw `type` or `click` actions with only a text payload.

### Required decisions

Choose one behavior for ungrounded goals before implementation:

- **Option A, recommended:** preserve compilation but mark the plan as weakly grounded using explicit metadata and conservative `on_fail` behavior.
- **Option B:** reject or abort plan generation for `type` / `click` goals that lack app or target context.

Recommended direction:

- Start with Option A.
- Rationale: it keeps the CLI usable for exploratory goals while making ambiguity visible in the plan and tests.

### Files

- Modify: `src/pipeline/goal_parser.py`
- Modify: `src/pipeline/plan_generator.py`
- Modify: `src/compiler/compiler.py`
- Modify: `registry/actions.yaml`
- Test: `tests/unit/test_pipeline.py`
- Test: `tests/unit/test_compiler.py`
- Test: `tests/integration/test_pipeline_runtime.py`

### Tasks

1. Extend `GoalParser` to detect app context when users say things like:
   - `In Safari, type 'hello world'`
   - `Click the Submit button in Edge`
   - `Open Edge and click Submit`
2. Add explicit constraints for action context instead of storing only `text` or `element`.
3. Update `PlanGenerator` so `click` and `type` steps preserve app/context metadata in `params`.
4. Decide how to encode weakly grounded steps, for example:
   - `params.requires_focused_target = true`
   - `metadata.context_confidence = low`
   - `on_fail = human_review` or `replan`
5. Keep compiled output compatible with current runtime commands while preserving enough metadata for future planner improvements.

### Acceptance criteria

- Parser can capture app context from supported phrasings.
- Generated `type` and `click` steps distinguish grounded from ungrounded goals.
- Plans for ungrounded goals are explicit about ambiguity instead of silently pretending full executability.
- Existing successful app-launch and new-tab scenarios still compile and run unchanged.

### Validation

```bash
pytest tests/unit/test_pipeline.py tests/unit/test_compiler.py tests/integration/test_pipeline_runtime.py -q
```

Real E2E smoke after unit coverage passes:

```bash
FSQ_MAC_CLI=/Users/qunmi/Documents/github/fsq-mac/.venv/bin/mac python3 -m src.cli run "In Safari, type 'hello world'" --json
FSQ_MAC_CLI=/Users/qunmi/Documents/github/fsq-mac/.venv/bin/mac python3 -m src.cli run "Open Edge and click 'Submit' button" --json
```

Expected result:

- either direct success on grounded flows
- or explicit, explainable failure paths that reference missing target context rather than opaque runtime errors

---

## Workstream B: Structured `fsq-mac` Error Classification

**Outcome:** Runtime evidence and evaluator output distinguish structured app/element/action failures from genuine environment failures.

### Design Direction

Do not classify based only on generic strings like `Failed after 1 attempts`. Extract structured error payloads first, then map them to `FailureClassification`.

Observed current problem:

- `fsq-mac` often returns JSON on `stdout` even when the exit code is non-zero.
- The JSON includes `error.code`, `error.message`, and retryability hints.
- The current executor sets `StepError.message` to a generic retry summary and the classifier largely falls back to `environment_failure`.

### Required changes

Add a parsing layer for structured CLI failures and preserve the result into evidence.

### Files

- Modify: `src/executor/executor.py`
- Modify: `src/evaluator/classifier.py`
- Optional Modify: `src/evidence/types.py`
- Test: `tests/unit/test_executor.py`
- Test: `tests/unit/test_evaluator.py`
- Test: `tests/integration/test_pipeline_runtime.py`

### Tasks

1. Add a helper in `Executor` to parse structured JSON responses from `stdout` or `stderr` when the command target is `fsq-mac`.
2. Preserve structured fields into `StepResult.evidence`, for example:
   - `fsq_ok`
   - `fsq_error_code`
   - `fsq_error_message`
   - `fsq_retryable`
3. Update `execute()` when building `StepError` so structured errors are not collapsed into generic `ExecutionError` text.
4. Extend `FailureClassifier` with a code-based mapping before regex fallback.

Recommended initial mapping:

- `ELEMENT_NOT_FOUND` -> `OBSERVATION_INSUFFICIENT`
- `SESSION_NOT_FOUND` -> `PRECONDITION_MISSING`
- `ACTION_BLOCKED` -> `PRECONDITION_MISSING`
- `TIMEOUT` -> `ENVIRONMENT_FAILURE`
- `INTERNAL_ERROR` -> `ENVIRONMENT_FAILURE`
- assertion-specific codes, if present later -> `ASSERTION_FAILED`

5. Keep regex and exit-code heuristics as fallback only for non-JSON tools or malformed output.
6. Verify evaluator recommendations improve with better classifications:
   - element lookup failures should prefer retry or replan, not blanket restart-session
   - missing session should recommend restart/bootstrap

### Acceptance criteria

- Structured `fsq-mac` error codes are preserved in execution evidence.
- `ELEMENT_NOT_FOUND` no longer becomes `environment_failure`.
- Evaluator output and repair recommendations become more specific for real observed failures.
- Non-`fsq-mac` commands continue to classify reasonably via fallback heuristics.

### Validation

```bash
pytest tests/unit/test_executor.py tests/unit/test_evaluator.py tests/integration/test_pipeline_runtime.py -q
```

Targeted evidence checks using the current real scenarios:

```bash
FSQ_MAC_CLI=/Users/qunmi/Documents/github/fsq-mac/.venv/bin/mac python3 -m src.cli run "Click on 'Submit' button" --json
FSQ_MAC_CLI=/Users/qunmi/Documents/github/fsq-mac/.venv/bin/mac python3 -m src.cli run "Type 'hello world'" --json
```

Expected result:

- `Click on 'Submit' button` classifies as `observation_insufficient`
- `Type 'hello world'` classifies according to the actual `fsq-mac` code path, not generic retry text

---

## Dependency Order

- `Workstream A` may begin immediately.
- `Workstream B` may also begin immediately, but it is better to land it after `Workstream A` if you want cleaner end-to-end interpretation of new context-aware failures.
- Real E2E validation should be rerun after each workstream, not only at the end.

Recommended order:

1. `Workstream B` first if the immediate goal is better observability with minimal behavior change.
2. `Workstream A` first if the immediate goal is fewer user-visible failures for grounded goals.

Recommended practical sequence:

1. Implement `Workstream B` enough to get trustworthy classifications.
2. Use that improved visibility while implementing `Workstream A`.

---

## Rollback Strategy

- Keep the classification parser behind narrow helpers so fallback text classification remains intact if structured parsing proves brittle.
- Do not remove existing regex rules until code-based mappings are validated against real evidence.
- Land context grounding in small commits, ideally one for parser/goal shape and one for plan/compiler propagation.

---

## Exit Criteria

This follow-up plan is complete when all of the following are true:

- grounded `type` and `click` goals are represented explicitly in the plan model
- ungrounded goals are visibly ambiguous rather than silently overpromising
- structured `fsq-mac` errors survive into evidence
- `ELEMENT_NOT_FOUND` and similar runtime failures are no longer mislabeled as `environment_failure`
- real E2E results are easier to interpret and debug from stored `evidence.json` alone
