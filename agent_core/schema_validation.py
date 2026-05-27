"""Small JSON Schema subset used to validate skill arguments before dispatch."""

from __future__ import annotations

from typing import Any


_TYPE_NAMES = {
    "array": list,
    "boolean": bool,
    "integer": int,
    "number": (int, float),
    "object": dict,
    "string": str,
}


def _json_type(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    if value is None:
        return "null"
    return type(value).__name__


def validate_arguments(arguments: dict, schema: dict | None) -> str | None:
    """Return a human-readable validation error, or None when valid.

    This intentionally supports only the subset Blender skills currently use:
    object schemas, required fields, property type checks, and enum values.
    """
    if not isinstance(arguments, dict):
        return "Tool arguments must be an object"
    if not isinstance(schema, dict):
        return None

    if schema.get("type", "object") != "object":
        return None

    properties = schema.get("properties") or {}
    required = schema.get("required") or []

    for name in required:
        if name not in arguments:
            return f"Missing required argument: {name}"

    for name, value in arguments.items():
        prop_schema = properties.get(name)
        if not isinstance(prop_schema, dict):
            continue

        expected_type = prop_schema.get("type")
        if isinstance(expected_type, list):
            allowed_types = expected_type
        elif expected_type:
            allowed_types = [expected_type]
        else:
            allowed_types = []

        if allowed_types and not _matches_any_type(value, allowed_types):
            expected = " or ".join(allowed_types)
            return (
                f"Argument '{name}' must be {expected}, "
                f"got {_json_type(value)}"
            )

        if "enum" in prop_schema and value not in prop_schema["enum"]:
            allowed = ", ".join(str(v) for v in prop_schema["enum"])
            return f"Argument '{name}' must be one of: {allowed}"

    return None


def _matches_any_type(value: Any, allowed_types: list[str]) -> bool:
    for type_name in allowed_types:
        if type_name == "number":
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return True
            continue
        if type_name == "integer":
            if isinstance(value, int) and not isinstance(value, bool):
                return True
            continue
        py_type = _TYPE_NAMES.get(type_name)
        if py_type is not None and isinstance(value, py_type):
            return True
        if type_name == "null" and value is None:
            return True
    return False
