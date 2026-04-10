"""Unit tests for test case asset schema."""

from src.schema.validator import SchemaValidator


def test_minimal_test_case_schema_accepts_basic_case():
    """Test minimal case document validates against the case schema."""
    case = {
        "id": "case-open-edge",
        "title": "Open Edge",
        "goal": "Open Edge",
        "tags": ["smoke", "edge"],
        "apps": ["Microsoft Edge"],
    }

    ok, errors = SchemaValidator().validate_document(case, "test-case")

    assert ok is True, errors
