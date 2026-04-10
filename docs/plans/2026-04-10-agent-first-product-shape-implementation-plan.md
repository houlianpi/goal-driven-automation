# Agent-First Product Shape Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reposition the repository as an agent-first automation core by documenting clear product boundaries, defining user-facing test asset models, and adding the minimum skill and documentation surface an upper-layer coding agent needs to use it correctly.

**Architecture:** Treat this as a product-shape and contract pass, not a runtime rewrite. The target model is: upper-layer coding agent owns conversation and LLM behavior; this repository owns execution and evidence; skills document how the agent should create `case` and `suite` assets and how it should execute and summarize them.

**Tech Stack:** Markdown docs, YAML or JSON asset schemas, Python 3.13, pytest, repository-local skills, Git-managed test assets.

---

## Scope

This plan covers:

- making the agent-first product positioning explicit in repository docs
- defining a first-class `case` / `suite` / `run` information model
- separating user-facing test assets from engine regression tests
- adding the minimum skill surface required for agent discoverability and correct usage
- documenting the core user paths the upper-layer agent should support

Out of scope for this pass:

- changing the main execution runtime beyond what new asset loading requires
- adding built-in LLM API configuration or prompt orchestration to this repository
- building a GUI or standalone end-user application
- redesigning `fsq-mac` itself

## Delivery Rules

- keep the repository's runtime contracts stable unless a task explicitly extends them
- define user-facing concepts before adding new storage or CLI behavior
- prefer additive documentation and schema work before loader or executor changes
- keep product assets under `data/` or another explicit product-facing namespace, not under `tests/`
- every new contract must have a schema or equivalent validation path plus focused tests

## Recommended Order

1. Document the agent-first product boundary.
2. Define the `case` and `suite` asset contracts.
3. Add example assets and validation coverage.
4. Add skill documentation for agent onboarding.
5. Add batch-oriented loading and execution entrypoints only after the asset model is stable.

---

### Task 1: Document Agent-First Product Boundary

**Files:**
- Modify: `README.md`
- Create: `docs/product/agent-first-positioning.md`
- Reference: `docs/plans/2026-04-10-agent-first-product-shape-design.md`

**Step 1: Write the failing documentation checklist**

Record that the repository docs currently do not make these points explicit:

- the repository is an execution core for a coding agent
- it is not primarily a standalone end-user testing product
- LLM ownership lives in the upper-layer agent
- user-facing objects should be `case`, `suite`, and `run result`

**Step 2: Inspect current docs before editing**

Run: `sed -n '1,220p' README.md`
Expected: the README describes architecture and setup, but not a clear product boundary or user model.

**Step 3: Add the product-boundary documentation**

Update `README.md` to include:

- a short product positioning section
- an explicit statement that upper-layer agents own LLM behavior
- a short explanation of where end users fit

Create `docs/product/agent-first-positioning.md` with:

- responsibilities of the upper-layer agent
- responsibilities of this repository
- non-goals such as built-in end-user UX and first-class LLM config

**Step 4: Review for consistency**

Run: `rg -n "LLM|agent-first|case|suite|run result" README.md docs/product/agent-first-positioning.md`
Expected: the new terms appear consistently and without contradiction.

**Step 5: Commit**

```bash
git add README.md docs/product/agent-first-positioning.md
git commit -m "docs: define agent-first product boundary"
```

---

### Task 2: Define The `case` Asset Contract

**Files:**
- Create: `schemas/test-case.schema.json`
- Create: `data/cases/examples/smoke-open-edge.json`
- Create: `docs/product/test-case-model.md`
- Test: `tests/unit/test_case_schema.py`

**Step 1: Write the failing schema test**

Add a unit test that loads a minimal case document and asserts it validates.

Example test shape:

```python
def test_minimal_test_case_schema_accepts_basic_case():
    case = {
        "id": "case-open-edge",
        "title": "Open Edge",
        "goal": "Open Edge",
        "tags": ["smoke", "edge"],
        "apps": ["Microsoft Edge"],
    }
    ok, errors = SchemaValidator().validate_document(case, "schemas/test-case.schema.json")
    assert ok is True, errors
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_case_schema.py::test_minimal_test_case_schema_accepts_basic_case -v`
Expected: FAIL because the schema or validator path does not yet exist.

