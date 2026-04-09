"""
Rule Memory - Versioned registry, schema, and policy storage.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path
from enum import Enum
import json
import yaml
import shutil

from src.time_utils import parse_datetime, utc_now


class RuleType(Enum):
    """Types of rules."""
    REGISTRY = "registry"
    SCHEMA = "schema"
    POLICY = "policy"


@dataclass
class RuleVersion:
    """A version of a rule file."""
    version: str
    created_at: datetime
    description: str
    changes: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "description": self.description,
            "changes": self.changes,
        }


@dataclass
class Rule:
    """A versioned rule."""
    rule_id: str
    rule_type: RuleType
    current_version: str
    versions: List[RuleVersion] = field(default_factory=list)
    path: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "rule_type": self.rule_type.value,
            "current_version": self.current_version,
            "versions": [v.to_dict() for v in self.versions],
            "path": self.path,
        }


class RuleMemory:
    """
    Rule Memory - Manages versioned registry, schema, and policy files.
    
    Features:
    - Version control for rule files
    - Rollback capability
    - Change tracking
    """
    
    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or Path(".")
        self.versions_dir = self.base_dir / "data" / "memory" / "rule_versions"
        self.manifest_path = self.base_dir / "data" / "memory" / "rules_manifest.json"
        self._rules: Dict[str, Rule] = {}
        self._load_manifest()
    
    def _load_manifest(self):
        """Load rules manifest."""
        if self.manifest_path.exists():
            with open(self.manifest_path, "r") as f:
                data = json.load(f)
                for rule_data in data.get("rules", []):
                    rule = Rule(
                        rule_id=rule_data["rule_id"],
                        rule_type=RuleType(rule_data["rule_type"]),
                        current_version=rule_data["current_version"],
                        versions=[
                            RuleVersion(
                                version=v["version"],
                                created_at=parse_datetime(v["created_at"]),
                                description=v["description"],
                                changes=v.get("changes", []),
                            )
                            for v in rule_data.get("versions", [])
                        ],
                        path=rule_data.get("path", ""),
                    )
                    self._rules[rule.rule_id] = rule
    
    def _save_manifest(self):
        """Save rules manifest."""
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        data = {"rules": [r.to_dict() for r in self._rules.values()]}
        with open(self.manifest_path, "w") as f:
            json.dump(data, f, indent=2)
    
    def register_rule(self, rule_id: str, rule_type: RuleType, path: str, description: str = "") -> Rule:
        """Register a new rule file for version control."""
        if rule_id in self._rules:
            return self._rules[rule_id]
        
        version = "1.0.0"
        rule = Rule(
            rule_id=rule_id,
            rule_type=rule_type,
            current_version=version,
            path=path,
            versions=[
                RuleVersion(
                    version=version,
                    created_at=utc_now(),
                    description=description or f"Initial version of {rule_id}",
                )
            ],
        )
        
        self._rules[rule_id] = rule
        self._snapshot(rule_id, version)
        self._save_manifest()
        
        return rule
    
    def update_rule(self, rule_id: str, description: str, changes: List[str], bump: str = "patch") -> Optional[str]:
        """Update a rule and create a new version."""
        rule = self._rules.get(rule_id)
        if not rule:
            return None
        
        # Calculate new version
        parts = rule.current_version.split(".")
        major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
        
        if bump == "major":
            major += 1
            minor = 0
            patch = 0
        elif bump == "minor":
            minor += 1
            patch = 0
        else:
            patch += 1
        
        new_version = f"{major}.{minor}.{patch}"
        
        # Create version record
        version = RuleVersion(
            version=new_version,
            created_at=utc_now(),
            description=description,
            changes=changes,
        )
        
        rule.versions.append(version)
        rule.current_version = new_version
        
        # Snapshot current state
        self._snapshot(rule_id, new_version)
        self._save_manifest()
        
        return new_version
    
    def _snapshot(self, rule_id: str, version: str):
        """Create a snapshot of the current rule file."""
        rule = self._rules.get(rule_id)
        if not rule or not rule.path:
            return
        
        source = self.base_dir / rule.path
        if not source.exists():
            return
        
        version_dir = self.versions_dir / rule_id
        version_dir.mkdir(parents=True, exist_ok=True)
        
        dest = version_dir / f"{version}{source.suffix}"
        shutil.copy2(source, dest)
    
    def rollback(self, rule_id: str, version: str) -> bool:
        """Rollback a rule to a previous version."""
        rule = self._rules.get(rule_id)
        if not rule:
            return False
        
        version_path = self.versions_dir / rule_id / f"{version}{Path(rule.path).suffix}"
        if not version_path.exists():
            return False
        
        target = self.base_dir / rule.path
        shutil.copy2(version_path, target)
        rule.current_version = version
        self._save_manifest()
        
        return True
    
    def get_rule(self, rule_id: str) -> Optional[Rule]:
        """Get a rule by ID."""
        return self._rules.get(rule_id)
    
    def get_version_history(self, rule_id: str) -> List[RuleVersion]:
        """Get version history for a rule."""
        rule = self._rules.get(rule_id)
        if rule:
            return rule.versions
        return []
    
    def list_rules(self, rule_type: Optional[RuleType] = None) -> List[Rule]:
        """List all registered rules."""
        rules = list(self._rules.values())
        if rule_type:
            rules = [r for r in rules if r.rule_type == rule_type]
        return rules
    
    def diff_versions(self, rule_id: str, v1: str, v2: str) -> Optional[Dict[str, Any]]:
        """Get diff information between two versions."""
        rule = self._rules.get(rule_id)
        if not rule:
            return None
        
        suffix = Path(rule.path).suffix
        path1 = self.versions_dir / rule_id / f"{v1}{suffix}"
        path2 = self.versions_dir / rule_id / f"{v2}{suffix}"
        
        if not path1.exists() or not path2.exists():
            return None
        
        # Return change summary from version history
        changes = []
        recording = False
        for v in rule.versions:
            if v.version == v1:
                recording = True
                continue
            if recording:
                changes.extend(v.changes)
            if v.version == v2:
                break
        
        return {
            "rule_id": rule_id,
            "from_version": v1,
            "to_version": v2,
            "changes": changes,
        }
