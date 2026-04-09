"""
Evolution Engine - Coordinates memory updates and system evolution.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path

from .run_memory import RunMemory
from .case_memory import CaseMemory, Case, CaseType
from .rule_memory import RuleMemory, RuleType
from src.evidence.types import RunEvidence, StepEvidence, StepStatus
from src.repair.repair_loop import RepairResult, RepairOutcome


@dataclass
class EvolutionEvent:
    """An evolution event that occurred."""
    event_type: str  # case_promoted, rule_updated, cleanup
    timestamp: datetime
    details: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
        }


class EvolutionEngine:
    """
    Coordinates memory updates and system evolution.
    
    Responsibilities:
    - Analyze completed runs for learnable patterns
    - Promote successful repairs to cases
    - Track rule changes
    - Maintain evolution history
    """
    
    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or Path(".")
        self.run_memory = RunMemory(self.base_dir / "runs")
        self.case_memory = CaseMemory(self.base_dir / "memory" / "cases.json")
        self.rule_memory = RuleMemory(self.base_dir)
        self._events: List[EvolutionEvent] = []
    
    def process_run_completion(self, evidence: RunEvidence, repair_result: Optional[RepairResult] = None) -> List[EvolutionEvent]:
        """
        Process a completed run for learning opportunities.
        
        Args:
            evidence: Run evidence
            repair_result: Optional repair result if repairs were attempted
            
        Returns:
            List of evolution events that occurred
        """
        events = []
        
        # End run memory tracking
        self.run_memory.end_run(evidence.status.value if hasattr(evidence.status, 'value') else str(evidence.status))
        
        # Learn from repairs
        if repair_result and repair_result.outcome in [RepairOutcome.RECOVERED, RepairOutcome.PARTIAL]:
            for attempt in repair_result.repair_attempts:
                if attempt.success:
                    case = self.case_memory.promote_from_evidence(
                        action=self._get_step_action(evidence, attempt.step_id),
                        error_type=attempt.failure_type,
                        repair_strategy=attempt.strategy,
                        success=True,
                    )
                    if case:
                        event = EvolutionEvent(
                            event_type="case_promoted",
                            timestamp=datetime.utcnow(),
                            details={
                                "case_id": case.case_id,
                                "run_id": evidence.run_id,
                                "step_id": attempt.step_id,
                                "strategy": attempt.strategy,
                            },
                        )
                        events.append(event)
        
        # Track success patterns
        if all(s.status == StepStatus.SUCCESS for s in evidence.steps):
            self._record_success_pattern(evidence)
        
        self._events.extend(events)
        return events
    
    def _get_step_action(self, evidence: RunEvidence, step_id: str) -> str:
        """Get action type for a step."""
        for step in evidence.steps:
            if step.step_id == step_id:
                return step.action
        return "unknown"
    
    def _record_success_pattern(self, evidence: RunEvidence):
        """Record a successful execution pattern."""
        actions = [s.action for s in evidence.steps]
        pattern = {
            "plan_id": evidence.plan_id,
            "action_sequence": actions,
            "step_count": len(evidence.steps),
        }
        
        # Create or update success pattern case
        case = Case(
            case_id=f"pattern-{evidence.plan_id}",
            case_type=CaseType.SUCCESS_PATTERN,
            pattern=pattern,
            success_count=1,
            tags=list(set(actions)),
        )
        
        existing = self.case_memory.get_case(case.case_id)
        if existing:
            existing.success_count += 1
            existing.last_used = datetime.utcnow()
        else:
            self.case_memory.add_case(case)
    
    def get_repair_hint(self, action: str, error_type: str) -> Optional[str]:
        """Get a repair hint based on past cases."""
        return self.case_memory.get_repair_suggestion(action, error_type)
    
    def register_rules(self):
        """Register core rule files for version control."""
        rules = [
            ("registry-actions", RuleType.REGISTRY, "registry/actions.yaml", "Action registry"),
            ("registry-schema", RuleType.REGISTRY, "registry/schema.yaml", "Registry schema"),
            ("schema-plan-ir", RuleType.SCHEMA, "schemas/plan-ir.schema.json", "Plan IR schema"),
            ("schema-evidence", RuleType.SCHEMA, "schemas/evidence.schema.json", "Evidence schema"),
        ]
        
        for rule_id, rule_type, path, desc in rules:
            if Path(self.base_dir / path).exists():
                self.rule_memory.register_rule(rule_id, rule_type, path, desc)
    
    def update_registry(self, description: str, changes: List[str], bump: str = "patch") -> Optional[str]:
        """Update the action registry with version tracking."""
        return self.rule_memory.update_rule("registry-actions", description, changes, bump)
    
    def cleanup(self) -> Dict[str, int]:
        """Run cleanup operations on memory systems."""
        removed_cases = self.case_memory.cleanup_low_confidence()
        
        return {
            "removed_cases": removed_cases,
        }
    
    def get_evolution_stats(self) -> Dict[str, Any]:
        """Get statistics about system evolution."""
        cases = self.case_memory.list_cases()
        rules = self.rule_memory.list_rules()
        
        return {
            "total_cases": len(cases),
            "repair_cases": len([c for c in cases if c.case_type == CaseType.REPAIR_CASE]),
            "success_patterns": len([c for c in cases if c.case_type == CaseType.SUCCESS_PATTERN]),
            "registered_rules": len(rules),
            "recent_events": len(self._events),
        }
    
    def get_recent_events(self, limit: int = 20) -> List[EvolutionEvent]:
        """Get recent evolution events."""
        return self._events[-limit:]
