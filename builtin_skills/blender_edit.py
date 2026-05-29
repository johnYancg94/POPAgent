"""
Undo / redo trigger skills.

Many write skills declare metadata.undoable=True, which makes the executor push
an undo step after they succeed (executor.py). But nothing let the agent actually
*trigger* an undo. These two skills close that gap so the model can roll back its
own mistake instead of asking the user to press Ctrl+Z.

Critical: these skills set undoable=False. If they were undoable=True the executor
would push a fresh undo step right after undoing, corrupting the undo stack.

bpy.ops.ed.undo/redo need a valid window context. When invoked from the agent
timer there may be no active screen, so we locate a window and use temp_override.
"""

from __future__ import annotations
import bpy


def _window_override():
    wm = bpy.context.window_manager
    for window in getattr(wm, "windows", []):
        screen = window.screen
        if screen is None:
            continue
        for area in screen.areas:
            if area.type == "VIEW_3D":
                return {"window": window, "screen": screen, "area": area}
        return {"window": window, "screen": screen}
    return None


def _run_history_op(op, label: str) -> dict:
    override = _window_override()
    if override is None:
        return {
            "ok": False,
            "error_kind": "undo_unavailable",
            "error": f"No window context available to {label}.",
        }
    try:
        with bpy.context.temp_override(**override):
            op()
    except RuntimeError as exc:
        return {"ok": False, "error_kind": "nothing_to_change", "error": str(exc)}
    except Exception as exc:
        return {"ok": False, "error_kind": "history_failed", "error": str(exc)}
    return {"ok": True, "action": label}


def _handler_undo(context=None) -> dict:
    del context
    return _run_history_op(bpy.ops.ed.undo, "undo")


def _handler_redo(context=None) -> dict:
    del context
    return _run_history_op(bpy.ops.ed.redo, "redo")


_HISTORY_METADATA = {
    "modifies_scene": True,
    "writes_files": False,
    "launches_external_process": False,
    "undoable": False,
    "requires_confirmation": "never",
}


UNDO = {
    "name": "blender.edit.undo",
    "description": (
        "Undo the most recent change in Blender's global undo history. Use this to "
        "roll back a skill call that produced the wrong result."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
    "owner": "builtin.edit",
    "handler": _handler_undo,
    "metadata": _HISTORY_METADATA,
}


REDO = {
    "name": "blender.edit.redo",
    "description": "Redo the change most recently undone via Blender's undo history.",
    "parameters": {"type": "object", "properties": {}, "required": []},
    "owner": "builtin.edit",
    "handler": _handler_redo,
    "metadata": _HISTORY_METADATA,
}
