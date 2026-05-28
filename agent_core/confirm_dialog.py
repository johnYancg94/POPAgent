"""
Confirmation dialog for skill execution.

Used by executor.py when a skill's metadata.requires_confirmation is "first" or "always".

Architecture:
- Async caller awaits ask_confirmation(skill, args) -> {"approved": bool, "trust_session": bool}
- Internally schedules a modal-popup Operator on the main thread via run_on_main.
- The operator writes the user's choice into a concurrent.futures.Future.

Trust list (session-scoped, in-memory only):
- skill names the user has trusted "for this session".
- Cleared on POPAgent register/unregister (no persistence).
"""

from __future__ import annotations
import asyncio
import bpy
import concurrent.futures
import json
from bpy.props import BoolProperty, StringProperty

from .main_thread import run_on_main
from . import skill_registry


_session_trust: set[str] = set()
_pending_future: concurrent.futures.Future | None = None
_pending_payload: dict | None = None


def _format_args(args: dict, max_len: int = 200) -> str:
    try:
        s = json.dumps(args, ensure_ascii=False)
    except (TypeError, ValueError):
        s = str(args)
    if len(s) > max_len:
        s = s[:max_len] + "..."
    return s


def _build_risk_lines(skill: dict, args: dict) -> list[str]:
    """Human-readable risk summary for the confirmation popup."""
    meta = skill.get("metadata", {})
    lines: list[str] = []
    if meta.get("writes_files"):
        path = args.get("path") or args.get("output_path") or args.get("filepath") or "(参数中)"
        lines.append(f"写文件: {path}")
    if meta.get("launches_external_process"):
        cmd = args.get("command") or args.get("cmd") or "(参数中)"
        lines.append(f"启动进程: {cmd}")
    if meta.get("modifies_scene"):
        if meta.get("undoable"):
            lines.append("修改场景 (可 Ctrl+Z 撤销)")
        else:
            lines.append("修改场景 (不可撤销)")
    if not lines:
        lines.append("只读操作")
    return lines


class POPAGENT_OT_confirm_skill(bpy.types.Operator):
    """Modal confirmation dialog for skill execution."""

    bl_idname = "popagent.confirm_skill"
    bl_label = "POPAgent 需要确认"
    bl_options = {"INTERNAL"}

    skill_name: StringProperty(default="")
    skill_description: StringProperty(default="")
    args_summary: StringProperty(default="")
    risk_summary: StringProperty(default="")
    confirmation_level: StringProperty(default="first")  # "first" | "always"

    trust_session: BoolProperty(
        name="本会话信任此技能",
        description="勾选后本会话内此技能不再弹窗（仅 first 级别有效）",
        default=False,
    )

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=460)

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)

        title_row = col.row()
        title_row.alert = True
        title_row.label(text=f"将要执行: {self.skill_name}", icon="QUESTION")

        if self.skill_description:
            desc_box = col.box()
            for line in self.skill_description.split("\n"):
                desc_box.label(text=line[:80])

        col.separator()
        col.label(text="风险:", icon="ERROR")
        for line in self.risk_summary.split("\n"):
            if line.strip():
                col.label(text="  " + line)

        col.separator()
        col.label(text="参数:", icon="PROPERTIES")
        args_box = col.box()
        for chunk in _wrap_text(self.args_summary, 70):
            args_box.label(text=chunk)

        if self.confirmation_level == "first":
            col.separator()
            col.prop(self, "trust_session")

    def execute(self, context):
        _resolve(approved=True, trust_session=bool(self.trust_session))
        return {"FINISHED"}

    def cancel(self, context):
        _resolve(approved=False, trust_session=False)
        return {"CANCELLED"}


def _wrap_text(s: str, width: int) -> list[str]:
    if not s:
        return [""]
    return [s[i:i + width] for i in range(0, len(s), width)]


def _resolve(approved: bool, trust_session: bool) -> None:
    """Called from the operator's execute/cancel to resolve the pending Future."""
    global _pending_future, _pending_payload
    if _pending_future is None:
        return
    if approved and trust_session and _pending_payload is not None:
        _session_trust.add(_pending_payload["skill_name"])
    _pending_future.set_result({
        "approved": approved,
        "trust_session": trust_session,
    })
    _pending_future = None
    _pending_payload = None


def _invoke_popup_main_thread(skill: dict, args: dict) -> None:
    """Invoked on main thread via run_on_main; opens the confirmation operator."""
    risk = "\n".join(_build_risk_lines(skill, args))
    level = skill_registry.get_permission_level(skill, prefs=_current_preferences())
    bpy.ops.popagent.confirm_skill(
        "INVOKE_DEFAULT",
        skill_name=skill.get("name", "?"),
        skill_description=skill.get("description", "")[:240],
        args_summary=_format_args(args),
        risk_summary=risk,
        confirmation_level=level,
    )


def _current_preferences():
    try:
        from .. import __package__ as base_package

        return bpy.context.preferences.addons[base_package].preferences
    except Exception:
        return None


async def ask_confirmation(skill: dict, args: dict) -> dict:
    """Ask the user to approve a skill call. Returns {"approved": bool, "trust_session": bool}.

    Auto-approves when requires_confirmation="never" or the skill is in the session trust list
    (only honored for "first"-level skills; "always" never auto-approves).
    """
    global _pending_future, _pending_payload

    level = skill_registry.get_permission_level(skill, prefs=_current_preferences())

    if level == "never":
        return {"approved": True, "trust_session": False}

    if level == "first" and skill["name"] in _session_trust:
        return {"approved": True, "trust_session": True}

    fut: concurrent.futures.Future = concurrent.futures.Future()
    _pending_future = fut
    _pending_payload = {"skill_name": skill["name"]}

    run_on_main(_invoke_popup_main_thread, skill, args)

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: fut.result(timeout=300))


def clear_session_trust() -> None:
    """Reset the trust list (called on addon register/unregister)."""
    _session_trust.clear()


def session_trust_list() -> list[str]:
    return sorted(_session_trust)
