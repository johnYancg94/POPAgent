"""UI result registration skills for POPAgent answers."""

from __future__ import annotations

from ..utils.structured_results import object_results_to_json


def _handler_object_results(context=None, objects: list | None = None) -> dict:
    """Register object results that the Answer panel can render as controls."""
    object_results_json = object_results_to_json(objects or [])
    normalized_count = 0
    if object_results_json:
        import json

        normalized_count = len(json.loads(object_results_json).get("objects", []))
    return {
        "ok": True,
        "object_results_json": object_results_json,
        "count": normalized_count,
    }


OBJECT_RESULTS = {
    "name": "blender.object_results",
    "description": (
        "Register exact Blender object results for the POPAgent Answer panel. "
        "Call this after finding, listing, ranking, inspecting, or comparing objects "
        "so the UI can show clickable select-and-frame rows. This does not modify "
        "the scene and should only include exact object names observed from tool results."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "objects": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Exact object name"},
                        "object_name": {
                            "type": "string",
                            "description": (
                                "Exact Blender object name. Prefer this field when "
                                "mesh data names are also present."
                            ),
                        },
                        "mesh_data_name": {
                            "type": "string",
                            "description": (
                                "Mesh data datablock name, only as supporting identity "
                                "information; do not use it instead of object_name."
                            ),
                        },
                        "type": {"type": "string", "description": "Blender object type"},
                        "location": {
                            "type": "array",
                            "items": {"type": "number"},
                            "minItems": 3,
                            "maxItems": 3,
                            "description": "World location [x, y, z], when known",
                        },
                        "note": {
                            "type": "string",
                            "description": "Short reason or matched property",
                        },
                    },
                    "required": ["name"],
                },
                "description": "Objects to show in the Answer panel results area",
            },
        },
        "required": ["objects"],
    },
    "owner": "builtin",
    "handler": _handler_object_results,
    "metadata": {
        "modifies_scene": False,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": False,
        "requires_confirmation": "never",
    },
}
