#!/usr/bin/env python3
"""
Goal-Driven Automation CLI

Usage:
    python -m src.cli run "Open Edge and create new tab"
    python -m src.cli run "Open Edge" --dry-run
    python -m src.cli validate <plan.json>
"""
import argparse
import json
import sys
from pathlib import Path

from src.assets.loader import load_case, load_suite, resolve_suite_cases
from src.pipeline.pipeline import Pipeline


def cmd_run(args):
    """Run the automation pipeline."""
    pipeline = Pipeline(base_dir=Path("."))
    
    print(f"Goal: {args.goal}")
    print(f"Dry run: {args.dry_run}")
    print("-" * 50)
    
    result = pipeline.run(args.goal, dry_run=args.dry_run)
    
    print(f"\n{'='*50}")
    print(f"Run ID: {result.run_id}")
    print(f"Status: {result.final_status}")
    print(f"Success: {result.success}")
    
    print(f"\nStages:")
    for stage in result.stages:
        status = "✓" if stage.success else "✗"
        print(f"  {status} {stage.stage.value} ({stage.duration_ms}ms)")
        if stage.error:
            print(f"      Error: {stage.error}")
    
    if result.goal:
        print(f"\nParsed Goal:")
        print(f"  Type: {result.goal.goal_type.value}")
        print(f"  App: {result.goal.target_app}")
        print(f"  Actions: {result.goal.actions}")
    
    if result.plan:
        print(f"\nPlan: {result.plan.get('plan_id')}")
        print(f"  Steps: {len(result.plan.get('steps', []))}")
    
    if result.evaluation:
        print(f"\nEvaluation:")
        print(f"  Verdict: {result.evaluation.verdict.value}")
        print(f"  Passed: {result.evaluation.passed_steps}/{result.evaluation.total_steps}")
    
    if result.artifacts_dir:
        print(f"\nArtifacts: {result.artifacts_dir}/")
    
    if args.json:
        print(f"\n{'='*50}")
        print("JSON Output:")
        print(json.dumps(result.to_dict(), indent=2))
    
    return 0 if result.success else 1


def cmd_validate(args):
    """Validate a plan file."""
    from src.schema.validator import SchemaValidator
    
    validator = SchemaValidator()
    
    with open(args.plan_file) as f:
        plan = json.load(f)
    
    is_valid, errors = validator.validate_plan(plan)
    
    if is_valid:
        print(f"✓ Plan is valid")
        return 0
    else:
        print(f"✗ Plan validation failed:")
        for error in errors:
            print(f"  - {error}")
        return 1


def _build_pipeline_for_asset(asset_path: Path) -> Pipeline:
    """Build pipeline rooted at the repository base for the given asset path."""
    if asset_path.parent.name == "cases":
        base_dir = asset_path.parent.parent.parent
    elif asset_path.parent.name == "suites":
        base_dir = asset_path.parent.parent.parent
    else:
        base_dir = Path(".")
    return Pipeline(base_dir=base_dir)


def _resolve_asset_base_dir(asset_path: Path) -> Path:
    """Resolve repository base dir from a case or suite asset path."""
    if asset_path.parent.name in {"cases", "suites"}:
        return asset_path.parent.parent.parent
    return Path(".")


def cmd_run_case(args):
    """Run a user-facing case asset."""
    case_path = Path(args.case_file)
    case = load_case(case_path)
    pipeline = Pipeline(base_dir=_resolve_asset_base_dir(case_path))

    print(f"Case: {case['id']}")
    print(f"Goal: {case['goal']}")

    result = pipeline.run(case["goal"], dry_run=args.dry_run)

    print(f"Run ID: {result.run_id}")
    print(f"Status: {result.final_status}")
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.success else 1


def cmd_run_suite(args):
    """Run all case assets referenced by a suite."""
    suite_path = Path(args.suite_file)
    suite = load_suite(suite_path)
    base_dir = _resolve_asset_base_dir(suite_path)
    pipeline = Pipeline(base_dir=base_dir)
    cases = resolve_suite_cases(base_dir, suite)

    print(f"Suite: {suite['id']}")
    success_count = 0
    results = []

    for case in cases:
        result = pipeline.run(case["goal"], dry_run=args.dry_run)
        results.append(result)
        if result.success:
            success_count += 1
        print(f"- {case['id']}: {result.final_status}")

    print(f"Summary: {success_count}/{len(cases)} succeeded")
    if args.json:
        print(json.dumps({
            "suite_id": suite["id"],
            "total_cases": len(cases),
            "successful_cases": success_count,
            "results": [result.to_dict() for result in results],
        }, indent=2))
    return 0 if success_count == len(cases) else 1


def main():
    parser = argparse.ArgumentParser(description="Goal-Driven Automation CLI")
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # run command
    run_parser = subparsers.add_parser("run", help="Run automation from goal")
    run_parser.add_argument("goal", help="Natural language goal")
    run_parser.add_argument("--dry-run", action="store_true", help="Don't execute, just plan")
    run_parser.add_argument("--json", action="store_true", help="Output JSON")
    run_parser.set_defaults(func=cmd_run)

    run_case_parser = subparsers.add_parser("run-case", help="Run automation from a case asset")
    run_case_parser.add_argument("case_file", help="Path to case JSON file")
    run_case_parser.add_argument("--dry-run", action="store_true", help="Don't execute, just plan")
    run_case_parser.add_argument("--json", action="store_true", help="Output JSON")
    run_case_parser.set_defaults(func=cmd_run_case)

    run_suite_parser = subparsers.add_parser("run-suite", help="Run automation from a suite asset")
    run_suite_parser.add_argument("suite_file", help="Path to suite JSON file")
    run_suite_parser.add_argument("--dry-run", action="store_true", help="Don't execute, just plan")
    run_suite_parser.add_argument("--json", action="store_true", help="Output JSON")
    run_suite_parser.set_defaults(func=cmd_run_suite)
    
    # validate command
    validate_parser = subparsers.add_parser("validate", help="Validate a plan file")
    validate_parser.add_argument("plan_file", help="Path to plan JSON file")
    validate_parser.set_defaults(func=cmd_validate)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
