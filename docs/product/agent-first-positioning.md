# Agent-First Product Boundary

## Positioning

Goal-Driven Automation is an agent-first execution core for macOS automation. It is designed to be called by an upper-layer coding agent, not to act as a standalone end-user testing product.

## Upper-Layer Agent Responsibilities

- Own user interaction and conversation flow.
- Own LLM configuration, prompting, and model selection.
- Translate user intent into repository assets or run requests.
- Summarize run results back into user-readable output.

## Repository Responsibilities

- Parse goals into internal execution plans.
- Compile plans into runtime-capable commands.
- Execute steps through `fsq-mac`.
- Persist evidence, evaluation, and repair outputs.
- Provide stable asset contracts for `case`, `suite`, and `run result` workflows.

## User-Facing Model

Non-technical requesters should interact with the system through an upper-layer coding agent. That agent should speak in terms of:

- `case`
- `suite`
- `run result`

It should avoid exposing internal implementation details such as `tests/unit`, compiler modules, or schema internals.

## Non-Goals

- Built-in end-user conversational UX in this repository.
- First-class LLM API configuration stored and managed here.
- A second autonomous agent layer inside this repository.
- Treating repository regression tests as the main user-facing asset model.
