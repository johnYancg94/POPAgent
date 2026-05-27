"""Pure Python tests for skill argument validation."""

from pathlib import Path
import importlib.util
import sys


ROOT = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location(
    "schema_validation", ROOT / "agent_core" / "schema_validation.py"
)
schema_validation = importlib.util.module_from_spec(spec)
sys.modules["schema_validation"] = schema_validation
spec.loader.exec_module(schema_validation)


validate_arguments = schema_validation.validate_arguments


def test_accepts_arguments_matching_required_types():
    schema = {
        "type": "object",
        "required": ["name", "count"],
        "properties": {
            "name": {"type": "string"},
            "count": {"type": "integer"},
            "enabled": {"type": "boolean"},
        },
    }

    error = validate_arguments(
        {"name": "Cube", "count": 2, "enabled": False},
        schema,
    )

    assert error is None


def test_rejects_missing_required_argument_with_structured_message():
    schema = {
        "type": "object",
        "required": ["name"],
        "properties": {"name": {"type": "string"}},
    }

    error = validate_arguments({}, schema)

    assert error == "Missing required argument: name"


def test_rejects_wrong_argument_type_with_structured_message():
    schema = {
        "type": "object",
        "properties": {"count": {"type": "integer"}},
    }

    error = validate_arguments({"count": "2"}, schema)

    assert error == "Argument 'count' must be integer, got string"


def run():
    test_accepts_arguments_matching_required_types()
    test_rejects_missing_required_argument_with_structured_message()
    test_rejects_wrong_argument_type_with_structured_message()
    print("test_skill_argument_validation OK")
    return True


if __name__ == "__main__":
    run()
