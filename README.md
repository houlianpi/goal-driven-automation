# Goal-Driven Automation

Agent-First Automation Pipeline for macOS applications.

## Architecture

```
Human Goal → Goal Interpreter → Plan IR → Capability Compiler → fsq-mac CLI → Evidence Collector → Evaluator/Repair Loop → Human Review
```

## Project Status

| Phase | Description | Status |
|-------|-------------|--------|
| Phase 0 | Reset POC Baseline | 🔄 In Progress |
| Phase 1 | Core Schemas | ⏳ Planned |
| Phase 2 | Capability Registry | ⏳ Planned |
| Phase 3 | Compiler + Executor | ⏳ Planned |
| Phase 4 | Evidence Layer | ⏳ Planned |
| Phase 5 | Evaluator + Classifier | ⏳ Planned |
| Phase 6 | Repair/Replan Loop | ⏳ Planned |
| Phase 7 | Memory + Evolution | ⏳ Planned |
| Phase 8 | E2E Validation | ⏳ Planned |
| Phase 9 | Credible POC | ⏳ Planned |

## Getting Started

See [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) for the full implementation plan.

## Tech Stack

- Python
- fsq-mac CLI
- Appium Mac2
- YAML (Goals)
- JSON (Plan IR, Evidence)
