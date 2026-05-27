"""
Read-only Blender query skills.
All handlers run on main thread via executor; metadata modifies_scene=False.
"""

from __future__ import annotations
import bpy
import json
import base64
import tempfile
import os


def _handler_query_scene(context=None, detail: str = "summary",
                         filter: str = "") -> dict:
    """Return a scene summary (or filtered detail) as a dict."""
    if context is None:
        context = bpy.context

    active = context.active_object
    selected = context.selected_objects

    result = {
        "ok": True,
        "mode": context.mode,
        "active": f"{active.name} ({active.type})" if active else None,
        "selected_count": len(selected),
        "selected": [f"{o.name} ({o.type})" for o in selected],
        "collections": [c.name for c in bpy.data.collections],
        "total_objects": len(bpy.data.objects),
    }

    if detail == "full":
        objects_info = []
        for obj in (context.selected_objects if filter == "selected"
                    else bpy.data.objects):
            objects_info.append({
                "name": obj.name,
                "type": obj.type,
                "location": list(obj.location),
                "visible": not obj.hide_viewport,
            })
        result["objects"] = objects_info

    return result


def _handler_list_addons(context=None) -> dict:
    """Return list of enabled addon module names."""
    import sys
    modules = []
    for addon in bpy.context.preferences.addons:
        key = addon.module
        mod = sys.modules.get(key)
        bl_info = getattr(mod, "bl_info", {}) if mod else {}
        modules.append({
            "module": key,
            "name": bl_info.get("name", key),
        })
    return {"ok": True, "addons": [m["module"] for m in modules], "count": len(modules)}


def _handler_viewport_screenshot(context=None) -> dict:
    """Capture 3D viewport as base64 PNG (stored in temp file, not disk-permanent)."""
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp.close()
    path = tmp.name

    try:
        bpy.ops.screen.screenshot(filepath=path)
        with open(path, "rb") as f:
            data = base64.b64encode(f.read()).decode("utf-8")
        return {"ok": True, "image_base64": data, "format": "png"}
    except Exception as exc:
        return {"ok": False, "error_kind": "screenshot_failed", "error": str(exc)}
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


QUERY_SCENE = {
    "name": "blender.query_scene",
    "description": (
        "Return a summary of the current Blender scene: active object, "
        "selection, mode, collections, and optional full object list."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "detail": {
                "type": "string",
                "enum": ["summary", "full"],
                "description": "summary = compact overview; full = per-object detail list",
            },
            "filter": {
                "type": "string",
                "enum": ["all", "selected"],
                "description": "When detail=full, which objects to include",
            },
        },
        "required": [],
    },
    "owner": "builtin",
    "handler": _handler_query_scene,
    "metadata": {
        "modifies_scene": False,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": False,
        "requires_confirmation": "never",
    },
}

LIST_ADDONS = {
    "name": "blender.list_addons",
    "description": "Return the list of currently enabled Blender addon module names.",
    "parameters": {"type": "object", "properties": {}, "required": []},
    "owner": "builtin",
    "handler": _handler_list_addons,
    "metadata": {
        "modifies_scene": False,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": False,
        "requires_confirmation": "never",
    },
}

VIEWPORT_SCREENSHOT = {
    "name": "blender.viewport_screenshot",
    "description": (
        "Capture the current 3D viewport and return it as a base64-encoded PNG string."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
    "owner": "builtin",
    "handler": _handler_viewport_screenshot,
    "metadata": {
        "modifies_scene": False,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": False,
        "requires_confirmation": "never",
    },
}
