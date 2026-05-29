"""
Transform write skills: move/rotate/scale, apply transforms, set origin.

Lets the agent go from "can select" to "can place". transform.set writes
obj.location/rotation_euler/scale directly (no operator, no viewport context
needed). transform.apply and transform.set_origin wrap bpy.ops with a
temp_override so they work from the agent timer.

All modify the scene and are undoable; the executor pushes the undo step.
"""

from __future__ import annotations
import bpy
import math


def _target_objects(context):
    objs = list(context.selected_objects)
    if not objs and context.active_object:
        objs = [context.active_object]
    return objs


def _as_vec3(value, label: str):
    if value is None:
        return None, None
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return None, f"'{label}' must be a 3-number array [x, y, z]."
    try:
        return [float(v) for v in value], None
    except (TypeError, ValueError):
        return None, f"'{label}' must contain numbers."


def _handler_set(
    context=None,
    location=None,
    rotation_euler=None,
    scale=None,
) -> dict:
    if context is None:
        context = bpy.context

    if location is None and rotation_euler is None and scale is None:
        return {
            "ok": False,
            "error_kind": "no_transform",
            "error": "Provide at least one of location, rotation_euler, scale.",
        }

    loc, err = _as_vec3(location, "location")
    if err:
        return {"ok": False, "error_kind": "invalid_arguments", "error": err}
    rot, err = _as_vec3(rotation_euler, "rotation_euler")
    if err:
        return {"ok": False, "error_kind": "invalid_arguments", "error": err}
    scl, err = _as_vec3(scale, "scale")
    if err:
        return {"ok": False, "error_kind": "invalid_arguments", "error": err}

    objs = _target_objects(context)
    if not objs:
        return {"ok": False, "error_kind": "no_selection", "error": "No objects selected or active."}

    updated = []
    for obj in objs:
        if loc is not None:
            obj.location = loc
        if rot is not None:
            obj.rotation_euler = [math.radians(d) for d in rot]
        if scl is not None:
            obj.scale = scl
        updated.append(obj.name)

    return {"ok": True, "updated": updated, "count": len(updated)}


def _override_with_objects(context, objs):
    override = {"selected_objects": objs, "active_object": objs[0], "object": objs[0]}
    for window in getattr(context.window_manager, "windows", []):
        if window.screen:
            override["window"] = window
            override["screen"] = window.screen
            for area in window.screen.areas:
                if area.type == "VIEW_3D":
                    override["area"] = area
                    break
            break
    return override


def _handler_apply(
    context=None,
    location: bool = False,
    rotation: bool = True,
    scale: bool = True,
) -> dict:
    if context is None:
        context = bpy.context
    objs = _target_objects(context)
    if not objs:
        return {"ok": False, "error_kind": "no_selection", "error": "No objects selected or active."}

    try:
        with bpy.context.temp_override(**_override_with_objects(context, objs)):
            bpy.ops.object.transform_apply(
                location=location, rotation=rotation, scale=scale
            )
    except Exception as exc:
        return {"ok": False, "error_kind": "apply_failed", "error": str(exc)}

    return {
        "ok": True,
        "applied": {"location": location, "rotation": rotation, "scale": scale},
        "objects": [o.name for o in objs],
    }


_ORIGIN_TYPES = {
    "GEOMETRY_ORIGIN",
    "ORIGIN_GEOMETRY",
    "ORIGIN_CURSOR",
    "ORIGIN_CENTER_OF_MASS",
    "ORIGIN_CENTER_OF_VOLUME",
}


def _handler_set_origin(context=None, type: str = "ORIGIN_GEOMETRY", center: str = "MEDIAN") -> dict:
    if context is None:
        context = bpy.context
    if type not in _ORIGIN_TYPES:
        return {
            "ok": False,
            "error_kind": "invalid_arguments",
            "error": f"Unsupported origin type: {type}",
        }
    objs = _target_objects(context)
    if not objs:
        return {"ok": False, "error_kind": "no_selection", "error": "No objects selected or active."}

    try:
        with bpy.context.temp_override(**_override_with_objects(context, objs)):
            bpy.ops.object.origin_set(type=type, center=center)
    except Exception as exc:
        return {"ok": False, "error_kind": "origin_set_failed", "error": str(exc)}

    return {"ok": True, "type": type, "center": center, "objects": [o.name for o in objs]}


_VEC3 = {
    "type": "array",
    "description": "Three numbers [x, y, z].",
}

TRANSFORM_SET = {
    "name": "blender.transform.set",
    "description": (
        "Set absolute transform on selected objects (falls back to active). "
        "location and scale are in world units; rotation_euler is in DEGREES (XYZ). "
        "Omit any field to leave it unchanged. Applies the same values to every "
        "selected object."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "location": _VEC3,
            "rotation_euler": {"type": "array", "description": "Euler rotation in DEGREES [x, y, z]."},
            "scale": _VEC3,
        },
        "required": [],
    },
    "owner": "builtin.transform",
    "handler": _handler_set,
    "metadata": {
        "modifies_scene": True,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": True,
        "requires_confirmation": "first",
    },
}

TRANSFORM_APPLY = {
    "name": "blender.transform.apply",
    "description": (
        "Apply (bake) object transforms into mesh data for selected objects. "
        "Defaults to applying rotation and scale (the common pre-export step) while "
        "leaving location. Set flags explicitly to change what is baked."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "location": {"type": "boolean", "description": "Apply location (default false)."},
            "rotation": {"type": "boolean", "description": "Apply rotation (default true)."},
            "scale": {"type": "boolean", "description": "Apply scale (default true)."},
        },
        "required": [],
    },
    "owner": "builtin.transform",
    "handler": _handler_apply,
    "metadata": {
        "modifies_scene": True,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": True,
        "requires_confirmation": "first",
    },
}

TRANSFORM_SET_ORIGIN = {
    "name": "blender.transform.set_origin",
    "description": (
        "Set the origin point of selected objects. type=ORIGIN_GEOMETRY moves the "
        "origin to the geometry center (default), ORIGIN_CURSOR to the 3D cursor, "
        "ORIGIN_CENTER_OF_MASS/VOLUME to computed centers."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "type": {
                "type": "string",
                "enum": [
                    "ORIGIN_GEOMETRY",
                    "ORIGIN_CURSOR",
                    "ORIGIN_CENTER_OF_MASS",
                    "ORIGIN_CENTER_OF_VOLUME",
                ],
                "description": "Origin placement mode.",
            },
            "center": {
                "type": "string",
                "enum": ["MEDIAN", "BOUNDS"],
                "description": "Center computation for ORIGIN_GEOMETRY.",
            },
        },
        "required": [],
    },
    "owner": "builtin.transform",
    "handler": _handler_set_origin,
    "metadata": {
        "modifies_scene": True,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": True,
        "requires_confirmation": "first",
    },
}
