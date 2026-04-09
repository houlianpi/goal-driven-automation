"""
Schema Validator - Validates Plan IR and Evidence against JSON Schema.
"""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import jsonschema
from jsonschema import Draft7Validator


class SchemaValidationError(Exception):
    """Raised when schema validation fails."""
    def __init__(self, errors: List[str]):
        self.errors = errors
        super().__init__(f"Validation failed with {len(errors)} error(s)")


class SchemaValidator:
    """Validates JSON data against schemas."""
    
    def __init__(self, schemas_dir: Optional[Path] = None):
        """Initialize validator with schemas directory."""
        if schemas_dir is None:
            schemas_dir = Path(__file__).parent.parent.parent / "schemas"
        self.schemas_dir = schemas_dir
        self._schemas: Dict[str, Dict] = {}
    
    def _load_schema(self, schema_name: str) -> Dict[str, Any]:
        """Load and cache a schema by name."""
        if schema_name not in self._schemas:
            schema_path = self.schemas_dir / f"{schema_name}.schema.json"
            if not schema_path.exists():
                raise FileNotFoundError(f"Schema not found: {schema_path}")
            with open(schema_path, "r") as f:
                self._schemas[schema_name] = json.load(f)
        return self._schemas[schema_name]
    
    def validate(self, data: Dict[str, Any], schema_name: str) -> Tuple[bool, List[str]]:
        """
        Validate data against a schema.
        
        Args:
            data: JSON data to validate
            schema_name: Schema name (without .schema.json extension)
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        schema = self._load_schema(schema_name)
        validator = Draft7Validator(schema)
        errors = []
        
        for error in sorted(validator.iter_errors(data), key=lambda e: e.path):
            path = ".".join(str(p) for p in error.path) or "(root)"
            errors.append(f"{path}: {error.message}")
        
        return len(errors) == 0, errors
    
    def validate_or_raise(self, data: Dict[str, Any], schema_name: str) -> None:
        """Validate data and raise exception if invalid."""
        is_valid, errors = self.validate(data, schema_name)
        if not is_valid:
            raise SchemaValidationError(errors)
    
    def validate_plan(self, plan: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate a Plan IR document."""
        return self.validate(plan, "plan-ir")
    
    def validate_evidence(self, evidence: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate an Evidence document."""
        return self.validate(evidence, "evidence")
    
    def validate_plan_file(self, path: Path) -> Tuple[bool, List[str]]:
        """Validate a Plan IR JSON file."""
        with open(path, "r") as f:
            data = json.load(f)
        return self.validate_plan(data)
    
    def validate_evidence_file(self, path: Path) -> Tuple[bool, List[str]]:
        """Validate an Evidence JSON file."""
        with open(path, "r") as f:
            data = json.load(f)
        return self.validate_evidence(data)


# Module-level convenience functions
def validate_plan(plan: Dict[str, Any], schemas_dir: Optional[str] = None) -> Tuple[bool, List[str]]:
    """Validate a Plan IR document."""
    path = Path(schemas_dir) if schemas_dir else None
    validator = SchemaValidator(path)
    return validator.validate_plan(plan)


def validate_evidence(evidence: Dict[str, Any], schemas_dir: Optional[str] = None) -> Tuple[bool, List[str]]:
    """Validate an Evidence document."""
    path = Path(schemas_dir) if schemas_dir else None
    validator = SchemaValidator(path)
    return validator.validate_evidence(evidence)


def validate_plan_file(path: str, schemas_dir: Optional[str] = None) -> Tuple[bool, List[str]]:
    """Validate a Plan IR JSON file."""
    schemas_path = Path(schemas_dir) if schemas_dir else None
    validator = SchemaValidator(schemas_path)
    return validator.validate_plan_file(Path(path))


def validate_evidence_file(path: str, schemas_dir: Optional[str] = None) -> Tuple[bool, List[str]]:
    """Validate an Evidence JSON file."""
    schemas_path = Path(schemas_dir) if schemas_dir else None
    validator = SchemaValidator(schemas_path)
    return validator.validate_evidence_file(Path(path))
