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
import functools
import time
from typing import Any

from .skill_registry import get_skill_by_name, is_handler_valid
from .main_thread import run_on_main
from .confirm_dialog import ask_confirmation
from .schema_validation import validate_arguments
from .progress import AgentProgressEvent
from ..providers.base import ToolCallRaw


_RESULT_OK = "ok"
_RESULT_ERR = "error"

# Default grace window for a skill handler running on the main thread. Skills
# whose metadata sets long_running=True get a much larger window, because a
# bake / heavy modifier apply legitimately takes longer — and timing it out
# would not stop the work anyway (see _make_error "still_running" below).
_DEFAULT_HANDLER_TIMEOUT = 30.0
_LONG_RUNNING_HANDLER_TIMEOUT = 600.0
_UNDO_PUSH_TIMEOUT = 5.0
_SNAPSHOT_TIMEOUT = 5.0


def _handler_timeout(meta: dict) -> float:
    # awaits_user: 等用户输入（ask_human）；long_running: 算得久（烘焙等）。
    # 语义不同但都需要放宽到长超时窗口，否则 30s 默认会误判 still_running。
    if meta.get("awaits_user") or meta.get("long_running"):
        return _LONG_RUNNING_HANDLER_TIMEOUT
    return _DEFAULT_HANDLER_TIMEOUT


def _make_error(kind: str, message: str) -> dict:
    return {"ok": False, "error_kind": kind, "error": message}


def _make_ok(result: Any) -> dict:
    if isinstance(result, dict):
        result.setdefault("ok", True)
        return result
    return {"ok": True, "result": result}


def _snapshot_addon_preferences(context, fields: list[str]) -> dict:
    addons = getattr(getattr(context, "preferences", None), "addons", None)
    if addons is None:
        return {}

    prefs = None
    for key in ("POPAgent",):
        try:
            prefs = addons[key].preferences
            break
        except Exception:
            pass
    if prefs is None:
        try:
            iterable = addons.values()
        except Exception:
            iterable = addons
        for addon in iterable:
            candidate = getattr(addon, "preferences", None)
            if candidate is not None:
                prefs = candidate
                break
    if prefs is None:
        return {}
    return {field: getattr(prefs, field, "") for field in fields}


async def _background_context(context, meta: dict) -> Any:
    if meta.get("background_context") != "addon_preferences":
        return context
    fields = list(meta.get("background_prefs_fields") or [])
    future = run_on_main(_snapshot_addon_preferences, context, fields)
    return await asyncio.wait_for(asyncio.wrap_future(future), timeout=_SNAPSHOT_TIMEOUT)


async def run(call: ToolCallRaw, context, progress=None) -> dict:
    """Execute one tool call; always returns a dict, never raises."""

    skill = get_skill_by_name(call.name)
    if skill is None:
        return _make_error("skill_not_found", f"No skill registered: {call.name}")

    if not is_handler_valid(skill):
        return _make_error("handler_stale",
                           f"Skill '{call.name}' handler is stale — reload the addon.")

    meta: dict = skill.get("metadata", {})
    handler = skill["handler"]
    validation_error = validate_arguments(call.arguments, skill.get("parameters"))
    if validation_error:
        return _make_error("invalid_arguments", validation_error)

    # Phase 3: open modal popup when metadata requires.
    # never -> no popup; first -> popup once per session unless trusted; always -> every call.
    decision = await ask_confirmation(skill, call.arguments)
    if not decision.get("approved"):
        return _make_error("user_denied", f"用户取消了 '{call.name}' 的执行。")

    if progress is not None:
        progress(AgentProgressEvent(kind="tool_call_start", tool_name=call.name))
    started_at = time.perf_counter()

    # Dispatch to main thread by default; only explicitly reviewed pure-Python
    # skills may run on the background executor.
    try:
        if meta.get("requires_main_thread", True):
            future = run_on_main(handler, context=context, **call.arguments)
            # run_on_main returns a concurrent.futures.Future; wrap for asyncio so
            # awaiting it does not occupy a thread-pool worker (important when many
            # read-only skills run concurrently via asyncio.gather).
            result = await asyncio.wait_for(
                asyncio.wrap_future(future), timeout=_handler_timeout(meta)
            )
        else:
            loop = asyncio.get_running_loop()
            handler_context = await _background_context(context, meta)
            bound = functools.partial(handler, context=handler_context, **call.arguments)
            result = await asyncio.wait_for(
                loop.run_in_executor(None, bound), timeout=_handler_timeout(meta)
            )
    except (asyncio.TimeoutError, TimeoutError):
        if progress is not None:
            progress(AgentProgressEvent(kind="tool_call_error", tool_name=call.name))
        # The grace window elapsed. Critically, the handler is STILL executing on
        # the main thread — the timeout only abandons our wait, it does not cancel
        # the work. Report honestly so the agent does not believe the call failed
        # or that the scene is unchanged.
        return _make_error(
            "still_running",
            f"'{call.name}' 仍在 Blender 主线程执行，未被中止（可能是大场景重算或耗时操作）。"
            "请等待 Blender 恢复响应后，再次查询当前状态确认结果，不要假定它失败或未生效。",
        )
    except Exception as exc:
        if progress is not None:
            progress(AgentProgressEvent(kind="tool_call_error", tool_name=call.name))
        return _make_error("handler_exception", str(exc))

    ok_result = _make_ok(result)
    if progress is not None:
        progress(
            AgentProgressEvent(
                kind="tool_call_finish" if ok_result.get("ok") else "tool_call_error",
                tool_name=call.name,
                duration_ms=(time.perf_counter() - started_at) * 1000,
            )
        )

    # Push undo step after successful execution (main thread).
    if ok_result.get("ok") and meta.get("undoable"):
        try:
            undo_future = run_on_main(_push_undo, call.name)
            await asyncio.wait_for(
                asyncio.wrap_future(undo_future), timeout=_UNDO_PUSH_TIMEOUT
            )
        except Exception:
            pass  # undo_push failure is non-fatal

    return ok_result


def _push_undo(name: str, **_) -> None:
    import bpy
    bpy.ops.ed.undo_push(message=f"POPAgent: {name}")
