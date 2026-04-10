"""Unit tests for case and suite asset loading."""

import json
from pathlib import Path

from src.assets.loader import load_case, load_suite, resolve_suite_cases


def test_suite_resolves_to_case_documents(tmp_path: Path):
    """Test explicit suite membership resolves to concrete case documents."""
    cases_dir = tmp_path / "data" / "cases"
    suites_dir = tmp_path / "data" / "suites"
    cases_dir.mkdir(parents=True)
    suites_dir.mkdir(parents=True)

    case_path = cases_dir / "case-open-edge.json"
    suite_path = suites_dir / "suite-smoke-core.json"

    case_path.write_text(
        json.dumps(
            {
                "id": "case-open-edge",
                "title": "Open Edge",
                "goal": "Open Edge",
                "tags": ["smoke", "edge"],
                "apps": ["Microsoft Edge"],
            }
        )
    )
    suite_path.write_text(
        json.dumps(
            {
                "id": "suite-smoke-core",
                "title": "Core smoke",
                "cases": ["case-open-edge"],
            }
        )
    )

    suite = load_suite(suite_path)
    case = load_case(case_path)
    resolved = resolve_suite_cases(tmp_path, suite)

    assert case["id"] == "case-open-edge"
    assert [item["id"] for item in resolved] == ["case-open-edge"]
