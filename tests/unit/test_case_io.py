"""Unit tests for case YAML IO and action registry."""

from pathlib import Path

from src.actions.action_space import ACTION_SPACE
from src.case.loader import load_case
from src.case.schema import CaseFile, CaseMeta, Postcondition, Step
from src.case.writer import save_case


def test_case_yaml_round_trip(tmp_path: Path):
    """Case YAML should round-trip through dataclasses without losing fields."""

    case = CaseFile(
        meta=CaseMeta(
            goal="登录 GitHub",
            app="Safari",
            created="2026-04-19T14:30:00Z",
            tags=["auth", "smoke"],
            variables=["USERNAME", "PASSWORD"],
        ),
        steps=[
            Step(action="launch", target="com.apple.Safari"),
            Step(action="input", target="Username or email", value="${USERNAME}"),
            Step(action="tap", target="Sign in", result="success", timestamp="2026-04-19T14:31:00Z"),
        ],
        postconditions=[
            Postcondition(assert_type="contains", target="window.title", value="GitHub"),
        ],
    )

    path = tmp_path / "cases" / "github-login.yaml"
    save_case(case, path)
    loaded = load_case(path)

    assert loaded == case


def test_action_space_matches_expected_contract():
    """Action space should expose the six baseline semantic actions."""

    assert [action.name for action in ACTION_SPACE] == [
        "launch",
        "tap",
        "input",
        "hotkey",
        "assert",
        "wait",
    ]
    assert ACTION_SPACE[0].fsq_cmd == "mac app launch {target}"
    assert ACTION_SPACE[3].params == {"keys": "key_combo"}
