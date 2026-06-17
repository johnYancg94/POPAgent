"""ask_human 的模态对话框 + Future 桥接。

agent 调 agent.ask_human → handler（bg worker 线程）调 ask_user_blocking →
schedule 模态 operator 到主线程 → worker 阻塞等用户输入 resolve 独立 Future。

handler 必须跑在 bg worker（requires_main_thread=False），不能在主线程阻塞等
模态框——否则主线程自等死锁。
"""
from __future__ import annotations
import bpy
import concurrent.futures
import json
from bpy.props import StringProperty

from .main_thread import run_on_main

_pending_answer: concurrent.futures.Future | None = None


def _wrap_dialog_text(text: str, width: int = 60) -> list[str]:
    lines: list[str] = []
    for raw_line in (text or "").splitlines() or [""]:
        line = raw_line.strip()
        if not line:
            lines.append("")
            continue
        while len(line) > width:
            lines.append(line[:width])
            line = line[width:]
        lines.append(line)
    return lines


def _dialog_options(operator) -> list[str]:
    if operator.options_json:
        try:
            values = json.loads(operator.options_json)
        except (TypeError, ValueError):
            values = []
        if isinstance(values, list):
            return [str(value) for value in values if str(value).strip()]
    return [o for o in operator.options_csv.split("\n") if o.strip()]


class POPAGENT_OT_ask_human(bpy.types.Operator):
    """Modal dialog asking the user a clarifying question."""
    bl_idname = "popagent.ask_human"
    bl_label = "POPAgent 需要澄清"
    bl_options = {"INTERNAL"}

    question: StringProperty(default="")
    options_csv: StringProperty(default="")
    options_json: StringProperty(default="")
    answer: StringProperty(name="你的回答", default="")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=560)

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        for line in _wrap_dialog_text(self.question):
            col.label(text=line[:80])
        col.separator()
        options = _dialog_options(self)
        if options:
            col.label(text="可选回答（完整内容如下，点击按钮选择）:")
            for index, option in enumerate(options, start=1):
                box = col.box()
                box.label(text=f"选项 {index}:")
                for line in _wrap_dialog_text(option):
                    box.label(text=line)
                op = box.operator("popagent.ask_human_pick", text="选择此项")
                op.value = option
            col.separator()
            col.label(text="或自由输入（点击 OK 提交）:")
        col.prop(self, "answer")

    def execute(self, context):
        _resolve(self.answer)
        return {"FINISHED"}

    def cancel(self, context):
        _resolve("")


class POPAGENT_OT_ask_human_pick(bpy.types.Operator):
    """Submit one of the fully displayed options."""
    bl_idname = "popagent.ask_human_pick"
    bl_label = "选择此项"
    bl_options = {"INTERNAL"}
    value: StringProperty(default="")

    def execute(self, context):
        _resolve(self.value)
        return {"FINISHED"}


def _resolve(answer: str) -> None:
    global _pending_answer
    if _pending_answer is None:
        return
    _pending_answer.set_result(answer)
    _pending_answer = None


def _invoke_dialog_main_thread(question: str, options: list[str]) -> None:
    bpy.ops.popagent.ask_human(
        "INVOKE_DEFAULT",
        question=question[:1000],
        options_csv="\n".join(options or []),
        options_json=json.dumps(options or [], ensure_ascii=False),
    )

def ask_user_blocking(question: str, options: list[str] | None = None) -> dict:
    """Ask the user a clarifying question; block (bg worker) until answered.

    MUST be called from a thread-pool worker (requires_main_thread=False),
    never the main thread — blocking the main thread deadlocks the dialog.
    """
    global _pending_answer
    fut: concurrent.futures.Future = concurrent.futures.Future()
    _pending_answer = fut
    run_on_main(_invoke_dialog_main_thread, question, options or [])
    try:
        answer = fut.result(timeout=300)
    except (concurrent.futures.TimeoutError, TimeoutError):
        _pending_answer = None
        return {"ok": False, "error_kind": "no_answer",
                "error": "用户未在限定时间内回答澄清问题。"}
    if not answer.strip():
        return {"ok": False, "error_kind": "no_answer",
                "error": "用户取消或未提供澄清回答。"}
    return {"ok": True, "answer": answer}
