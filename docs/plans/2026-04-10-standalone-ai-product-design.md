# Standalone AI Product Design

**Date:** 2026-04-10
**Status:** Approved
**Supersedes:** None (coexists with agent-first-product-shape-design.md as an alternative direction)

## Goal

Define the product shape for Goal-Driven Automation as a standalone AI-powered macOS GUI testing product. Users write natural language goals in YAML files, and the system plans, executes, verifies, and repairs autonomously using built-in LLM capabilities.

## Decision Summary

| Decision | Choice |
|----------|--------|
| Target users | QA engineers, non-technical testers, product managers |
| Product role | Standalone AI product with built-in LLM |
| LLM integration | Multi-provider pluggable (Claude / GPT / Gemini) |
| User input | Natural language goals in YAML files |
| Interface | CLI execution + GitHub for test management + HTML reports via GitHub Pages |
| LLM scope | All pipeline stages: parsing, planning, visual verification, repair, runtime decisions |
| Test file format | YAML |
| Architecture | Progressive AI injection into existing pipeline |

## Problem Being Solved

Two core questions were unresolved:

1. Should this product embed its own LLM, or serve as a tool layer for an external AI agent?
2. How should non-technical users define and manage tests without touching code?

This design resolves both:

- The product embeds LLM capabilities directly, so users need only an API key to get started.
- Users write simple YAML files with natural language goals. No code required.
- Tests are stored in a Git repo, executed via CLI, and results viewable as HTML reports.

## Product Overview

**One-line positioning:** Write macOS GUI tests in natural language. AI plans, executes, verifies, and repairs automatically.

### User Workflow

```
User (any role)                         GDA System
──────────────                    ──────────────
1. Create YAML file in repo
   tests/edge-new-tab.goal.yaml  →

2. CLI execution
   gda run tests/                →  LLM parses goal
                                 →  LLM generates Plan IR
                                 →  Compiler → fsq-mac commands
                                 →  Executor runs commands
                                 →  LLM verifies via screenshots
                                 →  (on failure) LLM repairs
                                 →  Generates HTML report

3. View results
   gda report --open             →  Opens HTML report
   (or GitHub Pages auto-deploy)
```

### CLI Commands

```bash
# Execute a single test
gda run tests/edge-new-tab.goal.yaml

# Execute all tests in a directory
gda run tests/

# Filter by tag
gda run tests/ --tags smoke

# Dry run (plan only, no execution)
gda run tests/edge-new-tab.goal.yaml --dry-run

# Generate report
gda report data/runs/latest/ --format html

# Configure LLM
gda config set llm.provider claude
gda config set llm.api_key sk-xxx
```

## YAML Test File Format

### Basic Format (for all users including non-technical)

```yaml
# tests/edge-new-tab.goal.yaml
name: Edge New Tab
app: Microsoft Edge
tags: [smoke, edge, tab]

goal: |
  Open Edge browser, create a new tab,
  then verify the tab count increased.
```

Only `goal:` is required. All other fields are optional metadata for organization and filtering.

### Extended Format (for QA engineers)

```yaml
# tests/safari-navigate.goal.yaml
name: Safari Multi-Tab Navigation
app: Safari
tags: [regression, safari, navigation]
priority: high

goal: |
  Open Safari, create 3 new tabs,
  navigate to github.com, google.com, and apple.com respectively,
  verify each tab title is correct.

config:
  timeout_ms: 60000
  max_repair_attempts: 3
  screenshot_on_failure: true
```

### Suite Format (for batch execution)

```yaml
# tests/suites/smoke.suite.yaml
name: Smoke Tests
description: Daily smoke tests
schedule: daily

include:
  - tests/edge-new-tab.goal.yaml
  - tests/safari-navigate.goal.yaml
  - tags: [smoke]
exclude:
  - tags: [slow, flaky]
```

### Directory Convention

```
tests/
├── edge-new-tab.goal.yaml
├── safari-navigate.goal.yaml
├── finder-new-folder.goal.yaml
├── suites/
│   ├── smoke.suite.yaml
│   └── regression.suite.yaml
└── README.md
```

## LLM Abstraction Layer

### Architecture

```
Pipeline stages
    │
    ▼
LLMClient (unified interface)
    │
    ├── ClaudeProvider    ← Anthropic API
    ├── OpenAIProvider    ← OpenAI API
    ├── GeminiProvider    ← Google Gemini API
    └── OllamaProvider    ← Local models (optional)
```

### Configuration

```yaml
# gda.config.yaml (project root)
llm:
  default_provider: claude

  providers:
    claude:
      api_key: ${ANTHROPIC_API_KEY}
      model: claude-sonnet-4-6
    openai:
      api_key: ${OPENAI_API_KEY}
      model: gpt-4o

  # Route tasks to different models (optional)
  routing:
    goal_parsing: claude
    plan_generation: claude
    visual_verification: openai
    repair_analysis: claude
```

### Interface

```python
class LLMClient:
    def complete(self, prompt: str, ...) -> str
    def complete_with_image(self, prompt: str, images: list[Path], ...) -> str
    def complete_structured(self, prompt: str, schema: dict, ...) -> dict
```

Three core methods:
- `complete` — text interaction (goal parsing, repair analysis)
- `complete_with_image` — multimodal interaction (screenshot verification, UI state analysis)
- `complete_structured` — returns structured JSON (plan generation, evaluation results)

## Progressive AI Injection Roadmap

### Phase 0: LLM Abstraction Layer (prerequisite for all phases)

Build `src/llm/` with `LLMClient`, provider base class, and Claude provider as first implementation.

