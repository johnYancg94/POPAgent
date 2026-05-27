import json
from .base import BaseProvider, LLMResponse, ToolCallRaw, StreamEvent, StreamParser


class OpenAICompatProvider(BaseProvider):
    """Handles OpenAI and DeepSeek (OpenAI-compatible) APIs."""

    def __init__(self, org: str):
        self._org = org  # "openai" or "deepseek"

    def get_api_key(self, prefs) -> str:
        if self._org == "openai":
            return prefs.open_ai_api_key
        return prefs.deepseek_api_key

    def get_url(self, prefs) -> str:
        if self._org == "openai":
            return prefs.open_ai_base_url.rstrip("/") + "/chat/completions"
        return prefs.deepseek_base_url.rstrip("/") + "/chat/completions"

    def get_headers(self, prefs) -> dict:
        key = self.get_api_key(prefs)
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
        if prefs.use_streaming:
            headers["Accept"] = "text/event-stream"
        return headers

    def get_payload(self, prefs) -> dict:
        model = prefs.open_ai_model if self._org == "openai" else prefs.deepseek_model
        payload = {
            "temperature": 1.0,
            "top_p": 1.0,
            "stream": prefs.use_streaming,
            "frequency_penalty": 0,
            "model": model,
            "n": 1,
            "presence_penalty": 0,
        }
        if self._org == "openai":
            payload["reasoning_effort"] = "medium"
        return payload

    def get_schema(self) -> dict:
        return {
            "req_contents": "messages",
            "req_role_system": "system",
            "req_role_user": "user",
            "req_role_assistant": "assistant",
            "req_parts": "content",
            "res_root": "choices",
            "res_content": "message",
            "res_finish_reason": "finish_reason",
        }

    def skills_to_tools(self, skills: list[dict]) -> list[dict]:
        self._reset_tool_name_map()
        tools = []
        for skill in skills:
            tools.append({
                "type": "function",
                "function": {
                    "name": self._to_wire_tool_name(skill["name"]),
                    "description": skill.get("description", ""),
                    "parameters": skill.get("parameters", {"type": "object", "properties": {}}),
                },
            })
        return tools

    def build_request(self, prefs, messages: list[dict], tools: list[dict],
                      system: str = "", stream: bool = False) -> tuple[str, dict, dict]:
        url = self.get_url(prefs)
        headers = self.get_headers(prefs)
        # OpenAI: system is a message, already prepended by MessageBuilder.to_openai()
        model = prefs.open_ai_model if self._org == "openai" else prefs.deepseek_model
        body: dict = {
            "model": model,
            "messages": messages,
            "temperature": 1.0,
            "stream": bool(stream),
        }
        if self._org == "openai":
            body["reasoning_effort"] = "medium"
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        if stream:
            headers = dict(headers)
            headers["Accept"] = "text/event-stream"
        return url, headers, body

    def parse_response(self, response_json: dict) -> LLMResponse:
        choice = response_json.get("choices", [{}])[0]
        message = choice.get("message", {})
        text = message.get("content") or ""
        reasoning_content = message.get("reasoning_content") or ""
        finish_reason = choice.get("finish_reason", "")

        tool_calls = []
        for tc in message.get("tool_calls") or []:
            fn = tc.get("function", {})
            try:
                args = json.loads(fn.get("arguments", "{}"))
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(ToolCallRaw(
                id=tc.get("id", ""),
                name=self._from_wire_tool_name(fn.get("name", "")),
                arguments=args,
            ))

        return LLMResponse(
            text=text,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            reasoning_content=reasoning_content,
            raw=response_json,
        )

    def supports_streaming_with_tools(self) -> bool:
        return True

    def create_stream_parser(self) -> "OpenAIStreamParser":
        return OpenAIStreamParser(getattr(self, "_tool_wire_to_skill_name", {}).copy())


class OpenAIStreamParser(StreamParser):
    """Assembles OpenAI / DeepSeek SSE chunks into text + tool_calls.

    Each tool_call streams as `delta.tool_calls[*]` deltas keyed by `index`;
    arguments arrive as JSON string fragments that must be concatenated before
    being parsed as JSON.
    """

    def __init__(self, tool_wire_to_skill_name: dict[str, str] | None = None):
        self._text_parts: list[str] = []
        self._reasoning_parts: list[str] = []
        # index -> {"id": str, "name": str, "args": str}
        self._tool_acc: dict[int, dict] = {}
        self._finish_reason: str = ""
        self._emitted_tool_indices: set[int] = set()
        self._tool_wire_to_skill_name = tool_wire_to_skill_name or {}

    def _from_wire_tool_name(self, name: str) -> str:
        return self._tool_wire_to_skill_name.get(name, name)

    def feed_line(self, line: str) -> list[StreamEvent]:
        if not line:
            return []
        if not line.startswith("data:"):
            return []
        data = line[5:].strip()
        if data == "[DONE]":
            return [StreamEvent(kind="done", payload=self._finish_reason or "stop")]
        try:
            chunk = json.loads(data)
        except json.JSONDecodeError:
            return []

        events: list[StreamEvent] = []
        choice = (chunk.get("choices") or [{}])[0]
        delta = choice.get("delta") or {}
        finish = choice.get("finish_reason")
        if finish:
            self._finish_reason = finish

        text_delta = delta.get("content")
        if isinstance(text_delta, str) and text_delta:
            self._text_parts.append(text_delta)
            events.append(StreamEvent(kind="text", payload=text_delta))

        reasoning_delta = delta.get("reasoning_content")
        if isinstance(reasoning_delta, str) and reasoning_delta:
            self._reasoning_parts.append(reasoning_delta)

        for tc_delta in delta.get("tool_calls") or []:
            idx = tc_delta.get("index", 0)
            slot = self._tool_acc.setdefault(idx, {"id": "", "name": "", "args": ""})
            if tc_delta.get("id"):
                slot["id"] = tc_delta["id"]
            fn = tc_delta.get("function") or {}
            if fn.get("name"):
                slot["name"] = fn["name"]
            args_delta = fn.get("arguments")
            if isinstance(args_delta, str):
                slot["args"] += args_delta

        # When finish_reason indicates tool_calls, finalize all in-flight calls.
        if finish == "tool_calls":
            for idx in sorted(self._tool_acc.keys()):
                if idx in self._emitted_tool_indices:
                    continue
                slot = self._tool_acc[idx]
                try:
                    parsed_args = json.loads(slot["args"]) if slot["args"] else {}
                except json.JSONDecodeError:
                    parsed_args = {}
                events.append(StreamEvent(
                    kind="tool_call",
                    payload=ToolCallRaw(
                        id=slot["id"],
                        name=self._from_wire_tool_name(slot["name"]),
                        arguments=parsed_args,
                    ),
                ))
                self._emitted_tool_indices.add(idx)

        return events

    def finalize(self) -> LLMResponse:
        # Emit any tool_calls not yet emitted (defensive: server may close early).
        tool_calls: list[ToolCallRaw] = []
        for idx in sorted(self._tool_acc.keys()):
            slot = self._tool_acc[idx]
            try:
                parsed_args = json.loads(slot["args"]) if slot["args"] else {}
            except json.JSONDecodeError:
                parsed_args = {}
            tool_calls.append(ToolCallRaw(
                id=slot["id"],
                name=self._from_wire_tool_name(slot["name"]),
                arguments=parsed_args,
            ))
        return LLMResponse(
            text="".join(self._text_parts),
            tool_calls=tool_calls,
            finish_reason=self._finish_reason or ("tool_calls" if tool_calls else "stop"),
            reasoning_content="".join(self._reasoning_parts),
            raw=None,
        )
