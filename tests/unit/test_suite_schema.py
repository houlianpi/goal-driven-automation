"""Unit tests for test suite asset schema."""

from src.schema.validator import SchemaValidator


def test_minimal_test_suite_schema_accepts_case_references():
    """Test minimal suite document validates against the suite schema."""
    suite = {
        "id": "suite-smoke-core",
        "title": "Core smoke",
        "cases": ["case-open-edge"],
    }

    ok, errors = SchemaValidator().validate_document(suite, "test-suite")

    assert ok is True, errors
