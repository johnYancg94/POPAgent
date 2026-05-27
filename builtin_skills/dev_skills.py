# -*- coding: utf-8 -*-
"""
Developer skill: execute arbitrary Python code in Blender's main thread.

Registered by default as a built-in POPAgent skill.
The agent loop's normal metadata gates still apply; this skill sets
requires_confirmation="always" so the executor logs a warning on every call.
"""

from __future__ import annotations
import bpy
import traceback


def _handler_run_python(context=None, code: str = "") -> dict:
    """Execute a Python code string in Blender's main thread.

    Returns stdout-equivalent output captured from exec() via a StringIO trick,
    plus any exception message on failure.
    """
    if context is None:
        context = bpy.context

    if not code.strip():
        return {"ok": False, "error_kind": "empty_code", "error": "No code provided."}

    import io
    import sys

    stdout_capture = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = stdout_capture

    exec_globals = {"bpy": bpy, "context": context}
    try:
        exec(compile(code, "<popagent_dev>", "exec"), exec_globals)
        output = stdout_capture.getvalue()
        return {"ok": True, "output": output}
    except Exception as exc:
        tb = traceback.format_exc()
        return {"ok": False, "error_kind": "exec_error", "error": tb}
    finally:
        sys.stdout = old_stdout


RUN_PYTHON = {
    "name": "dev.run_python",
    "description": (
        "Execute arbitrary Python code in Blender's main thread. "
        "Use with extreme caution — code runs with full Blender API access. "
        "Returns captured stdout output and any exception tracebacks."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python source code to execute. May use 'import bpy', 'context', etc.",
            },
        },
        "required": ["code"],
    },
    "owner": "builtin.dev",
    "handler": _handler_run_python,
    "metadata": {
        "modifies_scene": True,
        "writes_files": True,
        "launches_external_process": False,
        "undoable": False,
        "requires_confirmation": "always",
    },
}
