# User Setup & Distribution Model

## Core Principle

GDA is a **tool**, not a project to clone. Users install it as a package and use it through
Claude Code Skills inside their own workspace.

## User Workspace

Users maintain test cases in their own repository or directory — not inside the GDA codebase.

```
my-product-repo/              # or standalone test repo
├── test-cases/
│   ├── smoke-edge.json
│   └── login-flow.json
├── test-suites/
│   └── daily-smoke.json
└── qa-screenshots/           # execution evidence output
```

Case files can live in:

- A dedicated QA repository (e.g. `my-team/edge-test-cases`)
- A subdirectory of a product repository (e.g. `my-product/qa/cases/`)
- Any local directory the user points to

## Installation Flow

No `git clone` required. The Skill should guide users through setup on first use.

| Step | Owner | Command / Action |
|------|-------|------------------|
| 1. Install fsq-mac | Skill guidance | `pip install fsq-mac` |
| 2. Environment check | Skill auto-run | `mac doctor` |
| 3. Fix permissions / Appium | User (manual) | macOS System Settings → Accessibility |
| 4. Install GDA | Skill guidance | `pip install goal-driven-automation` |
| 5. Install Skill | User or Skill | Register skill into Claude Code |
| 6. Start using | Conversation | "帮我跑一下 smoke 测试" |

### What `mac doctor` Checks

- Appium server installed and reachable
- macOS Accessibility permission granted to the terminal / IDE
- Python version compatible
- fsq-mac CLI available on PATH

Users follow `mac doctor` suggested actions to fix any failures.

## Distribution Strategy

| Component | Distribution | Install |
|-----------|-------------|---------|
| fsq-mac | PyPI package | `pip install fsq-mac` |
| GDA engine | PyPI package (planned) | `pip install goal-driven-automation` |
| Claude Code Skill | Skill registry or manual copy | Skill install command |
| Test cases | User's own repo / directory | User-managed |

### Current Gap

GDA is not yet published to PyPI. Until then, users who need the engine pipeline must
install from the Git URL:

```bash
pip install git+https://github.com/houlianpi/goal-driven-automation.git
```

## Skill-Driven Setup

The Skill should include first-run detection logic:

1. Check if `mac` CLI is available → if not, prompt `pip install fsq-mac`
2. Run `mac doctor` → if issues, show fix instructions and pause
3. Check if `goal-driven-automation` is importable → if not, prompt install
4. Proceed with user's request

This means the Skill acts as both the **usage interface** and the **setup wizard**.

## What Users Should NOT Do

- Clone the GDA repository (unless contributing to development)
- Edit GDA source code to configure their test cases
- Store their case files inside the GDA package directory
- Interact with GDA internals (`src/`, `schemas/`, `data/runs/`) directly

## Relationship to Agent-First Positioning

This document complements [agent-first-positioning.md](agent-first-positioning.md):

- **Agent-first positioning** defines the boundary between GDA and the upper-layer agent.
- **This document** defines how real users get from zero to a working setup.

The Skill bridges both sides — it is the upper-layer agent's interface to GDA, and the
user's entry point into the system.
