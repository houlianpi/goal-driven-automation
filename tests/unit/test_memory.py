"""Unit tests for Memory system."""
import pytest
import tempfile
from pathlib import Path
from datetime import datetime

from src.memory.run_memory import RunMemory, RunState, Decision
from src.memory.case_memory import CaseMemory, Case, CaseType
from src.memory.rule_memory import RuleMemory, RuleType
from src.memory.evolution import EvolutionEngine


class TestRunMemory:
    def test_start_and_end_run(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            memory = RunMemory(Path(tmpdir))
            state = memory.start_run("run-001", "plan-test", 5)
            assert state.run_id == "run-001"
            assert state.status == "running"
            
            result = memory.end_run("completed")
            assert result.status == "completed"
            assert memory.current_run is None
    
    def test_record_decisions(self):
        memory = RunMemory()
        memory.start_run("run-001", "plan-test", 5)
        
        memory.record_decision("s1", "retry", "Transient failure")
        memory.record_decision("s2", "skip", "Non-critical step")
        
        decisions = memory.get_recent_decisions()
        assert len(decisions) == 2
        assert decisions[0].decision_type == "retry"
    
    def test_context_management(self):
        memory = RunMemory()
        memory.start_run("run-001", "plan-test", 5)
        
        memory.set_context("session_id", "sess-123")
        assert memory.get_context("session_id") == "sess-123"
        assert memory.get_context("missing", "default") == "default"


class TestCaseMemory:
    def test_add_and_get_case(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "cases.json"
            memory = CaseMemory(path)
            
            case = Case(
                case_id="case-001",
                case_type=CaseType.REPAIR_CASE,
                pattern={"action": "click", "error": "timeout"},
                success_count=5,
            )
            memory.add_case(case)
            
            retrieved = memory.get_case("case-001")
            assert retrieved is not None
            assert retrieved.success_count == 5
    
    def test_promote_from_evidence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "cases.json"
            memory = CaseMemory(path)
            
            case = memory.promote_from_evidence(
                action="click",
                error_type="timeout",
                repair_strategy="retry",
                success=True,
            )
            
            assert case is not None
            assert case.case_type == CaseType.REPAIR_CASE
            assert case.success_count == 1
    
    def test_find_similar(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "cases.json"
            memory = CaseMemory(path)
            
            case = Case(
                case_id="case-001",
                case_type=CaseType.REPAIR_CASE,
                pattern={"action": "click", "error_type": "timeout"},
                success_count=10,
            )
            memory.add_case(case)
            
            similar = memory.find_similar(
                {"action": "click", "error_type": "timeout"},
                min_confidence=0.0,
            )
            assert len(similar) == 1
    
    def test_confidence_calculation(self):
        case = Case(
            case_id="case-001",
            case_type=CaseType.REPAIR_CASE,
            pattern={},
            success_count=8,
            failure_count=2,
        )
        assert case.confidence == 0.8


class TestRuleMemory:
    def test_register_rule(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            (base_dir / "registry").mkdir()
            (base_dir / "registry" / "actions.yaml").write_text("test: data")
            
            memory = RuleMemory(base_dir)
            rule = memory.register_rule(
                "registry-actions",
                RuleType.REGISTRY,
                "registry/actions.yaml",
                "Action registry",
            )
            
            assert rule.current_version == "1.0.0"
            assert len(rule.versions) == 1
    
    def test_update_rule(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            (base_dir / "registry").mkdir()
            (base_dir / "registry" / "actions.yaml").write_text("test: data")
            
            memory = RuleMemory(base_dir)
            memory.register_rule("registry-actions", RuleType.REGISTRY, "registry/actions.yaml")
            
            new_version = memory.update_rule(
                "registry-actions",
                "Added new action",
                ["Added launch_app action"],
                bump="minor",
            )
            
            assert new_version == "1.1.0"
    
    def test_rollback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            (base_dir / "registry").mkdir()
            file_path = base_dir / "registry" / "actions.yaml"
            file_path.write_text("version: 1")
            
            memory = RuleMemory(base_dir)
            memory.register_rule("registry-actions", RuleType.REGISTRY, "registry/actions.yaml")
            
            # Update file and version
            file_path.write_text("version: 2")
            memory.update_rule("registry-actions", "Update", ["Changed version"])
            
            # Rollback
            success = memory.rollback("registry-actions", "1.0.0")
            assert success
            assert file_path.read_text() == "version: 1"


class TestEvolutionEngine:
    def test_get_evolution_stats(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = EvolutionEngine(Path(tmpdir))
            stats = engine.get_evolution_stats()
            
            assert "total_cases" in stats
            assert "repair_cases" in stats
            assert "registered_rules" in stats
    
    def test_get_repair_hint(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = EvolutionEngine(Path(tmpdir))
            
            # Add a repair case
            engine.case_memory.promote_from_evidence(
                action="click",
                error_type="timeout",
                repair_strategy="retry",
                success=True,
            )
            # Increase confidence
            case = list(engine.case_memory._cases.values())[0]
            case.success_count = 10
            
            hint = engine.get_repair_hint("click", "timeout")
            assert hint == "retry"
