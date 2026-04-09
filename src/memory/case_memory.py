"""
Case Memory - Reusable patterns and repair cases.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path
from enum import Enum
import json
import hashlib

from src.time_utils import parse_datetime, utc_now


class CaseType(Enum):
    """Types of reusable cases."""
    SUCCESS_PATTERN = "success_pattern"
    REPAIR_CASE = "repair_case"
    FAILURE_PATTERN = "failure_pattern"


@dataclass
class Case:
    """A reusable case extracted from execution."""
    case_id: str
    case_type: CaseType
    pattern: Dict[str, Any]  # Generalized pattern
    success_count: int = 0
    failure_count: int = 0
    last_used: Optional[datetime] = None
    created_at: datetime = field(default_factory=utc_now)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def confidence(self) -> float:
        """Calculate confidence based on success rate."""
        total = self.success_count + self.failure_count
        if total == 0:
            return 0.0
        return self.success_count / total
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "case_type": self.case_type.value,
            "pattern": self.pattern,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "confidence": self.confidence,
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "created_at": self.created_at.isoformat(),
            "tags": self.tags,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Case":
        return cls(
            case_id=data["case_id"],
            case_type=CaseType(data["case_type"]),
            pattern=data["pattern"],
            success_count=data.get("success_count", 0),
            failure_count=data.get("failure_count", 0),
            last_used=parse_datetime(data["last_used"]) if data.get("last_used") else None,
            created_at=parse_datetime(data["created_at"]) if data.get("created_at") else utc_now(),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
        )


class CaseMemory:
    """
    Case Memory - Stores reusable patterns and repair cases.
    
    Features:
    - Pattern matching for similar cases
    - Confidence-based retrieval
    - Automatic promotion from run evidence
    """
    
    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or Path("data/memory/cases.json")
        self._cases: Dict[str, Case] = {}
        self._load()
    
    def _load(self):
        """Load cases from storage."""
        if self.storage_path.exists():
            with open(self.storage_path, "r") as f:
                data = json.load(f)
                for case_data in data.get("cases", []):
                    case = Case.from_dict(case_data)
                    self._cases[case.case_id] = case
    
    def _save(self):
        """Save cases to storage."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {"cases": [c.to_dict() for c in self._cases.values()]}
        with open(self.storage_path, "w") as f:
            json.dump(data, f, indent=2)
    
    def add_case(self, case: Case) -> str:
        """Add a new case."""
        self._cases[case.case_id] = case
        self._save()
        return case.case_id
    
    def get_case(self, case_id: str) -> Optional[Case]:
        """Get a case by ID."""
        return self._cases.get(case_id)
    
    def update_usage(self, case_id: str, success: bool):
        """Update case usage statistics."""
        case = self._cases.get(case_id)
        if case:
            if success:
                case.success_count += 1
            else:
                case.failure_count += 1
            case.last_used = utc_now()
            self._save()
    
    def find_similar(self, pattern: Dict[str, Any], case_type: Optional[CaseType] = None, min_confidence: float = 0.5) -> List[Case]:
        """Find cases similar to a pattern."""
        results = []
        pattern_hash = self._hash_pattern(pattern)
        
        for case in self._cases.values():
            if case_type and case.case_type != case_type:
                continue
            if case.confidence < min_confidence:
                continue
            
            similarity = self._calculate_similarity(pattern, case.pattern)
            if similarity > 0.5:
                results.append(case)
        
        return sorted(results, key=lambda c: c.confidence, reverse=True)
    
    def promote_from_evidence(self, action: str, error_type: str, repair_strategy: str, success: bool) -> Optional[Case]:
        """Promote a successful repair to a reusable case."""
        if not success:
            return None
        
        pattern = {
            "action": action,
            "error_type": error_type,
            "repair_strategy": repair_strategy,
        }
        
        pattern_hash = self._hash_pattern(pattern)
        case_id = f"case-{pattern_hash[:12]}"
        
        existing = self._cases.get(case_id)
        if existing:
            existing.success_count += 1
            existing.last_used = utc_now()
            self._save()
            return existing
        
        case = Case(
            case_id=case_id,
            case_type=CaseType.REPAIR_CASE,
            pattern=pattern,
            success_count=1,
            tags=[action, error_type, repair_strategy],
        )
        self.add_case(case)
        return case
    
    def get_repair_suggestion(self, action: str, error_type: str) -> Optional[str]:
        """Get a repair strategy suggestion based on past cases."""
        cases = self.find_similar(
            {"action": action, "error_type": error_type},
            case_type=CaseType.REPAIR_CASE,
            min_confidence=0.6,
        )
        
        if cases:
            return cases[0].pattern.get("repair_strategy")
        return None
    
    def _hash_pattern(self, pattern: Dict[str, Any]) -> str:
        """Generate a hash for pattern matching."""
        content = json.dumps(pattern, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()
    
    def _calculate_similarity(self, pattern1: Dict, pattern2: Dict) -> float:
        """Calculate similarity between two patterns."""
        keys1 = set(pattern1.keys())
        keys2 = set(pattern2.keys())
        
        if not keys1 or not keys2:
            return 0.0
        
        common = keys1 & keys2
        matching = sum(1 for k in common if pattern1.get(k) == pattern2.get(k))
        
        return matching / max(len(keys1), len(keys2))
    
    def list_cases(self, case_type: Optional[CaseType] = None, limit: int = 50) -> List[Case]:
        """List cases with optional filtering."""
        cases = list(self._cases.values())
        if case_type:
            cases = [c for c in cases if c.case_type == case_type]
        return sorted(cases, key=lambda c: c.last_used or c.created_at, reverse=True)[:limit]
    
    def cleanup_low_confidence(self, threshold: float = 0.3, min_uses: int = 5):
        """Remove cases with low confidence after sufficient uses."""
        to_remove = []
        for case_id, case in self._cases.items():
            total = case.success_count + case.failure_count
            if total >= min_uses and case.confidence < threshold:
                to_remove.append(case_id)
        
        for case_id in to_remove:
            del self._cases[case_id]
        
        if to_remove:
            self._save()
        
        return len(to_remove)
