"""Unit tests for Schema Validator."""
import pytest
import json
from pathlib import Path
from src.schema.validator import (
    SchemaValidator,
    SchemaValidationError,
    validate_plan,
    validate_evidence,
)


class TestSchemaValidator:
    """Test SchemaValidator class."""
    
    @pytest.fixture
    def validator(self):
        return SchemaValidator()
    
    def test_validate_valid_plan(self, validator):
        """Test validating a valid Plan IR."""
        plan = {
            "plan_id": "plan-test-001",
            "version": "1.0.0",
            "goal": "Test goal",
            "app": "Safari",
            "steps": [
                {
                    "step_id": "s1",
                    "action": "launch",
                    "params": {"app": "Safari"}
                }
            ]
        }
        is_valid, errors = validator.validate_plan(plan)
        assert is_valid is True
        assert len(errors) == 0
    
    def test_validate_plan_missing_required_fields(self, validator):
        """Test that missing required fields cause validation errors."""
        plan = {
            "plan_id": "plan-test-002",
            # Missing: version, goal, app, steps
        }
        is_valid, errors = validator.validate_plan(plan)
        assert is_valid is False
        assert len(errors) >= 4  # At least 4 missing fields
    
    def test_validate_plan_invalid_action(self, validator):
        """Test that invalid action type is rejected."""
        plan = {
            "plan_id": "plan-test-003",
            "version": "1.0.0",
            "goal": "Test",
            "app": "Safari",
            "steps": [
                {
                    "step_id": "s1",
                    "action": "invalid_action"  # Not in enum
                }
            ]
        }
        is_valid, errors = validator.validate_plan(plan)
        assert is_valid is False
        assert any("action" in e.lower() for e in errors)
    
    def test_validate_plan_invalid_id_pattern(self, validator):
        """Test that invalid plan_id pattern is rejected."""
        plan = {
            "plan_id": "INVALID_ID",  # Must match ^plan-[a-z0-9-]+$
            "version": "1.0.0",
            "goal": "Test",
            "app": "Safari",
            "steps": [{"step_id": "s1", "action": "launch"}]
        }
        is_valid, errors = validator.validate_plan(plan)
        assert is_valid is False
        assert any("plan_id" in e for e in errors)
    
    def test_validate_valid_evidence(self, validator):
        """Test validating valid Evidence."""
        evidence = {
            "evidence_id": "evidence-test-001",
            "plan_id": "plan-test-001",
            "run_id": "run-abc123",
            "status": "success",
            "steps": [
                {
                    "step_id": "s1",
                    "action": "launch",
                    "status": "success"
                }
            ]
        }
        is_valid, errors = validator.validate_evidence(evidence)
        assert is_valid is True
        assert len(errors) == 0
    
    def test_validate_evidence_invalid_status(self, validator):
        """Test that invalid status is rejected."""
        evidence = {
            "evidence_id": "evidence-test-002",
            "plan_id": "plan-test-001",
            "run_id": "run-abc123",
            "status": "unknown",  # Not in enum
            "steps": []
        }
        is_valid, errors = validator.validate_evidence(evidence)
        assert is_valid is False
        assert any("status" in e.lower() for e in errors)
    
    def test_validate_or_raise(self, validator):
        """Test validate_or_raise raises exception on invalid data."""
        invalid_plan = {"plan_id": "invalid"}
        with pytest.raises(SchemaValidationError) as exc_info:
            validator.validate_or_raise(invalid_plan, "plan-ir")
        assert len(exc_info.value.errors) > 0


class TestValidatePlanExamples:
    """Test validation of example plan files."""
    
    @pytest.fixture
    def validator(self):
        return SchemaValidator()
    
    def test_edge_new_tab_example(self, validator):
        """Test edge-new-tab.plan.json example."""
        path = Path(__file__).parent.parent.parent / "schemas" / "examples" / "edge-new-tab.plan.json"
        if path.exists():
            is_valid, errors = validator.validate_plan_file(path)
            assert is_valid is True, f"Errors: {errors}"
    
    def test_safari_navigate_example(self, validator):
        """Test safari-navigate.plan.json example."""
        path = Path(__file__).parent.parent.parent / "schemas" / "examples" / "safari-navigate.plan.json"
        if path.exists():
            is_valid, errors = validator.validate_plan_file(path)
            assert is_valid is True, f"Errors: {errors}"


class TestValidateEvidenceExamples:
    """Test validation of example evidence files."""
    
    @pytest.fixture
    def validator(self):
        return SchemaValidator()
    
    def test_success_evidence_example(self, validator):
        """Test success.evidence.json example."""
        path = Path(__file__).parent.parent.parent / "schemas" / "examples" / "success.evidence.json"
        if path.exists():
            is_valid, errors = validator.validate_evidence_file(path)
            assert is_valid is True, f"Errors: {errors}"
    
    def test_partial_repair_evidence_example(self, validator):
        """Test partial-with-repair.evidence.json example."""
        path = Path(__file__).parent.parent.parent / "schemas" / "examples" / "partial-with-repair.evidence.json"
        if path.exists():
            is_valid, errors = validator.validate_evidence_file(path)
            assert is_valid is True, f"Errors: {errors}"


class TestHelperFunctions:
    """Test module-level helper functions."""
    
    def test_validate_plan_function(self):
        """Test validate_plan helper."""
        plan = {
            "plan_id": "plan-test-func",
            "version": "1.0.0",
            "goal": "Test",
            "app": "Safari",
            "steps": [{"step_id": "s1", "action": "launch"}]
        }
        is_valid, errors = validate_plan(plan)
        assert is_valid is True
    
    def test_validate_evidence_function(self):
        """Test validate_evidence helper."""
        evidence = {
            "evidence_id": "evidence-test-func",
            "plan_id": "plan-test",
            "run_id": "run-123",
            "status": "success",
            "steps": []
        }
        is_valid, errors = validate_evidence(evidence)
        assert is_valid is True
