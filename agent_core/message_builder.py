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
    images: list[dict[str, str]] = field(default_factory=list)
    reasoning_content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_result_id: str = ""              # for tool_result role
    tool_result_name: str = ""
    tool_result_content: Any = ""


# ─── Builder ────────────────────────────────────────────────────────────────

class MessageBuilder:
    """Accumulate messages, emit provider-specific wire format."""

    def __init__(self):
        self._messages: list[_Msg] = []

    # ── Append helpers ──

    def append_user(
        self, text: str, images: list[dict[str, str]] | None = None
    ) -> None:
        self._messages.append(_Msg(role="user", text=text, images=images or []))

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
        self._messages.append(
            _Msg(
                role="tool_result",
                tool_result_id=call_id,
                tool_result_name=name,
                tool_result_content=result,
            )
        )

    # ── Wire-format conversion ──

    def to_openai(
        self,
        system_prompt: str | None = None,
        tool_name_mapper=None,
        include_reasoning_content: bool = False,
        include_image_results: bool = False,
    ) -> list[dict]:
        """Emit OpenAI-compatible messages list."""
        map_tool_name = tool_name_mapper or (lambda name: name)
        out: list[dict] = []
        if system_prompt:
            out.append({"role": "system", "content": system_prompt})
        for msg in self._messages:
            if msg.role == "user":
                if include_image_results and msg.images:
                    content = []
                    if msg.text:
                        content.append({"type": "text", "text": msg.text})
                    for image in msg.images:
                        content.append(_openai_image_block(image))
                    out.append({"role": "user", "content": content})
                else:
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
                screenshot = _viewport_screenshot_image(
                    msg.tool_result_name,
                    msg.tool_result_content,
                )
                if include_image_results and screenshot:
                    out.append({
                        "role": "tool",
                        "tool_call_id": msg.tool_result_id,
                        "content": (
                            "Viewport screenshot captured. The next message "
                            "contains the PNG image for visual analysis."
                        ),
                    })
                    out.append({
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    "This is the current Blender viewport "
                                    "screenshot returned by the tool. Use it "
                                    "as visual evidence for the user's request."
                                ),
                            },
                            _openai_image_block(screenshot),
                        ],
                    })
                else:
                    out.append({
                        "role": "tool",
                        "tool_call_id": msg.tool_result_id,
                        "content": _stringify_tool_result(msg.tool_result_content),
                    })
        return out

    def to_anthropic(
        self,
        system_prompt: str | None = None,
        tool_name_mapper=None,
        include_image_results: bool = False,
    ) -> tuple[str, list[dict]]:
        """Return (system_text, messages_list) for the Anthropic Messages API."""
        map_tool_name = tool_name_mapper or (lambda name: name)
        messages: list[dict] = []
        for msg in self._messages:
            if msg.role == "user":
                if include_image_results and msg.images:
                    content = []
                    if msg.text:
                        content.append({"type": "text", "text": msg.text})
                    for image in msg.images:
                        content.append(_anthropic_image_block(image))
                    messages.append({"role": "user", "content": content})
                else:
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
                screenshot = _viewport_screenshot_image(
                    msg.tool_result_name,
                    msg.tool_result_content,
                )
                if include_image_results and screenshot:
                    content = [
                        {
                            "type": "text",
                            "text": (
                                "Viewport screenshot captured. Use this PNG "
                                "image as visual evidence for the user's request."
                            ),
                        },
                        _anthropic_image_block(screenshot),
                    ]
                else:
                    content = _stringify_tool_result(msg.tool_result_content)
                messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": msg.tool_result_id,
                            "content": content,
                        }
                    ],
                })
        return (system_prompt or "", messages)

    # ── History interop ──

    @classmethod
    def from_history(
        cls,
        history_items,  # bpy_prop_collection of HistoryPropertyGroup
        max_items: int | None = None,
    ) -> "MessageBuilder":
        """Reconstruct from Blender property history (plain chat messages only)."""
        mb = cls()
        for item in reversed(history_context_items(history_items, max_items)):
            mb.append_user(item.user_prompt)
            mb.append_assistant(item.answer)
        return mb


def history_context_items(history_items, max_items: int | None = None) -> list:
    items = [
        item
        for item in history_items
        if not item.is_error and item.is_enabled
    ]
    if max_items is not None:
        items = items[:max(0, max_items)]
    return items


def _stringify_tool_result(result: Any) -> str:
    if isinstance(result, str):
        return result
    return json.dumps(result, ensure_ascii=False)


def _openai_image_block(image: dict[str, str]) -> dict:
    return {
        "type": "image_url",
        "image_url": {
            "url": f"data:{image['media_type']};base64,{image['data']}",
        },
    }


def _anthropic_image_block(image: dict[str, str]) -> dict:
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": image["media_type"],
            "data": image["data"],
        },
    }


def _viewport_screenshot_image(name: str, result: Any) -> dict[str, str] | None:
    if name != "blender.viewport_screenshot":
        return None

    payload = result
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return None
    if not isinstance(payload, dict) or not payload.get("ok"):
        return None

    data = payload.get("image_base64")
    if not isinstance(data, str) or not data:
        return None

    fmt = str(payload.get("format") or "png").lower().lstrip(".")
    if fmt == "jpg":
        fmt = "jpeg"
    if fmt not in {"png", "jpeg", "gif", "webp"}:
        fmt = "png"
    return {"data": data, "media_type": f"image/{fmt}"}
