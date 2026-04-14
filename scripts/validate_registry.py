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
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def load_registry(path: Path) -> dict:
    with open(path) as f:
        data = yaml.safe_load(f)
    return data.get("actions", {})


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

    if args.contract is None:
        args.contract = ROOT.parent / "fsq-mac" / "docs" / "agent-contract.json"

    if not args.contract.exists():
        print(f"Contract not found: {args.contract}")
        print("Hint: pass --contract /path/to/agent-contract.json")
        sys.exit(1)
    if not args.registry.exists():
        print(f"Registry not found: {args.registry}")
        sys.exit(1)

    contract = load_contract(args.contract)
    registry = load_registry(args.registry)

    contract_actions = extract_contract_actions(contract)
    registry_map = extract_registry_actions(registry)
    registry_targets = set(registry_map.values())

    # Ignore builtins like sleep
    registry_cli_targets = {t for t in registry_targets if not t.startswith("__")}

    covered = contract_actions & registry_cli_targets
    missing = contract_actions - registry_cli_targets
    extra = registry_cli_targets - contract_actions

    print(f"Contract version: {contract.get('version', 'unknown')}")
    print(f"Contract actions: {len(contract_actions)}")
    print(f"Registry actions: {len(registry)}")
    print(f"Covered:          {len(covered)}/{len(contract_actions)} ({100*len(covered)/len(contract_actions):.0f}%)")
    print()

    if missing:
        print(f"Missing from registry ({len(missing)}):")
        for action in sorted(missing):
            print(f"  - {action}")
        print()

    if extra:
        print(f"Extra in registry (not in contract) ({len(extra)}):")
        for action in sorted(extra):
            print(f"  - {action}")
        print()

    if not missing:
        print("Registry fully covers the contract.")

    sys.exit(1 if missing else 0)


if __name__ == "__main__":
    main()
