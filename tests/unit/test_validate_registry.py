"""Unit tests for scripts.validate_registry."""
import json
from pathlib import Path

import pytest

from scripts import validate_registry


def write_contract(path: Path, domains: list[dict], version: str = "0.3.1"):
    path.write_text(json.dumps({"version": version, "domains": domains}))


def write_registry(path: Path, actions: dict):
    import yaml

    path.write_text(yaml.safe_dump({"actions": actions}))


def write_registry_with_supported_contract(path: Path, actions: dict, supported_contract_actions: list[str]):
    import yaml

    path.write_text(
        yaml.safe_dump(
            {
                "supported_contract_actions": supported_contract_actions,
                "actions": actions,
            }
        )
    )


class TestValidateRegistry:
    def test_validate_fails_when_contract_action_missing(self, tmp_path):
        contract = tmp_path / "agent-contract.json"
        registry = tmp_path / "actions.yaml"
        write_contract(contract, [{"name": "menu", "actions": ["click"]}])
        write_registry(registry, {})

        result = validate_registry.validate_registry_against_contract(contract, registry)

        assert result.exit_code == 1
        assert result.missing == {"menu.click"}

    def test_validate_passes_when_registry_covers_contract(self, tmp_path):
        contract = tmp_path / "agent-contract.json"
        registry = tmp_path / "actions.yaml"
        write_contract(contract, [{"name": "menu", "actions": ["click"]}])
        write_registry(
            registry,
            {"menu_click": {"compile_to": "mac menu click {menu_path}"}},
        )

        result = validate_registry.validate_registry_against_contract(contract, registry)

        assert result.exit_code == 0
        assert result.missing == set()
        assert result.covered == {"menu.click"}

    def test_builtins_are_excluded_from_contract_comparison(self, tmp_path):
        contract = tmp_path / "agent-contract.json"
        registry = tmp_path / "actions.yaml"
        write_contract(contract, [{"name": "menu", "actions": ["click"]}])
        write_registry(
            registry,
            {
                "menu_click": {"compile_to": "mac menu click {menu_path}"},
                "wait": {"compile_to": "sleep {seconds}"},
            },
        )

        result = validate_registry.validate_registry_against_contract(contract, registry)

        assert result.exit_code == 0
        assert "__builtin__.sleep" not in result.extra

    def test_unknown_registry_action_is_reported_as_extra(self, tmp_path):
        contract = tmp_path / "agent-contract.json"
        registry = tmp_path / "actions.yaml"
        write_contract(contract, [{"name": "menu", "actions": ["click"]}])
        write_registry(
            registry,
            {
                "menu_click": {"compile_to": "mac menu click {menu_path}"},
                "custom_raw": {"compile_to": "mac custom raw"},
            },
        )

        result = validate_registry.validate_registry_against_contract(contract, registry)

        assert result.extra == {"custom.raw"}

    def test_resolve_contract_path_prefers_environment_variable(self, tmp_path, monkeypatch):
        env_contract = tmp_path / "env-contract.json"
        write_contract(env_contract, [{"name": "menu", "actions": ["click"]}])
        monkeypatch.setenv("FSQ_MAC_CONTRACT_PATH", str(env_contract))

        resolved = validate_registry.resolve_contract_path(None)

        assert resolved == env_contract

    def test_supported_contract_subset_limits_missing_detection(self, tmp_path):
        contract = tmp_path / "agent-contract.json"
        registry = tmp_path / "actions.yaml"
        write_contract(
            contract,
            [
                {"name": "menu", "actions": ["click"]},
                {"name": "trace", "actions": ["start"]},
            ],
        )
        write_registry_with_supported_contract(
            registry,
            {"menu_click": {"compile_to": "mac menu click {menu_path}"}},
            supported_contract_actions=["menu.click"],
        )

        result = validate_registry.validate_registry_against_contract(contract, registry)

        assert result.exit_code == 0
        assert result.missing == set()
        assert result.covered == {"menu.click"}

    def test_supported_contract_subset_fails_when_declared_action_missing(self, tmp_path):
        contract = tmp_path / "agent-contract.json"
        registry = tmp_path / "actions.yaml"
        write_contract(
            contract,
            [
                {"name": "menu", "actions": ["click"]},
                {"name": "trace", "actions": ["start"]},
            ],
        )
        write_registry_with_supported_contract(
            registry,
            {"menu_click": {"compile_to": "mac menu click {menu_path}"}},
            supported_contract_actions=["menu.click", "trace.start"],
        )

        result = validate_registry.validate_registry_against_contract(contract, registry)

        assert result.exit_code == 1
        assert result.missing == {"trace.start"}

    def test_render_validation_report_handles_zero_contract_actions(self):
        result = validate_registry.ValidationResult(
            contract_version="0.3.1",
            contract_actions_count=0,
            registry_actions_count=1,
            covered=set(),
            missing=set(),
            extra=set(),
        )

        report = validate_registry.render_validation_report(result)

        assert "Covered:          0/0 (0%)" in report
