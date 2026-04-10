"""
Plan Generator - Generates semantic Plan IR from parsed Goals.
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import uuid

from .goal_parser import Goal, GoalType
from src.time_utils import utc_now


@dataclass
class PlanStep:
    """A step in the plan."""
    step_id: str
    action: str
    target: Optional[str] = None
    params: Dict[str, Any] = None
    evidence: Dict[str, bool] = None
    retry_policy: Dict[str, Any] = None
    on_fail: str = "abort"
    review_required: bool = False
    metadata: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        data = {
            "step_id": self.step_id,
            "action": self.action,
            "params": self.params or {},
            "evidence": self.evidence or {},
            "retry_policy": self.retry_policy or {},
            "on_fail": self.on_fail,
            "review_required": self.review_required,
        }
        if self.target is not None:
            data["target"] = self.target
        if self.metadata:
            data["metadata"] = self.metadata
        return data


class PlanGenerator:
    """
    Generates semantic Plan IR from parsed Goals.

    The generator emits stable, schema-level actions such as
    ``launch`` and ``shortcut``. The compiler is responsible for
    mapping those actions to capability-layer registry actions.
    """
    
    # Default evidence config per action type
    DEFAULT_EVIDENCE = {
        "launch": {"screenshot_after": True},
        "click": {"screenshot_before": True, "screenshot_after": True, "capture_ui_tree": True},
        "type": {"screenshot_after": True},
        "assert": {"screenshot_after": True, "capture_ui_tree": True},
        "wait": {},
        "shortcut": {"screenshot_after": True},
    }
    
    # Default retry policy per action type
    DEFAULT_RETRY = {
        "launch": {"max_attempts": 2, "delay_ms": 2000},
        "click": {"max_attempts": 3, "delay_ms": 500, "backoff": "linear"},
        "type": {"max_attempts": 2, "delay_ms": 500},
        "assert": {"max_attempts": 1},
        "wait": {"max_attempts": 1},
        "shortcut": {"max_attempts": 2, "delay_ms": 500},
    }

    SHORTCUTS = {
        "new_tab": ["command", "t"],
    }
    
    def generate(self, goal: Goal) -> Dict[str, Any]:
        """
        Generate a Plan IR from a Goal.
        
        Args:
            goal: Parsed goal
            
        Returns:
            Plan IR dictionary
        """
        plan_id = f"plan-{uuid.uuid4().hex[:8]}"
        
        steps = self._generate_steps(goal)
        
        return {
            "plan_id": plan_id,
            "version": "1.0.0",
            "goal": goal.description,
            "app": goal.target_app or "System",
            "preconditions": self._generate_preconditions(goal),
            "steps": [s.to_dict() for s in steps],
            "expected_final_state": goal.expected_state or "Goal completed",
            "created_at": utc_now().isoformat(),
            "metadata": {
                "goal_id": goal.goal_id,
                "goal_type": goal.goal_type.value,
            },
        }
    
    def _generate_steps(self, goal: Goal) -> List[PlanStep]:
        """Generate plan steps from goal actions."""
        steps = []
        step_num = 1
        
        for action in goal.actions:
            step = self._create_step(step_num, action, goal)
            if step:
                steps.append(step)
                step_num += 1
        
        # Add a semantic verification step when the goal includes a final state.
        if goal.expected_state and "assert" not in goal.actions:
            params: Dict[str, Any] = {"condition": goal.expected_state}
            if goal.target_app:
                params["locator"] = goal.target_app
                params["strategy"] = "accessibility_id"
            steps.append(PlanStep(
                step_id=f"s{step_num}",
                action="assert",
                params=params,
                evidence=self.DEFAULT_EVIDENCE.get("assert", {}),
                retry_policy=self.DEFAULT_RETRY.get("assert", {}),
                on_fail="continue",
            ))
        
        return steps
    
    def _create_step(self, num: int, action: str, goal: Goal) -> Optional[PlanStep]:
        """Create a single plan step."""
        step_id = f"s{num}"
        
        if action == "launch":
            return PlanStep(
                step_id=step_id,
                action="launch",
                target=goal.target_app,
                params={"app": goal.target_app},
                evidence=self.DEFAULT_EVIDENCE.get("launch", {}),
                retry_policy=self.DEFAULT_RETRY.get("launch", {}),
                on_fail="abort",
            )

        elif action == "new_tab":
            return PlanStep(
                step_id=step_id,
                action="shortcut",
                params={"keys": self.SHORTCUTS["new_tab"]},
                evidence=self.DEFAULT_EVIDENCE.get("shortcut", {}),
                retry_policy=self.DEFAULT_RETRY.get("shortcut", {}),
                on_fail="continue",
            )

        elif action == "click":
            params = {"selector": goal.constraints.get("element", "")}
            if goal.constraints.get("app"):
                params["app"] = goal.constraints["app"]
            if goal.constraints.get("locator_text"):
                params["locator_text"] = goal.constraints["locator_text"]
            if goal.constraints.get("locator_role"):
                params["locator_role"] = goal.constraints["locator_role"]

            confidence = "medium" if goal.constraints.get("app") else "low"
            return PlanStep(
                step_id=step_id,
                action="click",
                target=goal.constraints.get("element", "element"),
                params=params,
                evidence=self.DEFAULT_EVIDENCE.get("click", {}),
                retry_policy=self.DEFAULT_RETRY.get("click", {}),
                on_fail="replan" if confidence != "low" else "human_review",
                review_required=confidence == "low",
                metadata={"context_confidence": confidence},
            )
        
        elif action == "type":
            params = {"text": goal.constraints.get("text", "")}
            if goal.constraints.get("app"):
                params["app"] = goal.constraints["app"]
            if goal.constraints.get("requires_focused_target") is not None:
                params["requires_focused_target"] = goal.constraints["requires_focused_target"]
            if goal.constraints.get("input_target"):
                params["input_target"] = goal.constraints["input_target"]

            confidence = "medium" if goal.constraints.get("app") else "low"
            return PlanStep(
                step_id=step_id,
                action="type",
                params=params,
                evidence=self.DEFAULT_EVIDENCE.get("type", {}),
                retry_policy=self.DEFAULT_RETRY.get("type", {}),
                on_fail="retry" if confidence != "low" else "human_review",
                review_required=confidence == "low",
                metadata={"context_confidence": confidence},
            )
        
        elif action == "navigate":
            return PlanStep(
                step_id=step_id,
                action="type",
                params={"text": goal.constraints.get("url", "")},
                evidence=self.DEFAULT_EVIDENCE.get("type", {}),
                retry_policy=self.DEFAULT_RETRY.get("type", {}),
                on_fail="retry",
            )

        elif action == "wait":
            return PlanStep(
                step_id=step_id,
                action="wait",
                params={"seconds": goal.constraints.get("duration", 1000) / 1000.0},
                evidence={},
                retry_policy={"max_attempts": 1},
                on_fail="continue",
            )
        
        elif action == "assert":
            params: Dict[str, Any] = {"condition": goal.expected_state or "window visible"}
            if goal.constraints.get("element"):
                params["locator"] = goal.constraints["element"]
                params["strategy"] = "accessibility_id"
            return PlanStep(
                step_id=step_id,
                action="assert",
                params=params,
                evidence=self.DEFAULT_EVIDENCE.get("assert", {}),
                retry_policy=self.DEFAULT_RETRY.get("assert", {}),
                on_fail="continue",
            )
        
        return None
    
    def _generate_preconditions(self, goal: Goal) -> List[Dict[str, Any]]:
        """Generate preconditions for the plan."""
        preconditions = []
        
        preconditions.append({
            "check": "environment",
            "expected": "macos",
            "on_fail": "abort",
        })

        if goal.target_app:
            preconditions.append({
                "check": "app_installed",
                "expected": goal.target_app,
                "on_fail": "abort",
            })
        
        return preconditions