**Step 3: Write the minimal schema**

Create `schemas/test-case.schema.json` with fields such as:

- `id`
- `title`
- `goal`
- `tags`
- `apps`
- `priority`
- `owner`
- `enabled`

Keep the first version intentionally small and avoid step-level DSL design in this pass.

**Step 4: Add one example asset**

Create `data/cases/examples/smoke-open-edge.json` using the new schema.

**Step 5: Document the model**

Create `docs/product/test-case-model.md` explaining:

- what a case is
- which fields are required
- which fields are for filtering and reporting only
- how a coding agent should create new cases

**Step 6: Run test to verify it passes**

Run: `pytest tests/unit/test_case_schema.py -v`
Expected: PASS.

**Step 7: Commit**

```bash
git add schemas/test-case.schema.json data/cases/examples/smoke-open-edge.json docs/product/test-case-model.md tests/unit/test_case_schema.py
git commit -m "feat: define test case asset contract"
```

---

### Task 3: Define The `suite` Asset Contract

**Files:**
- Create: `schemas/test-suite.schema.json`
- Create: `data/suites/examples/smoke-core.json`
- Create: `docs/product/test-suite-model.md`
- Test: `tests/unit/test_suite_schema.py`

**Step 1: Write the failing schema test**

Add a unit test that validates a suite with explicit case references.

Example test shape:

```python
def test_minimal_test_suite_schema_accepts_case_references():
    suite = {
        "id": "suite-smoke-core",
        "title": "Core smoke",
        "cases": ["case-open-edge"],
    }
    ok, errors = SchemaValidator().validate_document(suite, "schemas/test-suite.schema.json")
    assert ok is True, errors
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_suite_schema.py::test_minimal_test_suite_schema_accepts_case_references -v`
Expected: FAIL because the suite contract does not yet exist.

**Step 3: Write the minimal schema**

Create `schemas/test-suite.schema.json` with fields such as:

- `id`
- `title`
- `cases`
- `tags`
- `selection`
- `enabled`

The initial version may support either explicit case IDs or simple tag-based selection, but do not add nested execution policy yet unless required by the tests.

**Step 4: Add one example suite**

Create `data/suites/examples/smoke-core.json` that references the example case from Task 2.

**Step 5: Document the model**

Create `docs/product/test-suite-model.md` describing:

- when to use a suite
- the difference between a suite and a case
- how batch execution should consume suites

**Step 6: Run test to verify it passes**

Run: `pytest tests/unit/test_suite_schema.py -v`
Expected: PASS.

**Step 7: Commit**

```bash
git add schemas/test-suite.schema.json data/suites/examples/smoke-core.json docs/product/test-suite-model.md tests/unit/test_suite_schema.py
git commit -m "feat: define test suite asset contract"
```

---

### Task 4: Add Asset Discovery And Batch Execution Contract

**Files:**
- Modify: `src/cli.py`
- Create: `src/assets/loader.py`
- Create: `docs/product/batch-execution.md`
- Test: `tests/unit/test_asset_loader.py`
- Test: `tests/integration/test_batch_cli.py`

**Step 1: Write the failing loader test**

