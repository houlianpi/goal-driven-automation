"""CLI package exports and compatibility helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.assets.loader import load_case, load_suite, resolve_suite_cases
from src.pipeline.pipeline import Pipeline


def _resolve_asset_base_dir(asset_path: Path) -> Path:
    """Resolve repository base dir from a case or suite asset path."""
    if asset_path.parent.name in {"cases", "suites"}:
        return asset_path.parent.parent.parent
    return Path(".")


def cmd_run_case(args: Any) -> int:
    """Run a legacy JSON case asset through the pipeline."""
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


def cmd_run_suite(args: Any) -> int:
    """Run all legacy JSON case assets referenced by a suite."""
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
        print(
            json.dumps(
                {
                    "suite_id": suite["id"],
                    "total_cases": len(cases),
                    "successful_cases": success_count,
                    "results": [result.to_dict() for result in results],
                },
                indent=2,
            )
        )
    return 0 if success_count == len(cases) else 1


__all__ = ["Pipeline", "cmd_run_case", "cmd_run_suite"]
