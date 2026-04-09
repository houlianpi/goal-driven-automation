# Post-Remediation Hygiene Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Finish the highest-value non-mainline cleanup work left after runtime remediation without destabilizing the repaired execution path.

**Architecture:** Treat this as a packaging, tooling, and maintenance pass rather than a product rewrite. Keep the runtime pipeline untouched unless a hygiene fix directly improves reproducibility or developer confidence. Prefer narrow, reversible changes with explicit regression checks after each task.

**Tech Stack:** Python 3.13, pytest, shell scripts, Markdown docs, HTML report generators.

---

## Scope

This plan covers the deferred follow-up items from the remediation roadmap that are important but not part of the repaired runtime core:

- document install and test flows in `README.md`
- fix `scripts/run_poc.sh` parent-shell counter bug
- reduce report-generator sprawl behind one supported entrypoint
- audit and clean empty placeholder packages where safe

Out of scope for this pass:

- changes to `Pipeline`, `Executor`, `Compiler`, or evidence semantics
- broad renames such as replacing `AssertionResult` compatibility aliases
- UI redesign of generated HTML reports beyond necessary consolidation

Preconditions already satisfied before this plan starts:

- `pyproject.toml` already exists and is the repository's dependency-management source of truth.
- `scripts/annotate_screenshot.py` no longer uses a bare `except:` and does not require a new hygiene task unless a broader script refactor is undertaken.

## Delivery Rules

- keep each task independently verifiable
- do not break existing script invocation patterns without a compatibility shim
- prefer one canonical report entrypoint rather than four separate supported paths
- remove empty package files only after confirming they are not needed for imports or test discovery

## Recommended Order

1. Document installation and test flow.
2. Fix `run_poc.sh` correctness.
3. Consolidate report generation behind one supported CLI.
4. Clean placeholder packages and empty files.

---

## Task 1: Document Setup And Validation Flow

**Files:**
- Modify: `README.md`
- Reference: `pyproject.toml`

**Step 1: Write the failing documentation checklist**

Add a short checklist to the plan issue or commit notes stating that the repository must explain:

- how to install runtime dependencies
- how to install dev dependencies
- how to run the full test suite
- how to run a sample dry-run pipeline command

**Step 2: Inspect current repo metadata**

Run: `sed -n '1,220p' README.md`
Expected: README contains architecture notes but not installation or test instructions.

Run: `sed -n '1,220p' pyproject.toml`
Expected: dependency and pytest configuration exist and should be reflected in docs.

**Step 3: Update `README.md` with minimal working instructions**

Add sections for:

- prerequisites: Python 3.13
- install: `pip install -e .` and `pip install -e .[dev]`
- test: `pytest -q`
- dry run example: `python -m src.cli run "Open Edge and create new tab" --dry-run`

Keep the existing architecture content and avoid turning the README into a long design document.

**Step 4: Verify commands are consistent with current repo state**

Run: `pytest -q`
Expected: PASS.

Optional consistency check:

Run: `python -m src.cli run "Open Edge and create new tab" --dry-run`
Expected: either the dry-run path works, or any failure is recorded as an out-of-scope CLI issue for later follow-up.

Do not repair `src.cli` in this plan unless the failure is caused directly by the documentation change itself.

**Step 5: Commit**

```bash
git add README.md
git commit -m "docs: add setup and test instructions"
```

---

## Task 2: Fix `run_poc.sh` Counter Semantics

**Files:**
- Modify: `scripts/run_poc.sh`
- Optional Test: `tests/integration/test_run_poc_script.py`

**Step 1: Write the failing reproduction note**

Document the shell bug: variables updated inside the `while` loop are lost because the loop is fed by a pipe and runs in a subshell.

**Step 2: Reproduce the control-flow issue locally**

Run: `sed -n '1,220p' scripts/run_poc.sh`
Expected: the `while` loop is fed by `python3 -c ... | while ...`, confirming subshell execution.

**Step 3: Replace pipe-fed loop with parent-shell input redirection**

Use process substitution:

```bash
while IFS="|" read -r id goal; do
  ...
done < <(python3 -c "...")
```

Also add a final summary line that prints `TOTAL`, `PASSED`, `FAILED`, and `REPAIRED` so the fix is externally visible.

