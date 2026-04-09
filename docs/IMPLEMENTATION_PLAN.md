# Agent-First Automation Pipeline Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a credible agent-first automation prototype where humans provide goals and review results, agents generate and revise plans, and `fsq-mac CLI` is the bottom execution layer.

**Architecture:** The system is organized around `Goal -> Plan IR -> fsq-mac CLI -> Evidence -> Repair`. Humans own goals and review gates, the agent owns planning and adaptation, and `fsq-mac` remains a pure capability layer rather than an intent interpreter.

**Tech Stack:** YAML, Python, `fsq-mac` CLI, Appium Mac2, macOS, pytest, structured JSON artifacts.

---

## Context Summary

This plan consolidates the core decisions reached so far:

- The target is not to help humans write automation faster.
- The target is to let AI generate and maintain automation with minimal human intervention.
- Humans should mainly define goals and review outcomes.
- `.feature` and step files are not the long-term center.
- `fsq-mac CLI` should be the lowest execution layer.
- A stable middle layer is required so the agent can translate human intent into executable actions.
- That middle layer is `Plan IR`, not a new step language.
- Evidence must be recorded as first-class output and then analyzed by the agent.
- Failures should lead to validation, classification, local replan, and repair loops.
- The mechanism must be evolvable through memory, evidence, and versioned schemas.

## Target System

The target system should look like this:

\`\`\`text
Human Goal
  ↓
Goal Interpreter
  ↓
Plan IR
  ↓
Capability Compiler
  ↓
fsq-mac CLI
  ↓
Evidence Collector
  ↓
Evaluator / Repair Loop
  ↓
Human Review
\`\`\`

### Asset Boundaries

- \`Goal\`
  Human asset. Expresses intent, constraints, acceptance, and review points.
- \`Plan IR\`
  Human-agent shared asset. Expresses structured intent for execution.
- \`Execution\`
  Agent asset. Compiles to and invokes \`fsq-mac CLI\`.
- \`Evidence\`
  Shared review asset. Records what happened and why.
- \`Memory\`
  Agent support asset. Stores run-time state, reusable cases, and stable rules.

## Phase Plan

### Phase 0: Reset the POC Baseline
Reframe the existing demo into an honest, executable foundation.

### Phase 1: Define the Core Schemas
Make the system machine-operable before making it feature-rich.

### Phase 2: Build a Capability Registry
Prevent the agent from inventing arbitrary actions.

### Phase 3: Build the Compiler and Unified Executor
Make \`fsq-mac CLI\` the only bottom execution layer.

### Phase 4: Build the Evidence Layer
Make every run inspectable, replayable, and reviewable.

### Phase 5: Build the Evaluator and Failure Classifier
Turn raw evidence into decisions.

### Phase 6: Build the Repair and Replan Loop
Make failure a first-class part of the execution model.

### Phase 7: Add Memory and Evolution Loops
Let the system improve without turning the plan format into an uncontrolled language.

### Phase 8: Prove the End-to-End Loop on One Real Scenario
Validate the architecture on a narrow but real path.

### Phase 9: Expand to a Credible POC
Move from one scenario to a believable system demonstration.

## Delivery Structure

\`\`\`text
README.md
docs/
  plans/
goals/
plans/
runs/
memory/
registry/
src/
  goal_interpreter/
  planner/
  compiler/
  executor/
  evaluator/
  repair/
  schemas/
tests/
  unit/
  integration/
  examples/
\`\`\`

## Definition of Done for the First Credible Milestone

The first milestone is done only when all of the following are true:

- One real goal is captured in a structured form.
- The agent produces a valid \`Plan IR\`.
- The plan validates against a versioned schema.
- The plan compiles into \`fsq-mac CLI\` commands.
- The executor runs those commands and records structured results.
- Evidence is saved under a run directory.
- The evaluator compares evidence against expected signals.
- One failure path is classified and handled by retry, repair, or local replan.
- A human can review the final artifacts without reading raw source code.
