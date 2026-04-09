"""
Pipeline - End-to-end automation orchestration.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path
from enum import Enum
import json

from .goal_parser import GoalParser, Goal
from .plan_generator import PlanGenerator
from src.compiler.compiler import Compiler
from src.executor.executor import Executor
from src.evidence.storage import EvidenceStorage
from src.evidence.types import RunEvidence, RunStatus
from src.evaluator.evaluator import Evaluator, EvaluationResult
from src.repair.repair_loop import RepairLoop, RepairResult
from src.memory.evolution import EvolutionEngine


class PipelineStage(Enum):
    """Pipeline execution stages."""
    PARSE_GOAL = "parse_goal"
    GENERATE_PLAN = "generate_plan"
    COMPILE = "compile"
    EXECUTE = "execute"
    EVALUATE = "evaluate"
    REPAIR = "repair"
    FINALIZE = "finalize"


@dataclass
class StageResult:
    """Result of a pipeline stage."""
    stage: PipelineStage
    success: bool
    data: Any = None
    error: Optional[str] = None
    duration_ms: int = 0


@dataclass
class PipelineResult:
    """Complete pipeline execution result."""
    run_id: str
    goal: Optional[Goal] = None
    plan: Optional[Dict[str, Any]] = None
    evidence: Optional[RunEvidence] = None
    evaluation: Optional[EvaluationResult] = None
    repair_result: Optional[RepairResult] = None
    stages: List[StageResult] = field(default_factory=list)
    success: bool = False
    final_status: str = "unknown"
    artifacts_dir: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "goal": self.goal.to_dict() if self.goal else None,
            "plan_id": self.plan.get("plan_id") if self.plan else None,
            "success": self.success,
            "final_status": self.final_status,
            "artifacts_dir": self.artifacts_dir,
            "stages": [
                {
                    "stage": s.stage.value,
                    "success": s.success,
                    "error": s.error,
                    "duration_ms": s.duration_ms,
                }
                for s in self.stages
            ],
            "evaluation": self.evaluation.to_dict() if self.evaluation else None,
        }


class Pipeline:
    """
    End-to-end automation pipeline.
    
    Stages:
    1. Parse Goal - Natural language to structured Goal
    2. Generate Plan - Goal to Plan IR
    3. Compile - Plan IR to executable commands
    4. Execute - Run commands, collect evidence
    5. Evaluate - Classify results
    6. Repair - Attempt recovery if needed
    7. Finalize - Store results, update memory
    """
    
    def __init__(self, base_dir: Optional[Path] = None, mac_cli: str = "mac"):
        self.base_dir = base_dir or Path(".")
        self.mac_cli = mac_cli
        
        # Initialize components
        self.goal_parser = GoalParser()
        self.plan_generator = PlanGenerator()
        self.compiler = Compiler(self.base_dir / "registry" / "actions.yaml")
        self.executor = Executor()
        self.evidence_storage = EvidenceStorage(self.base_dir / "runs")
        self.evaluator = Evaluator()
        self.repair_loop = RepairLoop()
        self.evolution = EvolutionEngine(self.base_dir)
    
    def run(self, goal_text: str, dry_run: bool = False) -> PipelineResult:
        """
        Execute the complete pipeline.
        
        Args:
            goal_text: Natural language goal
            dry_run: If True, don't execute (plan only)
            
        Returns:
            PipelineResult with all artifacts
        """
        import uuid
        run_id = f"run-{uuid.uuid4().hex[:8]}"
        result = PipelineResult(run_id=run_id)
        
        try:
            # Stage 1: Parse Goal
            stage_result, goal = self._parse_goal(goal_text)
            result.stages.append(stage_result)
            if not stage_result.success:
                return self._finalize(result, "parse_failed")
            result.goal = goal
            
            # Stage 2: Generate Plan
            stage_result, plan = self._generate_plan(goal)
            result.stages.append(stage_result)
            if not stage_result.success:
                return self._finalize(result, "plan_failed")
            result.plan = plan
            
            # Stage 3: Compile
            stage_result, compiled = self._compile(plan)
            result.stages.append(stage_result)
            if not stage_result.success:
                return self._finalize(result, "compile_failed")
            
            if dry_run:
                result.success = True
                result.final_status = "dry_run_complete"
                return result
            
            # Stage 4: Execute
            stage_result, evidence = self._execute(plan, run_id)
            result.stages.append(stage_result)
            result.evidence = evidence
            result.artifacts_dir = f"runs/{run_id}"
            
            if not stage_result.success:
                # Continue to evaluation even on failure
                pass
            
            # Stage 5: Evaluate
            stage_result, evaluation = self._evaluate(evidence)
            result.stages.append(stage_result)
            result.evaluation = evaluation
            
            # Stage 6: Repair (if needed)
            if evaluation and evaluation.failed_steps > 0:
                stage_result, repair_result = self._repair(evidence)
                result.stages.append(stage_result)
                result.repair_result = repair_result
                
                if repair_result and repair_result.repaired_evidence:
                    result.evidence = repair_result.repaired_evidence
            
            # Determine final status
            if result.evidence:
                if result.evidence.status == RunStatus.SUCCESS:
                    result.success = True
                    result.final_status = "success"
                elif result.repair_result and result.repair_result.outcome.value == "recovered":
                    result.success = True
                    result.final_status = "recovered"
                elif result.evidence.status == RunStatus.PARTIAL:
                    result.success = False
                    result.final_status = "partial"
                else:
                    result.success = False
                    result.final_status = "failed"
            
            return self._finalize(result, result.final_status)
            
        except Exception as e:
            result.stages.append(StageResult(
                stage=PipelineStage.FINALIZE,
                success=False,
                error=str(e),
            ))
            result.final_status = "error"
            return result
    
    def _parse_goal(self, goal_text: str) -> tuple:
        """Stage 1: Parse goal."""
        start = datetime.utcnow()
        try:
            goal = self.goal_parser.parse(goal_text)
            duration = int((datetime.utcnow() - start).total_seconds() * 1000)
            return StageResult(
                stage=PipelineStage.PARSE_GOAL,
                success=True,
                data=goal.to_dict(),
                duration_ms=duration,
            ), goal
        except Exception as e:
            duration = int((datetime.utcnow() - start).total_seconds() * 1000)
            return StageResult(
                stage=PipelineStage.PARSE_GOAL,
                success=False,
                error=str(e),
                duration_ms=duration,
            ), None
    
    def _generate_plan(self, goal: Goal) -> tuple:
        """Stage 2: Generate plan."""
        start = datetime.utcnow()
        try:
            plan = self.plan_generator.generate(goal)
            duration = int((datetime.utcnow() - start).total_seconds() * 1000)
            return StageResult(
                stage=PipelineStage.GENERATE_PLAN,
                success=True,
                data=plan,
                duration_ms=duration,
            ), plan
        except Exception as e:
            duration = int((datetime.utcnow() - start).total_seconds() * 1000)
            return StageResult(
                stage=PipelineStage.GENERATE_PLAN,
                success=False,
                error=str(e),
                duration_ms=duration,
            ), None
    
    def _compile(self, plan: Dict[str, Any]) -> tuple:
        """Stage 3: Compile plan."""
        start = datetime.utcnow()
        try:
            compiled = self.compiler.compile_plan(plan)
            duration = int((datetime.utcnow() - start).total_seconds() * 1000)
            
            # Check for validation errors
            errors = [s for s in compiled.get("steps", []) if s.get("error")]
            if errors:
                return StageResult(
                    stage=PipelineStage.COMPILE,
                    success=False,
                    error=f"Compilation errors: {errors}",
                    duration_ms=duration,
                ), None
            
            return StageResult(
                stage=PipelineStage.COMPILE,
                success=True,
                data=compiled,
                duration_ms=duration,
            ), compiled
        except Exception as e:
            duration = int((datetime.utcnow() - start).total_seconds() * 1000)
            return StageResult(
                stage=PipelineStage.COMPILE,
                success=False,
                error=str(e),
                duration_ms=duration,
            ), None
    
    def _execute(self, plan: Dict[str, Any], run_id: str) -> tuple:
        """Stage 4: Execute plan."""
        start = datetime.utcnow()
        try:
            evidence = self.executor.execute(plan, run_id)
            duration = int((datetime.utcnow() - start).total_seconds() * 1000)
            
            # Save evidence
            self.evidence_storage.save_evidence(evidence)
            self.evidence_storage.save_input_plan(run_id, plan)
            
            success = evidence.status == RunStatus.SUCCESS
            return StageResult(
                stage=PipelineStage.EXECUTE,
                success=success,
                data={"run_id": run_id, "status": evidence.status.value},
                duration_ms=duration,
            ), evidence
        except Exception as e:
            duration = int((datetime.utcnow() - start).total_seconds() * 1000)
            return StageResult(
                stage=PipelineStage.EXECUTE,
                success=False,
                error=str(e),
                duration_ms=duration,
            ), None
    
    def _evaluate(self, evidence: RunEvidence) -> tuple:
        """Stage 5: Evaluate results."""
        start = datetime.utcnow()
        try:
            evaluation = self.evaluator.evaluate(evidence)
            duration = int((datetime.utcnow() - start).total_seconds() * 1000)
            return StageResult(
                stage=PipelineStage.EVALUATE,
                success=True,
                data=evaluation.to_dict(),
                duration_ms=duration,
            ), evaluation
        except Exception as e:
            duration = int((datetime.utcnow() - start).total_seconds() * 1000)
            return StageResult(
                stage=PipelineStage.EVALUATE,
                success=False,
                error=str(e),
                duration_ms=duration,
            ), None
    
    def _repair(self, evidence: RunEvidence) -> tuple:
        """Stage 6: Attempt repairs."""
        start = datetime.utcnow()
        try:
            repair_result = self.repair_loop.run(evidence)
            duration = int((datetime.utcnow() - start).total_seconds() * 1000)
            
            success = repair_result.outcome.value in ["recovered", "partial"]
            return StageResult(
                stage=PipelineStage.REPAIR,
                success=success,
                data=repair_result.to_dict(),
                duration_ms=duration,
            ), repair_result
        except Exception as e:
            duration = int((datetime.utcnow() - start).total_seconds() * 1000)
            return StageResult(
                stage=PipelineStage.REPAIR,
                success=False,
                error=str(e),
                duration_ms=duration,
            ), None
    
    def _finalize(self, result: PipelineResult, status: str) -> PipelineResult:
        """Stage 7: Finalize and store results."""
        result.final_status = status
        
        # Update evolution/memory if we have evidence
        if result.evidence:
            self.evolution.process_run_completion(result.evidence, result.repair_result)
        
        # Save pipeline result
        if result.artifacts_dir:
            result_path = self.base_dir / result.artifacts_dir / "pipeline_result.json"
            result_path.parent.mkdir(parents=True, exist_ok=True)
            with open(result_path, "w") as f:
                json.dump(result.to_dict(), f, indent=2)
        
        return result

class Pipeline:
    def __init__(self, base_dir: Optional[Path] = None, mac_cli: str = "mac"):
        self.base_dir = base_dir or Path(".")
        self.mac_cli = mac_cli
        self.goal_parser = GoalParser()
        self.plan_generator = PlanGenerator()
        self.compiler = Compiler(self.base_dir / "registry" / "actions.yaml")
        self.executor = Executor()
        self.evidence_storage = EvidenceStorage(self.base_dir / "runs")
        self.evaluator = Evaluator()
        self.repair_loop = RepairLoop()
        self.evolution = EvolutionEngine(self.base_dir)
    
    def run(self, goal_text: str, dry_run: bool = False) -> PipelineResult:
        import uuid
        run_id = f"run-{uuid.uuid4().hex[:8]}"
        result = PipelineResult(run_id=run_id)
        try:
            stage_result, goal = self._parse_goal(goal_text)
            result.stages.append(stage_result)
            if not stage_result.success: return self._finalize(result, "parse_failed")
            result.goal = goal
            stage_result, plan = self._generate_plan(goal)
            result.stages.append(stage_result)
            if not stage_result.success: return self._finalize(result, "plan_failed")
            result.plan = plan
            stage_result, compiled = self._compile(plan)
            result.stages.append(stage_result)
            if not stage_result.success: return self._finalize(result, "compile_failed")
            if dry_run:
                result.success = True
                result.final_status = "dry_run_complete"
                return result
            stage_result, evidence = self._execute(plan, run_id)
            result.stages.append(stage_result)
            result.evidence = evidence
            result.artifacts_dir = f"runs/{run_id}"
            stage_result, evaluation = self._evaluate(evidence)
            result.stages.append(stage_result)
            result.evaluation = evaluation
            if evaluation and evaluation.failed_steps > 0:
                stage_result, repair_result = self._repair(evidence)
                result.stages.append(stage_result)
                result.repair_result = repair_result
                if repair_result and repair_result.repaired_evidence:
                    result.evidence = repair_result.repaired_evidence
            if result.evidence:
                if result.evidence.status == RunStatus.SUCCESS:
                    result.success, result.final_status = True, "success"
                elif result.repair_result and result.repair_result.outcome.value == "recovered":
                    result.success, result.final_status = True, "recovered"
                elif result.evidence.status == RunStatus.PARTIAL:
                    result.success, result.final_status = False, "partial"
                else:
                    result.success, result.final_status = False, "failed"
            return self._finalize(result, result.final_status)
        except Exception as e:
            result.stages.append(StageResult(stage=PipelineStage.FINALIZE, success=False, error=str(e)))
            result.final_status = "error"
            return result

    def _parse_goal(self, goal_text: str) -> tuple:
        start = datetime.utcnow()
        try:
            goal = self.goal_parser.parse(goal_text)
            duration = int((datetime.utcnow() - start).total_seconds() * 1000)
            return StageResult(stage=PipelineStage.PARSE_GOAL, success=True, data=goal.to_dict(), duration_ms=duration), goal
        except Exception as e:
            return StageResult(stage=PipelineStage.PARSE_GOAL, success=False, error=str(e), duration_ms=int((datetime.utcnow() - start).total_seconds() * 1000)), None

    def _generate_plan(self, goal: Goal) -> tuple:
        start = datetime.utcnow()
        try:
            plan = self.plan_generator.generate(goal)
            return StageResult(stage=PipelineStage.GENERATE_PLAN, success=True, data=plan, duration_ms=int((datetime.utcnow() - start).total_seconds() * 1000)), plan
        except Exception as e:
            return StageResult(stage=PipelineStage.GENERATE_PLAN, success=False, error=str(e), duration_ms=int((datetime.utcnow() - start).total_seconds() * 1000)), None

    def _compile(self, plan: Dict[str, Any]) -> tuple:
        start = datetime.utcnow()
        try:
            compiled = self.compiler.compile_plan(plan)
            errors = [s for s in compiled.get("steps", []) if s.get("error")]
            if errors:
                return StageResult(stage=PipelineStage.COMPILE, success=False, error=f"Compilation errors: {errors}", duration_ms=int((datetime.utcnow() - start).total_seconds() * 1000)), None
            return StageResult(stage=PipelineStage.COMPILE, success=True, data=compiled, duration_ms=int((datetime.utcnow() - start).total_seconds() * 1000)), compiled
        except Exception as e:
            return StageResult(stage=PipelineStage.COMPILE, success=False, error=str(e), duration_ms=int((datetime.utcnow() - start).total_seconds() * 1000)), None

    def _execute(self, plan: Dict[str, Any], run_id: str) -> tuple:
        start = datetime.utcnow()
        try:
            evidence = self.executor.execute(plan, run_id)
            self.evidence_storage.save_evidence(evidence)
            self.evidence_storage.save_input_plan(run_id, plan)
            return StageResult(stage=PipelineStage.EXECUTE, success=evidence.status == RunStatus.SUCCESS, data={"run_id": run_id, "status": evidence.status.value}, duration_ms=int((datetime.utcnow() - start).total_seconds() * 1000)), evidence
        except Exception as e:
            return StageResult(stage=PipelineStage.EXECUTE, success=False, error=str(e), duration_ms=int((datetime.utcnow() - start).total_seconds() * 1000)), None

    def _evaluate(self, evidence: RunEvidence) -> tuple:
        start = datetime.utcnow()
        try:
            evaluation = self.evaluator.evaluate(evidence)
            return StageResult(stage=PipelineStage.EVALUATE, success=True, data=evaluation.to_dict(), duration_ms=int((datetime.utcnow() - start).total_seconds() * 1000)), evaluation
        except Exception as e:
            return StageResult(stage=PipelineStage.EVALUATE, success=False, error=str(e), duration_ms=int((datetime.utcnow() - start).total_seconds() * 1000)), None

    def _repair(self, evidence: RunEvidence) -> tuple:
        start = datetime.utcnow()
        try:
            repair_result = self.repair_loop.run(evidence)
            return StageResult(stage=PipelineStage.REPAIR, success=repair_result.outcome.value in ["recovered", "partial"], data=repair_result.to_dict(), duration_ms=int((datetime.utcnow() - start).total_seconds() * 1000)), repair_result
        except Exception as e:
            return StageResult(stage=PipelineStage.REPAIR, success=False, error=str(e), duration_ms=int((datetime.utcnow() - start).total_seconds() * 1000)), None

    def _finalize(self, result: PipelineResult, status: str) -> PipelineResult:
        result.final_status = status
        if result.evidence:
            self.evolution.process_run_completion(result.evidence, result.repair_result)
        if result.artifacts_dir:
            result_path = self.base_dir / result.artifacts_dir / "pipeline_result.json"
            result_path.parent.mkdir(parents=True, exist_ok=True)
            with open(result_path, "w") as f:
                json.dump(result.to_dict(), f, indent=2)
        return result
