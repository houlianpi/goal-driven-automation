"""Primary CLI entry point for goal-driven automation."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Sequence

from src.cache import CaseCache
from src.case import CaseFile
from src.cli.fix import FixLLMClient, fix_case
from src.cli.record import record_goal
from src.cli.run import run_loaded_case, run_path, run_results_for_path
from src.engine.planner import LLMClient, PlanningLoop
from src.report import ReportGenerator


def main(argv: Sequence[str] | None = None) -> int:
    """Run the `gda` CLI."""
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.goal == "run":
        if args.arg is None:
            parser.error("run requires a case path")
        if args.report == "html" and args.output is None:
            parser.error("run with --report html requires --output")
        args.command = "run"
        args.case_path = Path(args.arg)
        return cmd_run(args)
    if args.goal == "record":
        if args.arg is None:
            parser.error("record requires a goal")
        if args.output is None:
            parser.error("record requires -o/--output")
        args.command = "record"
        args.goal = args.arg
        return cmd_record(args)
    if args.goal == "fix":
        if args.arg is None:
            parser.error("fix requires a case path")
        args.command = "fix"
        args.case_path = Path(args.arg)
        return cmd_fix(args)
    if args.goal:
        args.command = None
        return cmd_goal(args)

    parser.print_help()
    return 1


def build_parser() -> argparse.ArgumentParser:
    """Create the top-level argparse parser."""
    parser = argparse.ArgumentParser(prog="gda", description="Goal-driven automation CLI")
    parser.set_defaults(command=None)
    parser.add_argument("--app", default="Safari", help="Target application name")
    parser.add_argument("--max-cycles", type=int, default=10, help="Maximum planning cycles")

    parser.add_argument("goal", nargs="?", help="Immediate goal or subcommand")
    parser.add_argument("arg", nargs="?", help="Subcommand argument")
    parser.add_argument("-o", "--output", type=Path, help="Output YAML path for record mode")
    parser.add_argument("--report", choices=["html"], help="Generate a run report")
    return parser


def cmd_goal(args: argparse.Namespace, llm_client: LLMClient | None = None) -> int:
    """Execute a goal immediately, with cache-assisted replay on repeat runs."""
    cache = CaseCache()
    cached_case = cache.get(args.goal, args.app)
    if cached_case is not None:
        return 0 if run_loaded_case(cached_case) else 1

    case = _plan_case(args.goal, args.app, args.max_cycles, llm_client=llm_client)
    cache.put(args.goal, args.app, case)
    return 0 if run_loaded_case(case) else 1


def cmd_record(args: argparse.Namespace, llm_client: LLMClient | None = None) -> int:
    """Record a goal into a YAML case file."""
    record_goal(
        goal=args.goal,
        app=args.app,
        output_path=args.output,
        max_cycles=args.max_cycles,
        llm_client=llm_client or _default_llm_client(),
    )
    return 0


def cmd_fix(args: argparse.Namespace, llm_client: FixLLMClient | None = None) -> int:
    """Attempt to repair a failed case file in place."""
    success = fix_case(args.case_path, llm_client or _default_fix_llm_client())
    return 0 if success else 1


def cmd_run(args: argparse.Namespace) -> int:
    """Replay an existing case file or a directory of case files."""
    if args.report == "html":
        results = run_results_for_path(args.case_path)
        ReportGenerator().generate_report(results, args.output)
        return 0 if all(result.success for result in results) else 1
    return 0 if run_path(args.case_path) else 1


def _plan_case(goal: str, app: str, max_cycles: int, *, llm_client: LLMClient | None) -> CaseFile:
    planner = PlanningLoop(
        goal=goal,
        app=app,
        max_cycles=max_cycles,
        llm_client=llm_client or _default_llm_client(),
    )
    return planner.run()


def _default_llm_client() -> LLMClient:
    """Return a placeholder planner client until the production LLM is wired in."""
    xml_response = os.environ.get("GDA_DEFAULT_XML_RESPONSE")
    if not xml_response:
        raise ValueError(
            "No planner client configured. Pass an llm_client in code or set GDA_DEFAULT_XML_RESPONSE."
        )
    return lambda prompt: xml_response


def _default_fix_llm_client() -> FixLLMClient:
    """Return a placeholder repair client until the production LLM is wired in."""
    yaml_response = os.environ.get("GDA_DEFAULT_FIX_RESPONSE")
    if not yaml_response:
        raise ValueError(
            "No fix client configured. Pass an llm_client in code or set GDA_DEFAULT_FIX_RESPONSE."
        )
    return lambda prompt: yaml_response


if __name__ == "__main__":
    sys.exit(main())
