"""
Plan Generator - Generates Plan IR from parsed Goals.
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from datetime import datetime
import uuid

from .goal_parser import Goal, GoalType


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
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "action": self.action,
            "target": self.target,
            "params": self.params or {},
            "evidence": self.evidence or {},
            "retry_policy": self.retry_policy or {},
            "on_fail": self.on_fail,
        }


class PlanGenerator:
    """
    Generates Plan IR from parsed Goals.
    
    Maps goal types and actions to concrete plan steps.
    """
    
    # Default evidence config per action type
    DEFAULT_EVIDENCE = {
        "launch": {"screenshot_after": True},
        "click": {"screenshot_before": True, "screenshot_after": True, "capture_ui_tree": True},
        "type": {"screenshot_after": True},
        "assert": {"screenshot_after": True, "capture_ui_tree": True},
        "wait": {},
        "navigate": {"screenshot_after": True},
        "new_tab": {"screenshot_after": True},
    }
    
    # Default retry policy per action type
    DEFAULT_RETRY = {
        "launch": {"max_attempts": 2, "delay_ms": 2000},
        "click": {"max_attempts": 3, "delay_ms": 500, "backoff": "linear"},
        "type": {"max_attempts": 2, "delay_ms": 500},
        "assert": {"max_attempts": 1},
        "wait": {"max_attempts": 1},
        "navigate": {"max_attempts": 2, "delay_ms": 1000},
        "new_tab": {"max_attempts": 2, "delay_ms": 500},
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
            "goal": {
                "goal_id": goal.goal_id,
                "description": goal.description,
            },
            "app": goal.target_app or "System",
            "preconditions": self._generate_preconditions(goal),
            "steps": [s.to_dict() for s in steps],
            "expected_final_state": goal.expected_state or "Goal completed",
            "metadata": {
                "generated_at": datetime.utcnow().isoformat(),
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
        
        # Add verification step if expected_state exists
        if goal.expected_state and "assert" not in goal.actions:
            steps.append(PlanStep(
                step_id=f"s{step_num}",
                action="assert",
                params={"condition": goal.expected_state},
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
                action="launch_app",
                target=goal.target_app,
                params={"app_name": goal.target_app},
                evidence=self.DEFAULT_EVIDENCE.get("launch", {}),
                retry_policy=self.DEFAULT_RETRY.get("launch", {}),
                on_fail="abort",
            )
        
        elif action == "new_tab":
            return PlanStep(
                step_id=step_id,
                action="keyboard_shortcut",
                params={"shortcut": "cmd+t"},
                evidence=self.DEFAULT_EVIDENCE.get("new_tab", {}),
                retry_policy=self.DEFAULT_RETRY.get("new_tab", {}),
                on_fail="continue",
            )
        
        elif action == "click":
            return PlanStep(
                step_id=step_id,
                action="element_click",
                target=goal.constraints.get("element", "element"),
                params={"locator": goal.constraints.get("element", "")},
                evidence=self.DEFAULT_EVIDENCE.get("click", {}),
                retry_policy=self.DEFAULT_RETRY.get("click", {}),
                on_fail="replan",
            )
        
        elif action == "type":
            return PlanStep(
                step_id=step_id,
                action="keyboard_type",
                params={"text": goal.constraints.get("text", "")},
                evidence=self.DEFAULT_EVIDENCE.get("type", {}),
                retry_policy=self.DEFAULT_RETRY.get("type", {}),
                on_fail="retry",
            )
        
        elif action == "navigate":
            return PlanStep(
                step_id=step_id,
                action="navigate_url",
                params={"url": goal.constraints.get("url", "")},
                evidence=self.DEFAULT_EVIDENCE.get("navigate", {}),
                retry_policy=self.DEFAULT_RETRY.get("navigate", {}),
                on_fail="retry",
            )
        
        elif action == "wait":
            return PlanStep(
                step_id=step_id,
                action="wait_explicit",
                params={"duration_ms": goal.constraints.get("duration", 1000)},
                evidence={},
                retry_policy={"max_attempts": 1},
                on_fail="continue",
            )
        
        elif action == "assert":
            return PlanStep(
                step_id=step_id,
                action="assert_element",
                params={"condition": goal.expected_state or ""},
                evidence=self.DEFAULT_EVIDENCE.get("assert", {}),
                retry_policy=self.DEFAULT_RETRY.get("assert", {}),
                on_fail="continue",
            )
        
        return None
    
    def _generate_preconditions(self, goal: Goal) -> List[Dict[str, Any]]:
        """Generate preconditions for the plan."""
        preconditions = []
        
        # macOS environment check
        preconditions.append({
            "type": "environment",
            "condition": "macos",
        })
        
        # App installed check if targeting specific app
        if goal.target_app:
            preconditions.append({
                "type": "app_installed",
                "app": goal.target_app,
            })
        
        return preconditions
