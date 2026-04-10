"""Integration tests for batch-oriented CLI commands."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src import cli


def test_cmd_run_case_executes_case_goal(tmp_path: Path, capsys):
    """Test run-case loads a case asset and executes its goal once."""
    case_path = tmp_path / "case-open-edge.json"
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

    args = SimpleNamespace(case_file=str(case_path), dry_run=True, json=False)

    with patch("src.cli.Pipeline") as pipeline_cls:
        pipeline = pipeline_cls.return_value
        pipeline.run.return_value = SimpleNamespace(
            run_id="run-case-1",
            final_status="dry_run_complete",
            success=True,
            stages=[],
            goal=None,
            plan=None,
            evaluation=None,
            artifacts_dir=None,
            to_dict=lambda: {"run_id": "run-case-1"},
        )

        exit_code = cli.cmd_run_case(args)

    assert exit_code == 0
    pipeline.run.assert_called_once_with("Open Edge", dry_run=True)
    assert "case-open-edge" in capsys.readouterr().out


def test_cmd_run_suite_executes_each_case_goal(tmp_path: Path, capsys):
    """Test run-suite expands suite membership and runs each case goal."""
    data_dir = tmp_path / "data"
    cases_dir = data_dir / "cases"
    suites_dir = data_dir / "suites"
    cases_dir.mkdir(parents=True)
    suites_dir.mkdir(parents=True)

    (cases_dir / "case-open-edge.json").write_text(
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
    (cases_dir / "case-open-safari.json").write_text(
        json.dumps(
            {
                "id": "case-open-safari",
                "title": "Open Safari",
                "goal": "Open Safari",
                "tags": ["smoke", "safari"],
                "apps": ["Safari"],
            }
        )
    )
    suite_path = suites_dir / "suite-smoke-core.json"
    suite_path.write_text(
        json.dumps(
            {
                "id": "suite-smoke-core",
                "title": "Core smoke",
                "cases": ["case-open-edge", "case-open-safari"],
            }
        )
    )

    args = SimpleNamespace(suite_file=str(suite_path), dry_run=True, json=False)

    with patch("src.cli.Pipeline") as pipeline_cls:
        pipeline = pipeline_cls.return_value
        pipeline.run.side_effect = [
            SimpleNamespace(
                run_id="run-1",
                final_status="dry_run_complete",
                success=True,
                stages=[],
                goal=None,
                plan=None,
                evaluation=None,
                artifacts_dir=None,
                to_dict=lambda: {"run_id": "run-1"},
            ),
            SimpleNamespace(
                run_id="run-2",
                final_status="dry_run_complete",
                success=True,
                stages=[],
                goal=None,
                plan=None,
                evaluation=None,
                artifacts_dir=None,
                to_dict=lambda: {"run_id": "run-2"},
            ),
        ]

        exit_code = cli.cmd_run_suite(args)

    assert exit_code == 0
    assert pipeline.run.call_count == 2
    pipeline.run.assert_any_call("Open Edge", dry_run=True)
    pipeline.run.assert_any_call("Open Safari", dry_run=True)
    output = capsys.readouterr().out
    assert "suite-smoke-core" in output
    assert "2/2" in output
