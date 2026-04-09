#!/usr/bin/env python3
"""
E2E Demo - Demonstrates full pipeline with failure and repair.
"""
import json
from pathlib import Path

from src.pipeline.goal_parser import GoalParser
from src.pipeline.plan_generator import PlanGenerator
from src.compiler.compiler import Compiler
from src.executor.mock_executor import MockExecutor
from src.evaluator.evaluator import Evaluator
from src.repair.repair_loop import RepairLoop
from src.memory.evolution import EvolutionEngine


def run_demo(goal_text: str, force_failure_step: str = None):
    """Run complete E2E demo."""
    print(f"\n{'='*60}")
    print(f"GOAL: {goal_text}")
    print('='*60)
    
    # Stage 1: Parse Goal
    print("\n[1/7] Parsing Goal...")
    parser = GoalParser()
    goal = parser.parse(goal_text)
    print(f"  Type: {goal.goal_type.value}")
    print(f"  App: {goal.target_app}")
    print(f"  Actions: {goal.actions}")
    
    # Stage 2: Generate Plan
    print("\n[2/7] Generating Plan...")
    generator = PlanGenerator()
    plan = generator.generate(goal)
    print(f"  Plan ID: {plan['plan_id']}")
    print(f"  Steps: {len(plan['steps'])}")
    for step in plan['steps']:
        print(f"    - {step['step_id']}: {step['action']}")
    
    # Stage 3: Compile
    print("\n[3/7] Compiling Plan...")
    compiler = Compiler()
    compiled = compiler.compile_plan(plan)
    print(f"  Compiled {len(compiled['steps'])} steps")
    for step in compiled['steps']:
        print(f"    - {step.get('command', 'N/A')}")
    
    # Stage 4: Execute (Mock)
    print("\n[4/7] Executing Plan (Mock)...")
    executor = MockExecutor(failure_rate=0.0)  # No random failures
    if force_failure_step:
        print(f"  [!] Forcing failure on step: {force_failure_step}")
        executor.force_failure(force_failure_step, "timeout")
    
    evidence = executor.execute(plan)
    print(f"  Run ID: {evidence.run_id}")
    print(f"  Status: {evidence.status.value}")
    for step in evidence.steps:
        status_icon = "✓" if step.status.value == "success" else "✗"
        print(f"    {status_icon} {step.step_id}: {step.action} ({step.status.value})")
        if step.error:
            print(f"      Error: {step.error.message}")
    
    # Stage 5: Evaluate
    print("\n[5/7] Evaluating Results...")
    evaluator = Evaluator()
    evaluation = evaluator.evaluate(evidence)
    print(f"  Verdict: {evaluation.verdict.value}")
    print(f"  Passed: {evaluation.passed_steps}/{evaluation.total_steps}")
    print(f"  Next Action: {evaluation.next_action.value}")
    
    # Stage 6: Repair (if needed)
    if evaluation.failed_steps > 0:
        print("\n[6/7] Attempting Repair...")
        repair_loop = RepairLoop()
        repair_result = repair_loop.run(evidence)
        print(f"  Outcome: {repair_result.outcome.value}")
        print(f"  Attempts: {len(repair_result.repair_attempts)}")
        for attempt in repair_result.repair_attempts:
            status = "✓" if attempt.success else "✗"
            print(f"    {status} {attempt.step_id}: {attempt.strategy} - {attempt.details[:50]}")
        
        if repair_result.repaired_evidence:
            evidence = repair_result.repaired_evidence
    else:
        print("\n[6/7] No repair needed")
    
    # Stage 7: Finalize
    print("\n[7/7] Finalizing...")
    evolution = EvolutionEngine(Path("."))
    events = evolution.process_run_completion(evidence)
    print(f"  Evidence saved to: runs/{evidence.run_id}/")
    print(f"  Evolution events: {len(events)}")
    
    # Summary
    final_status = "SUCCESS" if evidence.status.value == "success" else evidence.status.value.upper()
    print(f"\n{'='*60}")
    print(f"FINAL STATUS: {final_status}")
    print('='*60)
    
    return evidence


def main():
    print("\n" + "="*60)
    print("GOAL-DRIVEN AUTOMATION - E2E DEMO")
    print("="*60)
    
    # Demo 1: Success scenario
    print("\n\n>>> DEMO 1: Success Scenario")
    run_demo("Open Edge and create new tab")
    
    # Demo 2: Failure + Repair scenario
    print("\n\n>>> DEMO 2: Failure + Repair Scenario")
    run_demo("Open Safari", force_failure_step="s1")
    
    # Demo 3: Another success
    print("\n\n>>> DEMO 3: Terminal Command")
    run_demo("Open Terminal")
    
    print("\n\n" + "="*60)
    print("DEMO COMPLETE - 3 scenarios executed")
    print("="*60)


if __name__ == "__main__":
    main()