### Phase 1: LLM Goal Interpreter

**Replaces:** GoalParser (regex matching) + PlanGenerator (if/elif templates)

**Current state:** Can only handle predefined patterns like "Open Edge and create new tab".

**After:** LLM understands arbitrary natural language goals and generates structured Plan IR.

```
User YAML goal text
    │
    ▼
LLM Goal Interpreter
  Input: goal text + registry/actions.yaml (available capabilities)
  Output: structured Plan IR JSON
    │
    ▼
Schema Validator (existing) → validates Plan IR
    │
    ▼
Compiler (existing) → Plan IR → fsq-mac commands
```

The LLM prompt receives the registry (available actions) and Plan IR schema (output format), then converts natural language into a valid Plan IR.

**Why first:** This immediately enables non-technical users — just write `goal:` in YAML, AI generates the full execution plan.

### Phase 2: LLM Visual Verification

**Enhances:** Evaluator (currently only checks command return codes)

**After:** Takes screenshots after each step, LLM analyzes whether the goal was achieved.

```
Step completes
    │
    ├── Screenshot (mac capture screenshot)
    ├── UI Tree (mac capture ui-tree)
    │
    ▼
LLM Visual Verifier
  Input: screenshot + UI tree + step's expected outcome
  Output: {passed: bool, confidence: float, reason: string}
```

**Why second:** Moves test confidence from "command succeeded" to "AI verified correct UI state".

### Phase 3: LLM Smart Repair

**Enhances:** RepairLoop (currently: retry → restart → replan → skip chain)

**After:** LLM analyzes failure context (stderr + screenshot + UI tree) and generates targeted repair plans.

```
Step fails
    │
    ├── Error (stderr)
    ├── Current screenshot
    ├── UI Tree
    │
    ▼
LLM Repair Analyzer
  Analysis: "Address bar not focused because popup is blocking"
  Repair plan: [close popup, retry click address bar, type URL]
    │
    ▼
Compiler + Executor (execute repair plan)
```

### Phase 4: LLM Runtime Decisions

**Enhances:** Executor (currently: sequential command execution)

**After:** LLM observes current state after each step and decides the next action.

```
while not goal_reached:
    execute(next_step)
    observe(screenshot + ui_tree)
    decision = LLM.decide(goal, current_state, remaining_plan)
    if decision == "continue": next_step = plan.next()
    if decision == "adapt":    next_step = decision.adapted_step
    if decision == "abort":    break
```

**Why last:** Most complex, depends on Phase 2 (visual verification) and Phase 3 (repair).

### Phase Dependencies

```
Phase 0: LLM Abstraction Layer (prerequisite for all)
Phase 1: Goal Interpreter (independent)
Phase 2: Visual Verification (independent, benefits from Phase 1 Plan IR quality)
Phase 3: Smart Repair (benefits from Phase 2 visual information)
Phase 4: Runtime Decision (depends on Phase 2 + Phase 3)
```

## Backward Compatibility and Fallback

### Core Principle

The system must not break when LLM is unavailable.

```
LLM available?
  ├── YES → LLM Goal Interpreter → Plan IR → compile/execute
  └── NO  → Existing rule engine (GoalParser + PlanGenerator) → Plan IR → compile/execute
```

### Implementation

- Existing `GoalParser` and `PlanGenerator` are preserved as `RuleBasedInterpreter`
- New `LLMGoalInterpreter` added alongside
- Pipeline checks LLM configuration at initialization
- LLM API failures automatically fall back to rule engine
- Every fallback is logged for debugging

### Configuration

```yaml
# gda.config.yaml
pipeline:
  goal_interpreter: auto    # auto | llm | rules
  # auto = use LLM if configured, otherwise use rules
  # llm  = force LLM, fail on error
  # rules = force rule engine, never call LLM
```

### Testing Strategy

- All existing 111 unit tests use rule engine (no LLM dependency, no API cost)
- New LLM integration tests marked with `@pytest.mark.llm`, run only when API key is present
- CI: rule engine tests must pass, LLM tests are optional

## File Structure Changes

```
src/
├── llm/                          # NEW: LLM abstraction layer
│   ├── __init__.py
│   ├── client.py                 # LLMClient unified interface
│   ├── providers/
│   │   ├── __init__.py
│   │   ├── claude.py             # Claude provider
│   │   ├── openai.py             # OpenAI provider
│   │   └── base.py               # Provider base class
│   └── config.py                 # LLM configuration loading
│
├── goal_interpreter/             # NEW: replaces GoalParser + PlanGenerator
│   ├── __init__.py
│   ├── llm_interpreter.py        # LLM-driven goal interpreter
│   ├── rule_interpreter.py       # Existing rule engine (refactored from GoalParser + PlanGenerator)
│   └── prompts/
│       └── goal_to_plan.py       # LLM prompt templates
│
├── pipeline/
│   ├── pipeline.py               # MODIFIED: supports interpreter switching
│   ├── goal_parser.py            # PRESERVED: underlies rule_interpreter
│   └── plan_generator.py         # PRESERVED: underlies rule_interpreter
│
├── evaluator/
│   └── visual_verifier.py        # NEW Phase 2: LLM screenshot verification
│
├── repair/
│   └── llm_repair.py             # NEW Phase 3: LLM repair analysis
│
└── executor/
    └── adaptive_executor.py      # NEW Phase 4: LLM runtime decisions

# Project root
gda.config.yaml                   # NEW: product configuration file
```

## Non-Goals

- A standalone visual UI or web dashboard
- Replacing fsq-mac with a different execution backend
- Building a general-purpose autonomous agent
- Supporting non-macOS platforms
