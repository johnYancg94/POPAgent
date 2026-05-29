from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class LLMResponse:
    text: str
    tool_calls: list  # list[ToolCallRaw]
    finish_reason: str
    reasoning_content: str = ""
    usage: dict = field(default_factory=dict)
    raw: Any = None


@dataclass
class ToolCallRaw:
    id: str
    name: str
    arguments: dict


@dataclass
class StreamEvent:
    """A single event emitted while parsing a streaming response.

    kind:
      "text"      — payload is a str fragment to append to displayed answer.
      "tool_call" — a tool_call has fully assembled; payload is ToolCallRaw.
      "done"      — stream finished; payload is the finish_reason str.
    """

    kind: Literal["text", "tool_call", "done"]
    payload: Any


class BaseProvider(ABC):
    """Abstract base for all LLM providers."""

    def _reset_tool_name_map(self) -> None:
        self._tool_wire_to_skill_name = {}

    def _to_wire_tool_name(self, name: str) -> str:
        wire_name = name.replace(".", "__")
        if not hasattr(self, "_tool_wire_to_skill_name"):
            self._reset_tool_name_map()
        self._tool_wire_to_skill_name[wire_name] = name
        return wire_name

    def _from_wire_tool_name(self, name: str) -> str:
        mapping = getattr(self, "_tool_wire_to_skill_name", {})
        return mapping.get(name, name)

    @abstractmethod
    def get_api_key(self, prefs) -> str:
        ...

    @abstractmethod
    def get_url(self, prefs) -> str:
        ...

    @abstractmethod
    def get_headers(self, prefs) -> dict:
        ...

    @abstractmethod
    def get_payload(self, prefs) -> dict:
        ...

    @abstractmethod
    def get_schema(self) -> dict:
        """Return request/response schema keys for ChatCompanionProperties."""
        ...

    @abstractmethod
    def skills_to_tools(self, skills: list[dict]) -> list[dict]:
        """Convert skill dicts from registry to provider-specific tool schema."""
        ...

    @abstractmethod
    def build_request(self, prefs, messages: list[dict], tools: list[dict],
                      system: str = "") -> tuple[str, dict, dict]:
        """Return (url, headers, body) ready for httpx.post."""
        ...

    @abstractmethod
    def parse_response(self, response_json: dict) -> LLMResponse:
        """Parse raw JSON response into LLMResponse."""
        ...

    def create_stream_parser(self) -> "StreamParser":
        """Override to enable streaming-with-tool-calls. Default raises."""
        raise NotImplementedError(
            f"{type(self).__name__} does not support streaming."
        )

    def supports_streaming_with_tools(self) -> bool:
        """Whether build_request(stream=True) plus create_stream_parser is wired."""
        return False

    def supports_image_input(self, prefs) -> bool:
        """Whether this configured model can receive image content blocks."""
        return False

    def connectivity_request(self, prefs) -> tuple[str, str, dict]:
        """Return (method, url, headers) for a token-free reachability probe.

        Default targets an OpenAI-style `/models` listing derived from the
        chat-completions URL. Providers override when their base differs.
        """
        url = self.get_url(prefs).rsplit("/", 1)[0] + "/models"
        return "GET", url, self.get_headers(prefs)

    def apply_to_props(self, prefs, props) -> None:
        """Write provider config into ChatCompanionProperties."""
        import json

        props.api_key = self.get_api_key(prefs)
        props.api_url = self.get_url(prefs)
        props.api_headers = json.dumps(self.get_headers(prefs))
        props.api_payload = json.dumps(self.get_payload(prefs))

        schema = self.get_schema()
        props.req_schema_contents = schema["req_contents"]
        props.req_schema_role_system = schema["req_role_system"]
        props.req_schema_role_user = schema["req_role_user"]
        props.req_schema_role_assistant = schema["req_role_assistant"]
        props.req_schema_parts = schema["req_parts"]
        props.res_schema_root = schema["res_root"]
        props.res_schema_content = schema["res_content"]
        props.res_schema_finish_reason = schema["res_finish_reason"]
        props.api_details_updated = True


class StreamParser(ABC):
    """Incremental parser for an SSE-style streaming response.

    Feed it raw lines (already stripped of trailing newlines) one at a time;
    it yields StreamEvent objects. Call finalize() once the stream ends to
    obtain the complete LLMResponse with assembled tool_calls + text.
    """

    @abstractmethod
    def feed_line(self, line: str) -> list[StreamEvent]:
        """Process a single SSE line, return any events that fully assembled."""
        ...

    @abstractmethod
    def finalize(self) -> LLMResponse:
        """Return the complete response after stream end."""
        ...
