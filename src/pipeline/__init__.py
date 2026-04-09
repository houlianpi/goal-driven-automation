"""Pipeline - End-to-end automation orchestration."""
from .pipeline import Pipeline, PipelineResult
from .goal_parser import GoalParser, Goal

__all__ = ["Pipeline", "PipelineResult", "GoalParser", "Goal"]
from .plan_generator import PlanGenerator
__all__.append("PlanGenerator")
