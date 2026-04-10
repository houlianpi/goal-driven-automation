---
name: goal-driven-automation-capability-intro
description: Use when an upper-layer coding agent needs to understand this repository's role, supported workflows, and output artifacts before creating or running product-facing automation assets.
---

# Goal-Driven Automation Capability Intro

## When To Use

Use this repository when a coding agent needs a macOS automation execution core that can:

- accept a natural-language goal
- generate and compile an execution plan
- execute through `fsq-mac`
- persist evidence and evaluation artifacts
- run user-facing `case` and `suite` assets

## Repository Role

This repository is agent-first. It is not the main end-user conversational surface.

- The upper-layer coding agent owns user interaction, LLM choice, prompts, and conversation context.
- This repository owns execution, evidence, evaluation, and repair.

## Supported Workflows

- Run one natural-language goal with `python3 -m src.cli run "<goal>"`
- Run one `case` asset with `python3 -m src.cli run-case <path>`
- Run one `suite` asset with `python3 -m src.cli run-suite <path>`

## User-Facing Concepts

When talking to users, prefer:

- `case`
- `suite`
- `run result`

Avoid exposing internal implementation concepts such as compiler modules or repository test directories.

## Outputs To Read

- `data/runs/<run_id>/evidence.json`
- `data/runs/<run_id>/input_plan.json`
- pipeline result data returned by the CLI JSON mode

## Non-Goals

- Built-in LLM configuration in this repository
- Standalone end-user UI
- Asking non-technical users to work directly with engine internals