Add a unit test that loads a case file and a suite file from `data/` and resolves suite membership to concrete cases.

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_asset_loader.py::test_suite_resolves_to_case_documents -v`
Expected: FAIL because no asset loader exists yet.

**Step 3: Implement the minimal loader**

Create `src/assets/loader.py` with functions such as:

- `load_case(path)`
- `load_suite(path)`
- `resolve_suite_cases(base_dir, suite)`

Keep the implementation simple and filesystem-based.

**Step 4: Add a batch CLI entrypoint**

Extend `src/cli.py` with a command shape such as:

- `python -m src.cli run-case <path>`
- or `python -m src.cli run-suite <path>`

The first version may expand the suite into multiple goal runs and print a summary without introducing a job queue.

**Step 5: Add documentation**

Create `docs/product/batch-execution.md` showing:

- how the upper-layer agent should choose a case or suite
- how batch results are summarized
- where evidence is stored

**Step 6: Run focused tests**

Run: `pytest tests/unit/test_asset_loader.py tests/integration/test_batch_cli.py -v`
Expected: PASS.

**Step 7: Commit**

```bash
git add src/cli.py src/assets/loader.py docs/product/batch-execution.md tests/unit/test_asset_loader.py tests/integration/test_batch_cli.py
git commit -m "feat: add case and suite batch execution entrypoints"
```

---

### Task 5: Add Agent-Facing Skills For Repository Usage

**Files:**
- Create: `.agents/skills/goal-driven-automation-capability-intro/SKILL.md`
- Create: `.agents/skills/goal-driven-automation-test-authoring/SKILL.md`
- Create: `.agents/skills/goal-driven-automation-batch-execution/SKILL.md`
- Optional Create: `.agents/plugins/marketplace.json`
- Reference: `docs/product/agent-first-positioning.md`
- Reference: `docs/product/test-case-model.md`
- Reference: `docs/product/test-suite-model.md`
- Reference: `docs/product/batch-execution.md`

**Step 1: Write the failing usage checklist**

Record that an upper-layer agent currently lacks repository-local guidance for:

- when to use this repository
- how to create a case asset
- how to run a suite and summarize results

**Step 2: Review local skill conventions**

Run: `find . -maxdepth 3 -path './.agents/skills/*/SKILL.md'`
Expected: either existing local skill structure is present to copy, or the repository has no local skills and needs a minimal new convention.

**Step 3: Add the capability intro skill**

Document:

- repository role
- supported workflows
- clear non-goals
- expected outputs and artifact paths

**Step 4: Add the test authoring skill**

Document:

- how to create `case` assets
- naming, tags, and app metadata rules
- how to avoid leaking low-level engine internals into user-facing assets

**Step 5: Add the batch execution skill**

Document:

- how to choose between case and suite execution
- how to summarize failures for users
- how to reference evidence paths in the reply

**Step 6: Review for consistency**

Run: `rg -n "case|suite|run result|agent-first|LLM" .agents/skills docs/product`
Expected: terminology aligns across the new skill files and docs.

**Step 7: Commit**

```bash
git add .agents/skills .agents/plugins/marketplace.json docs/product
git commit -m "docs: add agent onboarding skills for product workflows"
```

---

### Task 6: Add Run Summary Contract For Agent Consumption

**Files:**
- Modify: `src/pipeline/pipeline.py`
- Modify: `src/cli.py`
- Create: `docs/product/run-result-model.md`
- Test: `tests/unit/test_pipeline.py`
- Test: `tests/integration/test_pipeline_runtime.py`

**Step 1: Write the failing regression test**

Add a test that asserts the batch or single-run output exposes the minimum fields an upper-layer agent needs, such as:

- run ID
- final status
- passed and failed step counts
- artifact directory

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_pipeline.py::test_run_result_exposes_agent_summary_fields -v`
Expected: FAIL because the current result contract is not framed as a stable agent summary object.

**Step 3: Add the minimal summary contract**

Implement the smallest additive result shape needed so an upper-layer agent can summarize runs without scraping verbose console output.

**Step 4: Document the model**

Create `docs/product/run-result-model.md` describing:

- required fields for agent consumption
- which fields are stable versus diagnostic
- how batch execution should aggregate multiple run results

**Step 5: Run focused tests**

Run: `pytest tests/unit/test_pipeline.py tests/integration/test_pipeline_runtime.py -v`
Expected: PASS.

**Step 6: Commit**

```bash
git add src/pipeline/pipeline.py src/cli.py docs/product/run-result-model.md tests/unit/test_pipeline.py tests/integration/test_pipeline_runtime.py
git commit -m "feat: expose stable run summary contract for agents"
```

---

## Final Validation

Run the focused validation set after all tasks complete:

```bash
pytest tests/unit/test_case_schema.py tests/unit/test_suite_schema.py tests/unit/test_asset_loader.py tests/unit/test_pipeline.py tests/integration/test_batch_cli.py tests/integration/test_pipeline_runtime.py -q
```

Expected result:

- case and suite contracts validate
- batch execution entrypoints resolve assets correctly
- runtime regression coverage remains green
- the repository docs and skills consistently describe the same product shape

## Delivery Outcome

At the end of this plan, the repository should have:

- an explicit agent-first product definition
- a user-facing asset model based on `case`, `suite`, and `run result`
- the minimum skill layer needed for upper-layer agent adoption
- a clear path for non-technical users to work through an upper-layer coding agent instead of direct repository manipulation
