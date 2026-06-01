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


def _diagnose_hint(exc: Exception) -> str:
    """Map a raised exception to a recovery hint that steers the agent away
    from re-submitting the same failing code."""
    name = type(exc).__name__
    if name == "AttributeError":
        return (
            "很可能是 Blender API 的属性/方法名写错，或该名称在当前版本不存在。"
            "不要原样重跑同一段代码——先调用 blender.api_search 确认本版本下正确的"
            "属性/方法名，再据此改写。"
        )
    if name == "NameError":
        return (
            "用到了未定义的变量或未 import 的名字。检查拼写、补上 import，"
            "不要重复提交同一段代码。"
        )
    if name in ("TypeError", "ValueError"):
        return (
            "参数类型或取值不对。不要原样重投同一段代码；检查传入参数，"
            "必要时用 blender.api_search 查正确的签名。"
        )
    return ""


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
        captured = stdout_capture.getvalue()
        err = {"ok": False, "error_kind": "exec_error", "error": tb}
        if captured:
            err["output"] = captured
        hint = _diagnose_hint(exc)
        if hint:
            err["hint"] = hint
        return err
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
