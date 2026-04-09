"""Unit tests for Pipeline."""
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.pipeline.goal_parser import GoalParser, GoalType
from src.pipeline.plan_generator import PlanGenerator
from src.pipeline.pipeline import Pipeline, PipelineStage


class TestGoalParser:
    @pytest.fixture
    def parser(self):
        return GoalParser()
    
    def test_parse_app_launch(self, parser):
        goal = parser.parse("Open Edge")
        assert goal.goal_type == GoalType.APP_LAUNCH
        assert goal.target_app == "Microsoft Edge"
        assert "launch" in goal.actions
    
    def test_parse_composite(self, parser):
        goal = parser.parse("Open Edge and create new tab")
        assert goal.goal_type == GoalType.COMPOSITE
        assert "launch" in goal.actions
        assert "new_tab" in goal.actions
    
    def test_parse_safari(self, parser):
        goal = parser.parse("Open Safari")
        assert goal.target_app == "Safari"
    
    def test_parse_click(self, parser):
        goal = parser.parse("Click on 'Submit' button")
        assert goal.goal_type == GoalType.UI_NAVIGATION
        assert "click" in goal.actions


class TestPlanGenerator:
    @pytest.fixture
    def generator(self):
        return PlanGenerator()
    
    def test_generate_launch_plan(self, generator):
        parser = GoalParser()
        goal = parser.parse("Open Edge")
        plan = generator.generate(goal)
        
        assert plan["plan_id"].startswith("plan-")
        assert plan["app"] == "Microsoft Edge"
        assert len(plan["steps"]) >= 1
        assert plan["steps"][0]["action"] == "launch_app"
    
    def test_generate_composite_plan(self, generator):
        parser = GoalParser()
        goal = parser.parse("Open Edge and create new tab")
        plan = generator.generate(goal)
        
        actions = [s["action"] for s in plan["steps"]]
        assert "launch_app" in actions
        assert "keyboard_shortcut" in actions


class TestPipeline:
    def test_dry_run(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create minimal registry
            registry_dir = Path(tmpdir) / "registry"
            registry_dir.mkdir()
            (registry_dir / "actions.yaml").write_text("""
version: "1.0"
actions:
  launch_app:
    cli_template: "mac app launch {app_name}"
  keyboard_shortcut:
    cli_template: "mac keyboard shortcut {shortcut}"
  assert_element:
    cli_template: "mac assert {condition}"
""")
            
            pipeline = Pipeline(base_dir=Path(tmpdir))
            result = pipeline.run("Open Edge and create new tab", dry_run=True)
            
            assert result.final_status == "dry_run_complete"
            assert result.success is True
            assert result.goal is not None
            assert result.plan is not None
    
    def test_stages_recorded(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            registry_dir = Path(tmpdir) / "registry"
            registry_dir.mkdir()
            (registry_dir / "actions.yaml").write_text("""
version: "1.0"
actions:
  launch_app:
    cli_template: "mac app launch {app_name}"
""")
            
            pipeline = Pipeline(base_dir=Path(tmpdir))
            result = pipeline.run("Open Edge", dry_run=True)
            
            stages = [s.stage for s in result.stages]
            assert PipelineStage.PARSE_GOAL in stages
            assert PipelineStage.GENERATE_PLAN in stages
            assert PipelineStage.COMPILE in stages