**Step 4: Validate shell syntax**

Run: `bash -n scripts/run_poc.sh`
Expected: no output, exit code `0`.

**Step 5: Add or skip automated regression test intentionally**

Preferred: add a small script-level regression test only if the repository already has a stable pattern for shell-script tests.

If skipped, note in the final summary that this was validated by syntax plus logic inspection rather than automated execution.

**Step 6: Commit**

```bash
git add scripts/run_poc.sh
git commit -m "fix: preserve poc counters in parent shell"
```

---

## Task 3: Consolidate Report Generation Entry Point

**Files:**
- Modify: `scripts/generate_report.py`
- Review: `scripts/generate_report_v2.py`
- Review: `scripts/generate_report_v3.py`
- Review: `scripts/generate_html_report.py`
- Optional Modify: `README.md`

**Step 1: Inventory report script overlap**

Review the four existing scripts and record:

- which input directory layout each expects
- whether each emits HTML
- whether screenshots are embedded or linked
- whether any are still referenced elsewhere in docs or scripts

**Step 2: Choose one supported entrypoint**

Recommended direction:

- keep `scripts/generate_report.py` as the canonical public entrypoint
- either fold the best behavior from `v2`/`v3` into it, or turn the older variants into compatibility wrappers that delegate to the canonical implementation

Do not keep four first-class scripts with overlapping responsibilities.

**Step 3: Implement the smallest consolidation**

Preferred low-risk option:

- leave the legacy scripts in place temporarily
- make each legacy script print a deprecation note or import and call the canonical implementation
- document one supported command only

This keeps external invocations from breaking while shrinking maintenance surface.

**Step 4: Verify the canonical script interface**

Run one of:

- `python3 scripts/generate_report.py --help`
- or, if no CLI parser exists, execute the script against a small fixture directory

Expected: the canonical script runs without syntax errors and the legacy path still resolves.

**Step 5: Update docs if command names changed**

If the supported report command changes, reflect that in `README.md` or the relevant plan docs.

**Step 6: Commit**

```bash
git add scripts/generate_report.py scripts/generate_report_v2.py scripts/generate_report_v3.py scripts/generate_html_report.py README.md
git commit -m "refactor: consolidate report generation entrypoint"
```

---

## Task 4: Audit Empty Packages And Placeholder Files

**Files:**
- Review: `src/__init__.py`
- Review: `src/compiler/__init__.py`
- Review: `src/executor/__init__.py`
- Review: `src/goal_interpreter/__init__.py`
- Review: `src/planner/__init__.py`
- Review: `src/schemas/__init__.py`
- Review: `tests/__init__.py`
- Review: `tests/unit/__init__.py`
- Review: `tests/integration/__init__.py`
- Review: `.gitkeep` files under `tests/`

**Step 1: Identify which empty files are structurally required**

Check whether any imports depend on package markers or whether namespace-package behavior is already sufficient under Python 3.13.

**Step 2: Remove only files with no compatibility value**

Candidates to delete if confirmed unused:

- empty `tests/__init__.py`
- empty `tests/unit/__init__.py`
- empty `tests/integration/__init__.py`
- stale `.gitkeep` files in directories that now contain real tests

Be conservative with `src/.../__init__.py` removals if packaging or import style could be affected.

**Step 3: Re-run test discovery after cleanup**

Run: `pytest -q`
Expected: PASS with identical test count or an intentional, explained delta.

**Step 4: Commit**

```bash
git add tests src
git commit -m "chore: remove empty placeholder files"
```

---

## Final Validation Sweep

Run after all tasks are complete:

```bash
bash -n scripts/run_poc.sh
pytest -q
```

Optional manual validation if local data exists:

```bash
python -m src.cli run "Open Edge and create new tab" --dry-run
python3 scripts/generate_report.py
```

If the `src.cli` dry-run command fails, record the failure and stop at triage. CLI repair is outside this hygiene plan unless the breakage was introduced by work in this plan.

## Exit Criteria

- `README.md` explains installation and test execution.
- `run_poc.sh` prints correct counters from the parent shell.
- one report script is documented as canonical and legacy variants are no longer equal-status entrypoints.
- empty placeholder files are reduced where safe.
- `pytest -q` still passes at the end.
