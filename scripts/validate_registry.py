#!/usr/bin/env python3
"""
Validate registry/actions.yaml against fsq-mac agent-contract.json.

Usage:
    python3 scripts/validate_registry.py [--contract PATH]

Compares the GDA action registry with the upstream fsq-mac contract to detect:
  - Missing actions (in contract but not in registry)
  - Outdated actions (in registry but not in contract)
  - Coverage percentage
"""
import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class ValidationResult:
    contract_version: str
    contract_actions_count: int
    registry_actions_count: int
    covered: set[str]
    missing: set[str]
    extra: set[str]

    @property
    def exit_code(self) -> int:
        return 1 if self.missing else 0


def load_registry(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f) or {}


def load_registry_actions(path: Path) -> dict:
    return load_registry(path).get("actions", {})


def load_contract(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def extract_contract_actions(contract: dict) -> set:
    """Extract all domain.action pairs from the contract."""
    actions = set()
    for domain in contract.get("domains", []):
        domain_name = domain["name"]
        for action in domain.get("actions", []):
            actions.add(f"{domain_name}.{action}")
    return actions


def extract_registry_actions(registry: dict) -> dict:
    """Map registry action names to their compile_to targets as domain.action pairs."""
    mapping = {}
    for action_name, action_def in registry.items():
        compile_to = action_def.get("compile_to", "")
        # Parse domain.action from compile_to: "mac <domain> <action> ..."
        # or from special markers like __element_argv__
        if compile_to.startswith("mac "):
            parts = compile_to.split()
            if len(parts) >= 3:
                mapping[action_name] = f"{parts[1]}.{parts[2]}"
        elif compile_to == "__element_argv__":
            # Extract verb from the action name
            verb = action_name.replace("element_", "")
            verb = verb.replace("_", "-")
            mapping[action_name] = f"element.{verb}"
        elif compile_to == "__assert_argv__":
            verb = action_name.replace("assert_", "")
            mapping[action_name] = f"assert.{verb}"
        elif compile_to.startswith("sleep"):
            mapping[action_name] = "__builtin__.sleep"
        else:
            mapping[action_name] = f"__unknown__.{action_name}"
    return mapping


def resolve_contract_path(explicit_path: Path | None) -> Path:
    if explicit_path is not None:
        return explicit_path

    env_path = os.environ.get("FSQ_MAC_CONTRACT_PATH")
    if env_path:
        return Path(env_path)

    return ROOT.parent / "fsq-mac" / "docs" / "agent-contract.json"


def validate_registry_against_contract(contract_path: Path, registry_path: Path) -> ValidationResult:
    contract = load_contract(contract_path)
    registry_doc = load_registry(registry_path)
    registry = registry_doc.get("actions", {})

    contract_actions = extract_contract_actions(contract)
    registry_map = extract_registry_actions(registry)
    registry_targets = set(registry_map.values())
    supported_contract_actions = set(registry_doc.get("supported_contract_actions", []))

    registry_cli_targets = {t for t in registry_targets if not t.startswith("__")}

    if supported_contract_actions:
        target_contract_actions = contract_actions & supported_contract_actions
    else:
        target_contract_actions = contract_actions

    covered = target_contract_actions & registry_cli_targets
    missing = target_contract_actions - registry_cli_targets
    extra = registry_cli_targets - contract_actions

    return ValidationResult(
        contract_version=contract.get("version", "unknown"),
        contract_actions_count=len(target_contract_actions),
        registry_actions_count=len(registry),
        covered=covered,
        missing=missing,
        extra=extra,
    )


def render_validation_report(result: ValidationResult) -> str:
    coverage_pct = 0 if result.contract_actions_count == 0 else 100 * len(result.covered) / result.contract_actions_count
    lines = [
        f"Contract version: {result.contract_version}",
        f"Contract actions: {result.contract_actions_count}",
        f"Registry actions: {result.registry_actions_count}",
        f"Covered:          {len(result.covered)}/{result.contract_actions_count} ({coverage_pct:.0f}%)",
        "",
    ]

    if result.missing:
        lines.append(f"Missing from registry ({len(result.missing)}):")
        for action in sorted(result.missing):
            lines.append(f"  - {action}")
        lines.append("")

    if result.extra:
        lines.append(f"Extra in registry (not in contract) ({len(result.extra)}):")
        for action in sorted(result.extra):
            lines.append(f"  - {action}")
        lines.append("")

    if not result.missing:
        lines.append("Registry fully covers the contract.")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Validate registry against fsq-mac contract")
    parser.add_argument(
        "--contract",
        type=Path,
        default=None,
        help="Path to agent-contract.json (default: ../fsq-mac/docs/agent-contract.json)",
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=ROOT / "registry" / "actions.yaml",
        help="Path to actions.yaml",
    )
    args = parser.parse_args()

    args.contract = resolve_contract_path(args.contract)

    if not args.contract.exists():
        print(f"Contract not found: {args.contract}")
        print("Hint: pass --contract /path/to/agent-contract.json")
        sys.exit(1)
    if not args.registry.exists():
        print(f"Registry not found: {args.registry}")
        sys.exit(1)

    result = validate_registry_against_contract(args.contract, args.registry)
    print(render_validation_report(result))
    sys.exit(result.exit_code)


if __name__ == "__main__":
    main()
