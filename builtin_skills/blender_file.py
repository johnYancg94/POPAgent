"""
Blender file lifecycle skill: save / save-as / incremental save.

Closes the loop for an agent that edits the scene but otherwise cannot persist
the .blend. Runs on the main thread (dispatched by the executor), so it calls
bpy.ops.wm directly.

Confirmation is "always": saving overwrites a file on disk and is not undoable.
The 'filepath' parameter name is deliberate — confirm_dialog reads it to show
the destination path in the risk popup.
"""

from __future__ import annotations
import bpy

from ..agent_core.file_versioning import next_incremental_path, ensure_blend_extension


def _handler_save(context=None, filepath: str = "", incremental: bool = False) -> dict:
    """Save the current .blend.

    No args        -> save in place (errors if the file was never saved).
    filepath       -> save as that path (.blend appended if no extension).
    incremental    -> save to an auto-incremented _NNN path next to the current file.
    """
    del context
    current = bpy.data.filepath

    if incremental:
        if not current:
            return {
                "ok": False,
                "error_kind": "never_saved",
                "error": "File has never been saved; cannot increment. Provide a filepath first.",
            }
        target = next_incremental_path(current)
    elif filepath:
        target = ensure_blend_extension(filepath)
    else:
        if not current:
            return {
                "ok": False,
                "error_kind": "never_saved",
                "error": "File has never been saved; provide a filepath to save as.",
            }
        target = current

    try:
        bpy.ops.wm.save_as_mainfile(filepath=target)
    except Exception as exc:
        return {"ok": False, "error_kind": "save_failed", "error": str(exc)}

    return {
        "ok": True,
        "saved_path": bpy.data.filepath,
        "incremented": bool(incremental),
        "previous_path": current or None,
    }


SAVE_FILE = {
    "name": "blender.file.save",
    "description": (
        "Save the current Blender .blend file. With no arguments, saves in place "
        "(fails if the file was never saved). Pass 'filepath' to save to a specific "
        "path (save-as). Pass incremental=true to save a new auto-numbered version "
        "next to the current file (e.g. char_chef_001.blend -> char_chef_002.blend)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "filepath": {
                "type": "string",
                "description": "Absolute target path for save-as. '.blend' is appended if no extension.",
            },
            "incremental": {
                "type": "boolean",
                "description": "Save a new auto-incremented version next to the current file.",
            },
        },
        "required": [],
    },
    "owner": "builtin.file",
    "handler": _handler_save,
    "metadata": {
        "modifies_scene": False,
        "writes_files": True,
        "launches_external_process": False,
        "undoable": False,
        "requires_confirmation": "always",
    },
}
