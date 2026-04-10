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
        if " and " in text or " then " in text:
            return True
        if "," not in text:
            return False

        parts = [part.strip() for part in text.split(",") if part.strip()]
        action_parts = sum(1 for part in parts if self._infer_actions(part))
        return action_parts > 1
    
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
        app = self._extract_known_app(text)
        constraints = self._build_click_constraints(text, default_app=app)
        element = constraints.get("element", "element")
        return Goal(
            goal_id=goal_id,
            description=text,
            goal_type=GoalType.UI_NAVIGATION,
            target_app=app,
            actions=["click"],
            expected_state=f"Clicked on {element}",
            constraints=constraints,
        )

    def _parse_data_entry(self, goal_id: str, text: str) -> Goal:
        """Parse data entry goal."""
        app = self._extract_known_app(text)
        constraints = self._build_type_constraints(text, default_app=app)
        return Goal(
            goal_id=goal_id,
            description=text,
            goal_type=GoalType.DATA_ENTRY,
            target_app=app,
            actions=["type"],
            expected_state="Text entered",
            constraints=constraints,
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
        constraints: Dict[str, Any] = {}

        for part in parts:
            part = part.strip()
            if not part:
                continue
            
            lower = part.lower()
            if lower.startswith("open"):
                actions.append("launch")
                app = self._extract_known_app(part) or self._extract_app(part)
            elif "new tab" in lower:
                actions.append("new_tab")
            elif "click" in lower:
                actions.append("click")
                constraints.update(self._build_click_constraints(part, default_app=app))
            elif "type" in lower:
                actions.append("type")
                constraints.update(self._build_type_constraints(part, default_app=app))
            elif "verify" in lower or "check" in lower:
                actions.append("assert")
            elif "wait" in lower:
                actions.append("wait")
            elif "navigate" in lower or "go to" in lower:
                actions.append("navigate")

        if app and ("click" in actions or "type" in actions):
            constraints.setdefault("app", app)

        return Goal(
            goal_id=goal_id,
            description=text,
            goal_type=GoalType.COMPOSITE,
            target_app=app,
            actions=actions or ["unknown"],
            constraints=constraints,
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
        app = self._extract_known_app(text)
        if app:
            return app

        # Try to extract from "Open [AppName]"
        match = re.search(r'open\s+(\w+)', text, re.IGNORECASE)
        if match:
            return match.group(1).title()

        return "Unknown"

    def _extract_known_app(self, text: str) -> Optional[str]:
        """Extract a known app name from text when present."""
        lower = text.lower()
        for pattern, app_name in self.APP_PATTERNS.items():
            if pattern in lower:
                return app_name
        return None

    def _infer_actions(self, text: str) -> List[str]:
        """Infer semantic actions present in a text fragment."""
        lower = text.lower()
        actions = []
        if lower.startswith("open"):
            actions.append("launch")
        if "new tab" in lower:
            actions.append("new_tab")
        if "click" in lower or "tap" in lower:
            actions.append("click")
        if "type" in lower or "enter" in lower or "input" in lower:
            actions.append("type")
        if "verify" in lower or "check" in lower or "assert" in lower:
            actions.append("assert")
        if "wait" in lower:
            actions.append("wait")
        if "navigate" in lower or "go to" in lower:
            actions.append("navigate")
        return actions

    def _build_click_constraints(self, text: str, default_app: Optional[str] = None) -> Dict[str, Any]:
        """Build click constraints with explicit locator and app context."""
        app = self._extract_known_app(text) or default_app
        element = self._extract_element(text)
        locator_text = self._extract_locator_text(text, fallback=element)
        locator_role = self._extract_locator_role(text)

        constraints: Dict[str, Any] = {"element": element}
        if app:
            constraints["app"] = app
        if locator_text:
            constraints["locator_text"] = locator_text
        if locator_role:
            constraints["locator_role"] = locator_role
        return constraints

    def _build_type_constraints(self, text: str, default_app: Optional[str] = None) -> Dict[str, Any]:
        """Build type constraints with explicit context metadata."""
        app = self._extract_known_app(text) or default_app
        constraints: Dict[str, Any] = {
            "text": self._extract_quoted(text),
            "requires_focused_target": True,
        }
        if app:
            constraints["app"] = app
        return constraints
    
    def _extract_element(self, text: str) -> str:
        """Extract element description from text."""
        # Try quoted text first
        quoted = self._extract_quoted(text)
        if quoted:
            return quoted
        
        # Try "click on [element]" pattern
        match = re.search(r'(?:click|tap)\s+(?:on\s+)?(.+?)(?:\s+in\s+\w[\w\s]+)?$', text, re.IGNORECASE)
        if match:
            element = match.group(1).strip()
            element = re.sub(r'^(?:the|a|an)\s+', '', element, flags=re.IGNORECASE)
            element = re.sub(
                r'\s+(button|link|tab|field|textbox|text field|menu item|menu)$',
                '',
                element,
                flags=re.IGNORECASE,
            )
            return element.strip()
        
        return "element"

    def _extract_locator_text(self, text: str, fallback: str = "") -> str:
        """Extract locator text separately from the broader element description."""
        quoted = self._extract_quoted(text)
        if quoted:
            return quoted
        return fallback

    def _extract_locator_role(self, text: str) -> str:
        """Extract a simple locator role when explicitly mentioned."""
        match = re.search(
            r'\b(button|link|tab|field|textbox|text field|menu item|menu)\b',
            text,
            re.IGNORECASE,
        )
        if match:
            return match.group(1).lower()
        return ""
    
    def _extract_quoted(self, text: str) -> str:
        """Extract quoted text."""
        match = re.search(r'["\']([^"\']+)["\']', text)
        if match:
            return match.group(1)
        return ""
