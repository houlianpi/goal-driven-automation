#!/usr/bin/env python3
"""Canonical report generator entrypoint."""
import argparse
import importlib.util
from pathlib import Path
from types import ModuleType


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_IMPL = SCRIPT_DIR / "generate_html_report.py"
LEGACY_IMPLS = {
    "v1": SCRIPT_DIR / "generate_html_report.py",
    "v2": SCRIPT_DIR / "generate_html_report.py",
    "v3": SCRIPT_DIR / "generate_html_report.py",
}


def _load_module(path: Path, module_name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load report implementation: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate an HTML report from Goal-Driven Automation artifacts."
    )
    parser.add_argument(
        "input_dir",
        nargs="?",
        help="Input directory. Defaults depend on the selected implementation.",
    )
    parser.add_argument(
        "output_path",
        nargs="?",
        help="Output report path. Defaults depend on the selected implementation.",
    )
    parser.add_argument(
        "--impl",
        choices=sorted(LEGACY_IMPLS.keys()),
        default="v3",
        help="Implementation backend. `v3` is the supported default.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    impl_path = LEGACY_IMPLS.get(args.impl, DEFAULT_IMPL)
    if args.impl != "v3":
        print(f"Deprecated report implementation selected: {args.impl}. Prefer scripts/generate_report.py with the default backend.")

    module = _load_module(impl_path, f"report_impl_{args.impl}")

    if args.input_dir is None and args.output_path is None:
        return int(module.main())

    if not hasattr(module, "generate_report") and not hasattr(module, "generate_html"):
        raise RuntimeError(f"Unsupported report implementation API: {impl_path}")

    input_dir = Path(args.input_dir) if args.input_dir else Path("data/e2e_results")
    output_path = Path(args.output_path) if args.output_path else input_dir / "report.html"

    if hasattr(module, "generate_report"):
        module.generate_report(input_dir, output_path)
    else:
        scenarios = module.load_scenarios(input_dir)
        module.generate_html(scenarios, input_dir, output_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
