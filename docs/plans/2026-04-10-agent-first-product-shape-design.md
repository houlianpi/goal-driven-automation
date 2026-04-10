# Agent-First Product Shape Design

**Date:** 2026-04-10

## Goal

Define the product shape for Goal-Driven Automation so the repository has a clear role in an AI-agent stack, a clear user entrypoint, and a clear model for managing test assets without exposing low-level code structure to non-technical requesters.

## Decision Summary

The repository should be positioned as an agent-first execution core, not as a standalone end-user testing product.

- Primary product role: bottom-layer automation and evidence pipeline for a coding agent.
- Primary user entrypoint: an upper-layer coding agent, not direct human use of this repository.
- LLM ownership: the upper-layer agent owns LLM configuration, prompting, and conversation state.
- Repository responsibility: parse goals, generate plans, compile executable steps, execute them, collect evidence, evaluate outcomes, and support repair.
- Discoverability layer: skills explain how an agent should use the repository and what outputs it can expect.
- Asset model: user-facing objects should become `case`, `suite`, and `run result`, rather than `tests/unit`, `tests/integration`, or internal source directories.

## Problem Being Solved

Two unresolved product questions were blocking direction:

1. Whether this repository should be a self-contained AI product with its own LLM API configuration, or a lower-level tool invoked by another agent.
2. How non-code users should interact with test cases and batch execution when the current repository shape is organized around engineering concerns.

The chosen direction resolves both by separating responsibilities:

- the upper-layer coding agent handles user interaction and intent interpretation
- this repository handles deterministic execution and evidence
- Git manages versioned test assets, but users do not need to understand the implementation directories directly

## Recommended Product Shape

### 1. System Role

Goal-Driven Automation is an execution kernel for agent-driven testing on macOS.

It is responsible for:

- taking a structured or natural-language goal handed to it by an agent
- converting that goal into an internal plan representation
- compiling the plan into runtime-capable commands
- executing those commands through `fsq-mac`
- collecting evidence, evaluation, and repair outputs

It is not responsible for:

- owning a conversational UX for end users
- storing or managing user API keys as a primary workflow
- acting as a general-purpose autonomous agent product
- teaching non-technical users the source-code layout of the repository

### 2. User Model

The real end user may still be a non-technical tester, PM, or operator, but their interaction path should be mediated by a coding agent.

Expected user journey:

1. The user asks the coding agent to create, update, or run tests.
2. The coding agent maps the request to repository assets and execution calls.
3. This repository executes and returns structured evidence.
4. The coding agent translates results back into user-readable summaries.

This keeps the repository agent-first while still supporting non-code requesters indirectly.

### 3. LLM Ownership

The mainline product should not add its own required LLM API configuration.

Rationale:

- it avoids duplicated agent logic
- it keeps architecture boundaries clean
- it prevents the repository from evolving two competing product modes
- it reduces operational complexity around model choice, prompt management, and secrets

If direct LLM integration is ever added, it should remain an explicitly secondary mode and not redefine the core positioning.

## Skill Layer Design

Skills should serve as an agent-facing discoverability and onboarding layer.

They should explain:

- what the tool can do
- when to use it
- when not to use it
- what input shape the agent should prepare
- what artifacts the agent should read after execution

Recommended minimum skill set:

### Capability Intro Skill

Purpose:

- explain repository purpose and system boundaries
- list supported goal types and output artifacts
- describe common success and failure paths

### Test Authoring Skill

Purpose:

- teach the agent how to create and modify user-facing test assets
- explain naming, tags, app coverage, and grouping rules
- keep asset creation aligned with repository conventions

### Batch Execution And Reporting Skill

Purpose:

- teach the agent how to execute cases or suites in bulk
- explain how to locate evidence and summarize failures
- define what information should be surfaced back to the user

These skills are not alternate execution engines. They are operational guidance for correct use of the execution engine.

## Test Asset Model

The current repository has engineering tests under `tests/`, but product-facing test assets should be modeled separately.

Recommended future asset layers:

- `cases/` or `data/cases/`
  Human-meaningful test case definitions expressed in a structured file format.
- `suites/` or `data/suites/`
  Batchable groupings of cases, either by explicit membership or by tags.
- `runs/` or existing evidence directories under `data/`
  Generated outputs such as evidence, screenshots, summaries, and repair outcomes.

### User-Facing Concepts

The upper-layer agent should talk in terms of:

- test case
- test suite
- run result

It should avoid exposing internal implementation concepts such as:

- unit test directory
- integration test directory
- compiler module
- schema validator

### Why Git Still Matters

Git remains useful because it gives:

- version history for cases and suites
- reviewable asset changes through commits or pull requests
- branch-specific validation during development work
- a safe path for agent-generated updates

But Git is an implementation detail of the operating model, not the primary mental model for non-technical requesters.

## Proposed Information Architecture

The product should converge on this conceptual structure:

- `src/`
  Execution engine internals.
- `tests/`
  Repository regression tests for the engine itself.
- `data/cases/`
  User-facing case assets.
- `data/suites/`
  User-facing batch execution groupings.
- `data/runs/`
  Execution outputs and evidence.
- `.agents/skills/` or equivalent skill location
  Agent-facing usage guidance.

This separates framework validation from product-facing automation assets.

## Core Product Principle

The repository should optimize for this sentence:

> A coding agent can reliably create, organize, batch-execute, and summarize natural-language test assets on behalf of a non-technical requester.

## Non-Goals

The following should not be treated as immediate requirements for this product shape:

- a standalone visual UI for end users
- direct end-user editing of repository internals
- full self-service LLM configuration inside this repository
- replacing the upper-layer coding agent with a second built-in agent layer

## Immediate Next Steps

1. Define the exact `case`, `suite`, and `run` asset contract.
2. Add agent-facing skills that explain repository capabilities and workflows.
3. Update repository documentation so the agent-first positioning is explicit.
4. Create an implementation plan that sequences asset-model work before broader UX or automation expansion.
