import json
from .base import BaseProvider, LLMResponse, ToolCallRaw, StreamEvent, StreamParser

_ANTHROPIC_API_VERSION = "2023-06-01"


class AnthropicProvider(BaseProvider):
    """Anthropic Claude Messages API."""

    def get_api_key(self, prefs) -> str:
        return getattr(prefs, "anthropic_api_key", "")

    def get_url(self, prefs) -> str:
        base = getattr(prefs, "anthropic_base_url", "https://api.anthropic.com/v1")
        return base.rstrip("/") + "/messages"

    def get_headers(self, prefs) -> dict:
        return {
            "x-api-key": self.get_api_key(prefs),
            "anthropic-version": _ANTHROPIC_API_VERSION,
            "Content-Type": "application/json",
        }

    def get_payload(self, prefs) -> dict:
        model = getattr(prefs, "anthropic_model", "claude-sonnet-4-6")
        return {
            "model": model,
            "max_tokens": 8096,
            "stream": False,
        }

    def get_schema(self) -> dict:
        return {
            "req_contents": "messages",
            "req_role_system": "system",
            "req_role_user": "user",
            "req_role_assistant": "assistant",
            "req_parts": "text",
            "res_root": "content",
            "res_content": "text",
            "res_finish_reason": "stop_reason",
        }

    def skills_to_tools(self, skills: list[dict]) -> list[dict]:
        # Claude tool schema differs from OpenAI: "input_schema" instead of "parameters"
        self._reset_tool_name_map()
        tools = []
        for skill in skills:
            params = skill.get("parameters", {"type": "object", "properties": {}})
            tools.append({
                "name": self._to_wire_tool_name(skill["name"]),
                "description": skill.get("description", ""),
                "input_schema": params,
            })
        return tools

    def build_request(self, prefs, messages: list[dict], tools: list[dict],
                      system: str = "", stream: bool = False) -> tuple[str, dict, dict]:
        url = self.get_url(prefs)
        headers = self.get_headers(prefs)
        model = getattr(prefs, "anthropic_model", "claude-sonnet-4-6")
        body: dict = {
            "model": model,
            "max_tokens": 8096,
            "messages": messages,
            "stream": bool(stream),
        }
        if system:
            body["system"] = system
        if tools:
            body["tools"] = tools
        if stream:
            headers = dict(headers)
            headers["Accept"] = "text/event-stream"
        return url, headers, body

    def parse_response(self, response_json: dict) -> LLMResponse:
        # Claude response: {"content": [{"type": "text"|"tool_use", ...}], "stop_reason": ...}
        content_blocks = response_json.get("content", [])
        stop_reason = response_json.get("stop_reason", "")

        text_parts = []
        tool_calls = []
        for block in content_blocks:
            if block.get("type") == "text":
                text_parts.append(block.get("text", ""))
            elif block.get("type") == "tool_use":
                tool_calls.append(ToolCallRaw(
                    id=block.get("id", ""),
                    name=self._from_wire_tool_name(block.get("name", "")),
                    arguments=block.get("input", {}),
                ))

        return LLMResponse(
            text="\n".join(text_parts),
            tool_calls=tool_calls,
            finish_reason=stop_reason,
            usage=response_json.get("usage") or {},
            raw=response_json,
        )

    def supports_streaming_with_tools(self) -> bool:
        return True

    def create_stream_parser(self) -> "AnthropicStreamParser":
        return AnthropicStreamParser(getattr(self, "_tool_wire_to_skill_name", {}).copy())


