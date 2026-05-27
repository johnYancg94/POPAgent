"""
Skill executor: metadata-gated dispatch to main thread.

Flow:
  run(call, context) -> dict
    1. look up skill in registry
    2. validate handler module still live
    3. check requires_confirmation (Phase 3 will hook UI here; Phase 1 auto-approves)
    4. dispatch handler via run_on_main, await Future
    5. if undoable=True, push undo step after success
    6. any exception -> structured error dict (never re-raised)
"""

from __future__ import annotations
import asyncio
import json
from typing import Any

from .skill_registry import get_skill_by_name, is_handler_valid
from .main_thread import run_on_main
from .confirm_dialog import ask_confirmation
from ..providers.base import ToolCallRaw


_RESULT_OK = "ok"
_RESULT_ERR = "error"


def _make_error(kind: str, message: str) -> dict:
    return {"ok": False, "error_kind": kind, "error": message}


def _make_ok(result: Any) -> dict:
    if isinstance(result, dict):
        result.setdefault("ok", True)
        return result
    return {"ok": True, "result": result}


async def run(call: ToolCallRaw, context) -> dict:
    """Execute one tool call; always returns a dict, never raises."""

    skill = get_skill_by_name(call.name)
    if skill is None:
        return _make_error("skill_not_found", f"No skill registered: {call.name}")

    if not is_handler_valid(skill):
        return _make_error("handler_stale",
                           f"Skill '{call.name}' handler is stale — reload the addon.")

    meta: dict = skill.get("metadata", {})
    handler = skill["handler"]

    # Phase 3: open modal popup when metadata requires.
    # never -> no popup; first -> popup once per session unless trusted; always -> every call.
    decision = await ask_confirmation(skill, call.arguments)
    if not decision.get("approved"):
        return _make_error("user_denied", f"用户取消了 '{call.name}' 的执行。")

    # Dispatch to main thread and await result.
    loop = asyncio.get_event_loop()
    try:
        future = run_on_main(handler, context=context, **call.arguments)
        # run_on_main returns a concurrent.futures.Future; wrap for asyncio
        result = await loop.run_in_executor(None, lambda: future.result(timeout=30))
    except TimeoutError:
        return _make_error("timeout", f"Skill '{call.name}' timed out (30s).")
    except Exception as exc:
        return _make_error("handler_exception", str(exc))

    ok_result = _make_ok(result)

    # Push undo step after successful execution (main thread).
    if ok_result.get("ok") and meta.get("undoable"):
        try:
            undo_future = run_on_main(_push_undo, call.name)
            await loop.run_in_executor(None, lambda: undo_future.result(timeout=5))
        except Exception:
            pass  # undo_push failure is non-fatal

    return ok_result


def _push_undo(name: str, **_) -> None:
    import bpy
    bpy.ops.ed.undo_push(message=f"POPAgent: {name}")
