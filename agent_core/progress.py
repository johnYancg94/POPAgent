"""Live progress events for POPAgent agent turns.

This module stays pure Python so it can be tested outside Blender. Callers wire
the sink to UI callbacks that marshal actual bpy writes back to the main thread.
"""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Callable, Literal


ProgressKind = Literal[
    "turn_start",
    "model_request_start",
    "model_stream_text",
    "tool_call_start",
    "tool_call_finish",
    "tool_call_error",
    "tool_group_start",
    "retry",
    "finalizing",
]


@dataclass
class AgentProgressEvent:
    kind: ProgressKind
    message: str = ""
    icon: str = ""
    tool_name: str = ""
    ok: bool = True
    duration_ms: float = 0
    text_delta: str = ""


def tool_status_text(name: str) -> str:
    """Return a compact user-facing status label for a tool name."""
    if name == "blender.api_search":
        return "查询 Blender API 文档"
    if name == "dev.run_python":
        return "执行 Python 脚本"
    if name.startswith("blender.material."):
        return "处理材质节点"
    if name.startswith("blender.geometry_nodes."):
        return "处理 Geometry Nodes"
    if (
        name.startswith("blender.scene")
        or name.startswith("blender.object")
        or name.startswith("blender.mesh")
        or name.startswith("blender.select")
        or name == "blender.viewport_screenshot"
    ):
        return "查看当前 Blender 场景信息"
    return f"调用工具：{name}"


class ProgressSink:
    """Consumes semantic progress events and writes throttled UI updates."""

    def __init__(
        self,
        *,
        status_writer: Callable[[str, str], None],
        text_writer: Callable[[str], None] | None = None,
        min_text_interval: float = 0.2,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._status_writer = status_writer
        self._text_writer = text_writer
        self._min_text_interval = max(0.0, float(min_text_interval))
        self._monotonic = monotonic
        self._running_text = ""
        self._last_text_flush = self._monotonic()

    @property
    def running_text(self) -> str:
        return self._running_text

    def emit(self, event: AgentProgressEvent) -> None:
        if event.kind == "model_stream_text":
            self._append_text(event.text_delta)
            return

        status = self._status_for(event)
        if status is not None:
            self._status_writer(*status)

    def flush_text(self) -> None:
        if self._text_writer is not None and self._running_text:
            self._text_writer(self._running_text)
            self._last_text_flush = self._monotonic()

    def _append_text(self, delta: str) -> None:
        if not delta:
            return
        self._running_text += delta
        if self._text_writer is None:
            return
        now = self._monotonic()
        if now - self._last_text_flush >= self._min_text_interval:
            self.flush_text()

    def _status_for(self, event: AgentProgressEvent) -> tuple[str, str] | None:
        if event.message:
            return event.message, event.icon or "INFO"
        if event.kind == "turn_start":
            return "开始处理请求...", "SORTTIME"
        if event.kind == "model_request_start":
            return "正在规划下一步...", "SORTTIME"
        if event.kind == "tool_group_start":
            return "准备执行工具...", "TOOL_SETTINGS"
        if event.kind == "tool_call_start":
            return f"准备调用：{tool_status_text(event.tool_name)}", "TOOL_SETTINGS"
        if event.kind == "tool_call_finish":
            label = tool_status_text(event.tool_name)
            ms = max(0, int(event.duration_ms))
            return f"完成：{label}（{ms} ms）", "CHECKMARK"
        if event.kind == "tool_call_error":
            return f"工具失败：{tool_status_text(event.tool_name)}", "ERROR"
        if event.kind == "retry":
            return "请求失败，正在重试...", "FILE_REFRESH"
        if event.kind == "finalizing":
            return "整理结果并写入历史...", "WORDWRAP_ON"
        return None