class AnthropicStreamParser(StreamParser):
    """Assembles Claude SSE events into text + tool_calls.

    Event protocol (one event = "event:" line + "data:" line):
      content_block_start  → block at {index} starts (text or tool_use; tool_use has id+name)
      content_block_delta  → text_delta or input_json_delta partial JSON
      content_block_stop   → block ended; tool_use input parsed at this point
      message_delta        → carries final stop_reason
      message_stop         → stream end
    """

    def __init__(self, tool_wire_to_skill_name: dict[str, str] | None = None):
        # index -> {"type": "text"|"tool_use", "text": str, "id": str, "name": str, "json_buf": str}
        self._blocks: dict[int, dict] = {}
        self._stop_reason: str = ""
        self._usage: dict = {}
        self._pending_event: str = ""
        self._emitted_tool_indices: set[int] = set()
        self._tool_wire_to_skill_name = tool_wire_to_skill_name or {}

    def _from_wire_tool_name(self, name: str) -> str:
        return self._tool_wire_to_skill_name.get(name, name)

    def feed_line(self, line: str) -> list[StreamEvent]:
        if not line:
            return []
        if line.startswith("event:"):
            self._pending_event = line[6:].strip()
            return []
        if not line.startswith("data:"):
            return []
        data = line[5:].strip()
        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            return []

        ev = self._pending_event
        events: list[StreamEvent] = []

        if ev == "content_block_start":
            idx = payload.get("index", 0)
            block = payload.get("content_block") or {}
            btype = block.get("type", "")
            slot = {"type": btype, "text": "", "id": "", "name": "", "json_buf": ""}
            if btype == "tool_use":
                slot["id"] = block.get("id", "")
                slot["name"] = block.get("name", "")
            self._blocks[idx] = slot

        elif ev == "message_start":
            message = payload.get("message") or {}
            usage = message.get("usage")
            if isinstance(usage, dict):
                self._usage.update(usage)

        elif ev == "content_block_delta":
            idx = payload.get("index", 0)
            slot = self._blocks.get(idx)
            if slot is None:
                return []
            delta = payload.get("delta") or {}
            dtype = delta.get("type", "")
            if dtype == "text_delta":
                txt = delta.get("text", "")
                if txt:
                    slot["text"] += txt
                    events.append(StreamEvent(kind="text", payload=txt))
            elif dtype == "input_json_delta":
                slot["json_buf"] += delta.get("partial_json", "")

        elif ev == "content_block_stop":
            idx = payload.get("index", 0)
            slot = self._blocks.get(idx)
            if slot and slot["type"] == "tool_use" and idx not in self._emitted_tool_indices:
                try:
                    parsed = json.loads(slot["json_buf"]) if slot["json_buf"] else {}
                except json.JSONDecodeError:
                    parsed = {}
                events.append(StreamEvent(
                    kind="tool_call",
                    payload=ToolCallRaw(
                        id=slot["id"],
                        name=self._from_wire_tool_name(slot["name"]),
                        arguments=parsed,
                    ),
                ))
                self._emitted_tool_indices.add(idx)

        elif ev == "message_delta":
            delta = payload.get("delta") or {}
            sr = delta.get("stop_reason")
            if sr:
                self._stop_reason = sr
            usage = payload.get("usage")
            if isinstance(usage, dict):
                self._usage.update(usage)

        elif ev == "message_stop":
            events.append(StreamEvent(kind="done", payload=self._stop_reason or "end_turn"))

        return events

    def finalize(self) -> LLMResponse:
        text_parts: list[str] = []
        tool_calls: list[ToolCallRaw] = []
        for idx in sorted(self._blocks.keys()):
            slot = self._blocks[idx]
            if slot["type"] == "text":
                text_parts.append(slot["text"])
            elif slot["type"] == "tool_use":
                try:
                    parsed = json.loads(slot["json_buf"]) if slot["json_buf"] else {}
                except json.JSONDecodeError:
                    parsed = {}
                tool_calls.append(ToolCallRaw(
                    id=slot["id"],
                    name=self._from_wire_tool_name(slot["name"]),
                    arguments=parsed,
                ))
        return LLMResponse(
            text="\n".join(p for p in text_parts if p),
            tool_calls=tool_calls,
            finish_reason=self._stop_reason or ("tool_use" if tool_calls else "end_turn"),
            usage=self._usage,
            raw=None,
        )
