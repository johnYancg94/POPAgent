"""
Cross-provider message builder.

Stores messages in a neutral internal format and converts to
provider-specific wire format on demand.

OpenAI wire order:
  [user] ... [assistant + tool_calls] [tool] ... [assistant final]

Claude wire order:
  [user] ... [assistant content=[tool_use]] [user content=[tool_result]] ... [assistant final]
"""

from __future__ import annotations
import json
from dataclasses import dataclass, field
from typing import Any


# ─── Internal data types ────────────────────────────────────────────────────

@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class _Msg:
    role: str                              # "user" | "assistant" | "tool_result"
    text: str = ""
    reasoning_content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_result_id: str = ""              # for tool_result role
    tool_result_name: str = ""
    tool_result_content: str = ""


# ─── Builder ────────────────────────────────────────────────────────────────

class MessageBuilder:
    """Accumulate messages, emit provider-specific wire format."""

    def __init__(self):
        self._messages: list[_Msg] = []

    # ── Append helpers ──

    def append_user(self, text: str) -> None:
        self._messages.append(_Msg(role="user", text=text))

    def append_assistant(self, text: str) -> None:
        self._messages.append(_Msg(role="assistant", text=text))

    def append_assistant_with_tool_calls(
        self,
        text: str,
        tool_calls: list[ToolCall],
        reasoning_content: str = "",
    ) -> None:
        self._messages.append(
            _Msg(
                role="assistant",
                text=text,
                reasoning_content=reasoning_content,
                tool_calls=tool_calls,
            )
        )

    def append_tool_result(
        self, call_id: str, name: str, result: Any
    ) -> None:
        content = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
        self._messages.append(
            _Msg(
                role="tool_result",
                tool_result_id=call_id,
                tool_result_name=name,
                tool_result_content=content,
            )
        )

    # ── Wire-format conversion ──

    def to_openai(
        self,
        system_prompt: str | None = None,
        tool_name_mapper=None,
        include_reasoning_content: bool = False,
    ) -> list[dict]:
        """Emit OpenAI-compatible messages list."""
        map_tool_name = tool_name_mapper or (lambda name: name)
        out: list[dict] = []
        if system_prompt:
            out.append({"role": "system", "content": system_prompt})
        for msg in self._messages:
            if msg.role == "user":
                out.append({"role": "user", "content": msg.text})
            elif msg.role == "assistant" and msg.tool_calls:
                assistant_msg = {
                    "role": "assistant",
                    "content": msg.text or None,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": map_tool_name(tc.name),
                                "arguments": json.dumps(tc.arguments),
                            },
                        }
                        for tc in msg.tool_calls
                    ],
                }
                if include_reasoning_content and msg.reasoning_content:
                    assistant_msg["reasoning_content"] = msg.reasoning_content
                out.append(assistant_msg)
            elif msg.role == "assistant":
                out.append({"role": "assistant", "content": msg.text})
            elif msg.role == "tool_result":
                out.append({
                    "role": "tool",
                    "tool_call_id": msg.tool_result_id,
                    "content": msg.tool_result_content,
                })
        return out

    def to_anthropic(
        self,
        system_prompt: str | None = None,
        tool_name_mapper=None,
    ) -> tuple[str, list[dict]]:
        """Return (system_text, messages_list) for the Anthropic Messages API."""
        map_tool_name = tool_name_mapper or (lambda name: name)
        messages: list[dict] = []
        for msg in self._messages:
            if msg.role == "user":
                messages.append({"role": "user", "content": msg.text})
            elif msg.role == "assistant" and msg.tool_calls:
                content: list[dict] = []
                if msg.text:
                    content.append({"type": "text", "text": msg.text})
                for tc in msg.tool_calls:
                    content.append({
                        "type": "tool_use",
                        "id": tc.id,
                        "name": map_tool_name(tc.name),
                        "input": tc.arguments,
                    })
                messages.append({"role": "assistant", "content": content})
            elif msg.role == "assistant":
                messages.append({
                    "role": "assistant",
                    "content": [{"type": "text", "text": msg.text}],
                })
            elif msg.role == "tool_result":
                messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": msg.tool_result_id,
                            "content": msg.tool_result_content,
                        }
                    ],
                })
        return (system_prompt or "", messages)

    # ── History interop ──

    @classmethod
    def from_history(
        cls,
        history_items,  # bpy_prop_collection of HistoryPropertyGroup
    ) -> "MessageBuilder":
        """Reconstruct from Blender property history (plain chat messages only)."""
        mb = cls()
        for item in reversed(history_items):
            if item.is_error or not item.is_enabled:
                continue
            mb.append_user(item.user_prompt)
            mb.append_assistant(item.answer)
        return mb
