"""
Run Memory - Tracks current run state and recent decisions.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path
import json


@dataclass
class Decision:
    """A decision made during execution."""
    step_id: str
    decision_type: str  # retry, skip, replan, abort
    reason: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    context: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "decision_type": self.decision_type,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat(),
            "context": self.context,
        }


@dataclass
class RunState:
    """Current state of a run."""
    run_id: str
    plan_id: str
    current_step: int = 0
    total_steps: int = 0
    status: str = "running"  # running, paused, completed, failed
    started_at: datetime = field(default_factory=datetime.utcnow)
    decisions: List[Decision] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "plan_id": self.plan_id,
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "status": self.status,
            "started_at": self.started_at.isoformat(),
            "decisions": [d.to_dict() for d in self.decisions],
            "context": self.context,
        }


class RunMemory:
    """
    Run Memory - Ephemeral memory for current execution.
    
    Tracks:
    - Current step progress
    - Recent decisions
    - Execution context
    """
    
    def __init__(self, storage_dir: Optional[Path] = None):
        self.storage_dir = storage_dir or Path("runs")
        self._current_run: Optional[RunState] = None
        self._recent_decisions: List[Decision] = []
        self._max_recent = 50
    
    def start_run(self, run_id: str, plan_id: str, total_steps: int) -> RunState:
        """Start tracking a new run."""
        self._current_run = RunState(
            run_id=run_id,
            plan_id=plan_id,
            total_steps=total_steps,
        )
        return self._current_run
    
    def update_progress(self, step_index: int, status: str = "running"):
        """Update current step progress."""
        if self._current_run:
            self._current_run.current_step = step_index
            self._current_run.status = status
    
    def record_decision(self, step_id: str, decision_type: str, reason: str, context: Optional[Dict] = None):
        """Record a decision made during execution."""
        decision = Decision(
            step_id=step_id,
            decision_type=decision_type,
            reason=reason,
            context=context or {},
        )
        
        if self._current_run:
            self._current_run.decisions.append(decision)
        
        self._recent_decisions.append(decision)
        if len(self._recent_decisions) > self._max_recent:
            self._recent_decisions.pop(0)
    
    def set_context(self, key: str, value: Any):
        """Set execution context value."""
        if self._current_run:
            self._current_run.context[key] = value
    
    def get_context(self, key: str, default: Any = None) -> Any:
        """Get execution context value."""
        if self._current_run:
            return self._current_run.context.get(key, default)
        return default
    
    def end_run(self, status: str = "completed"):
        """End current run tracking."""
        if self._current_run:
            self._current_run.status = status
            self._save_run_state()
            result = self._current_run
            self._current_run = None
            return result
        return None
    
    def _save_run_state(self):
        """Save run state to disk."""
        if not self._current_run:
            return
        
        run_dir = self.storage_dir / self._current_run.run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        
        state_path = run_dir / "run_memory.json"
        with open(state_path, "w") as f:
            json.dump(self._current_run.to_dict(), f, indent=2)
    
    def get_recent_decisions(self, limit: int = 10) -> List[Decision]:
        """Get recent decisions across runs."""
        return self._recent_decisions[-limit:]
    
    def get_decisions_by_type(self, decision_type: str) -> List[Decision]:
        """Get decisions of a specific type."""
        return [d for d in self._recent_decisions if d.decision_type == decision_type]
    
    @property
    def current_run(self) -> Optional[RunState]:
        """Get current run state."""
        return self._current_run
