"""
Write-class Blender skills that modify scene state (undoable).
"""

from __future__ import annotations
import bpy
import fnmatch


def _handler_select_objects(context=None, names: list[str] | None = None,
                             pattern: str = "", mode: str = "SET") -> dict:
    """Select objects by explicit name list or glob pattern.

    mode: SET (replace), ADD (add to), SUBTRACT (remove from).
    """
    if context is None:
        context = bpy.context

    if mode not in ("SET", "ADD", "SUBTRACT"):
        mode = "SET"

    if mode == "SET":
        bpy.ops.object.select_all(action="DESELECT")

    matched = []
    all_objs = bpy.data.objects

    if names:
        for name in names:
            obj = all_objs.get(name)
            if obj:
                if mode == "SUBTRACT":
                    obj.select_set(False)
                else:
                    obj.select_set(True)
                matched.append(name)

    if pattern:
        for obj in all_objs:
            if fnmatch.fnmatch(obj.name, pattern):
                if mode == "SUBTRACT":
                    obj.select_set(False)
                else:
                    obj.select_set(True)
                if obj.name not in matched:
                    matched.append(obj.name)

    return {
        "selected": matched,
        "count": len(matched),
    }


def _handler_set_active(context=None, name: str = "") -> dict:
    """Set the active object by name."""
    if context is None:
        context = bpy.context

    obj = bpy.data.objects.get(name)
    if obj is None:
        return {"ok": False, "error_kind": "not_found",
                "error": f"Object '{name}' not found."}

    context.view_layer.objects.active = obj
    if not obj.select_get():
        obj.select_set(True)

    return {"active": obj.name, "type": obj.type}


SELECT_OBJECTS = {
    "name": "blender.select_objects",
    "description": (
        "Select Blender objects by an explicit name list or a glob pattern (e.g. 'Cube*'). "
        "mode=SET replaces the selection, ADD extends it, SUBTRACT removes matched objects."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "names": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Exact object names to select",
            },
            "pattern": {
                "type": "string",
                "description": "Glob pattern, e.g. 'mesh_*' or 'LOD_*'",
            },
            "mode": {
                "type": "string",
                "enum": ["SET", "ADD", "SUBTRACT"],
                "description": "How to combine with current selection",
            },
        },
        "required": [],
    },
    "owner": "builtin",
    "handler": _handler_select_objects,
    "metadata": {
        "modifies_scene": True,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": True,
        "requires_confirmation": "never",
    },
}

SET_ACTIVE = {
    "name": "blender.set_active",
    "description": "Set the active object by name (also selects it if not already selected).",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Exact name of the object to make active",
            },
        },
        "required": ["name"],
    },
    "owner": "builtin",
    "handler": _handler_set_active,
    "metadata": {
        "modifies_scene": True,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": True,
        "requires_confirmation": "never",
    },
}
