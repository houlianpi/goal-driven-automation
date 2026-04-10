"""Filesystem-backed loading for case and suite assets."""

import json
from pathlib import Path
from typing import Any, Dict, List


def _load_json(path: Path) -> Dict[str, Any]:
    with open(path, "r") as f:
        return json.load(f)


def load_case(path: Path) -> Dict[str, Any]:
    """Load a case asset from disk."""
    return _load_json(Path(path))


def load_suite(path: Path) -> Dict[str, Any]:
    """Load a suite asset from disk."""
    return _load_json(Path(path))


def resolve_suite_cases(base_dir: Path, suite: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Resolve explicit suite case ids to concrete case documents."""
    cases_dir = Path(base_dir) / "data" / "cases"
    resolved = []

    for case_id in suite.get("cases", []):
        candidate = cases_dir / f"{case_id}.json"
        if not candidate.exists():
            raise FileNotFoundError(f"Case asset not found: {candidate}")
        resolved.append(load_case(candidate))

    return resolved
