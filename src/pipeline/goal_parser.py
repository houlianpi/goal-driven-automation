"""
Goal Parser - Parses natural language goals into structured format.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum
import re


class GoalType(Enum):
    """Types of goals."""
    APP_LAUNCH = "app_launch"
    UI_NAVIGATION = "ui_navigation"
    DATA_ENTRY = "data_entry"
    VERIFICATION = "verification"
    COMPOSITE = "composite"


@dataclass
class Goal:
    """A parsed goal."""
    goal_id: str
    description: str
    goal_type: GoalType
    target_app: Optional[str] = None
    actions: List[str] = field(default_factory=list)
    expected_state: Optional[str] = None
    constraints: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "description": self.description,
            "goal_type": self.goal_type.value,
            "target_app": self.target_app,
            "actions": self.actions,
            "expected_state": self.expected_state,
            "constraints": self.constraints,
        }


class GoalParser:
    """
    Parses natural language goals into structured Goal objects.
    
    Supports common patterns:
    - "Open [app]" → APP_LAUNCH
    - "Open [app] and [action]" → COMPOSITE
    - "Click [element]" → UI_NAVIGATION
    - "Type [text]" → DATA_ENTRY
    - "Verify [condition]" → VERIFICATION
    """
    
    # App name patterns
    APP_PATTERNS = {
        "edge": "Microsoft Edge",
        "safari": "Safari",
        "chrome": "Google Chrome",
        "firefox": "Firefox",
        "finder": "Finder",
        "terminal": "Terminal",
        "notes": "Notes",
        "mail": "Mail",
    }
    
    def parse(self, goal_text: str) -> Goal:
        """
        Parse a goal from natural language.
        
        Args:
            goal_text: Natural language goal description
            
        Returns:
            Parsed Goal object
        """
        goal_text = goal_text.strip()
        lower = goal_text.lower()
        
        # Generate goal ID
        goal_id = f"goal-{hash(goal_text) % 100000:05d}"
        
        # Detect goal type and extract details
        if self._is_composite(lower):
            return self._parse_composite(goal_id, goal_text)
        elif lower.startswith("open"):
            return self._parse_app_launch(goal_id, goal_text)
        elif "click" in lower or "tap" in lower:
            return self._parse_ui_navigation(goal_id, goal_text)
        elif "type" in lower or "enter" in lower or "input" in lower:
            return self._parse_data_entry(goal_id, goal_text)
        elif "verify" in lower or "check" in lower or "assert" in lower:
            return self._parse_verification(goal_id, goal_text)
        else:
            # Default to composite with extracted actions
            return self._parse_generic(goal_id, goal_text)
    
    def _is_composite(self, text: str) -> bool:
        """Check if goal contains multiple actions."""
        return " and " in text or " then " in text or "," in text
    
    def _parse_app_launch(self, goal_id: str, text: str) -> Goal:
        """Parse app launch goal."""
        app = self._extract_app(text)
        return Goal(
            goal_id=goal_id,
            description=text,
            goal_type=GoalType.APP_LAUNCH,
            target_app=app,
            actions=["launch"],
            expected_state=f"{app} is running and focused",
        )
    
    def _parse_ui_navigation(self, goal_id: str, text: str) -> Goal:
        """Parse UI navigation goal."""
        element = self._extract_element(text)
        return Goal(
            goal_id=goal_id,
            description=text,
            goal_type=GoalType.UI_NAVIGATION,
            actions=["click"],
            expected_state=f"Clicked on {element}",
            constraints={"element": element},
        )
    
    def _parse_data_entry(self, goal_id: str, text: str) -> Goal:
        """Parse data entry goal."""
        data = self._extract_quoted(text)
        return Goal(
            goal_id=goal_id,
            description=text,
            goal_type=GoalType.DATA_ENTRY,
            actions=["type"],
            expected_state="Text entered",
            constraints={"text": data},
        )
    
    def _parse_verification(self, goal_id: str, text: str) -> Goal:
        """Parse verification goal."""
        condition = text.lower().replace("verify", "").replace("check", "").replace("assert", "").strip()
        return Goal(
            goal_id=goal_id,
            description=text,
            goal_type=GoalType.VERIFICATION,
            actions=["assert"],
            expected_state=condition,
        )
    
    def _parse_composite(self, goal_id: str, text: str) -> Goal:
        """Parse composite goal with multiple actions."""
        # Split by conjunctions
        parts = re.split(r'\s+and\s+|\s+then\s+|,\s*', text, flags=re.IGNORECASE)
        
        actions = []
        app = None
        
        for part in parts:
            part = part.strip()
            if not part:
                continue
            
            lower = part.lower()
            if lower.startswith("open"):
                actions.append("launch")
                app = self._extract_app(part)
            elif "new tab" in lower:
                actions.append("new_tab")
            elif "click" in lower:
                actions.append("click")
            elif "type" in lower:
                actions.append("type")
            elif "verify" in lower or "check" in lower:
                actions.append("assert")
            elif "wait" in lower:
                actions.append("wait")
            elif "navigate" in lower or "go to" in lower:
                actions.append("navigate")
        
        return Goal(
            goal_id=goal_id,
            description=text,
            goal_type=GoalType.COMPOSITE,
            target_app=app,
            actions=actions or ["unknown"],
        )
    
    def _parse_generic(self, goal_id: str, text: str) -> Goal:
        """Parse generic goal."""
        return Goal(
            goal_id=goal_id,
            description=text,
            goal_type=GoalType.COMPOSITE,
            actions=["execute"],
        )
    
    def _extract_app(self, text: str) -> str:
        """Extract app name from text."""
        lower = text.lower()
        for pattern, app_name in self.APP_PATTERNS.items():
            if pattern in lower:
                return app_name
        
        # Try to extract from "Open [AppName]"
        match = re.search(r'open\s+(\w+)', lower)
        if match:
            return match.group(1).title()
        
        return "Unknown"
    
    def _extract_element(self, text: str) -> str:
        """Extract element description from text."""
        # Try quoted text first
        quoted = self._extract_quoted(text)
        if quoted:
            return quoted
        
        # Try "click on [element]" pattern
        match = re.search(r'click\s+(?:on\s+)?(.+)', text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        
        return "element"
    
    def _extract_quoted(self, text: str) -> str:
        """Extract quoted text."""
        match = re.search(r'["\']([^"\']+)["\']', text)
        if match:
            return match.group(1)
        return ""
