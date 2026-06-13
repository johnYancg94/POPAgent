"""Pure Python tests for viewport screenshot vision handoff."""

from pathlib import Path
import importlib.util
import json
import sys
import types


ROOT = Path(__file__).resolve().parents[1]
pkg = types.ModuleType("popagent_vision_test")
pkg.__path__ = [str(ROOT)]
sys.modules["popagent_vision_test"] = pkg

agent_pkg = types.ModuleType("popagent_vision_test.agent_core")
agent_pkg.__path__ = [str(ROOT / "agent_core")]
sys.modules["popagent_vision_test.agent_core"] = agent_pkg

spec = importlib.util.spec_from_file_location(
    "popagent_vision_test.agent_core.message_builder",
    ROOT / "agent_core" / "message_builder.py",
)
message_builder = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = message_builder
spec.loader.exec_module(message_builder)

MessageBuilder = message_builder.MessageBuilder
ToolCall = message_builder.ToolCall


PNG_BASE64 = "iVBORw0KGgo="


class _HistoryItem:
    def __init__(
        self,
        user_prompt,
        answer,
        is_enabled=True,
        is_error=False,
    ):
        self.user_prompt = user_prompt
        self.answer = answer
        self.is_enabled = is_enabled
        self.is_error = is_error


def _builder_with_screenshot():
    mb = MessageBuilder()
    mb.append_user("看看当前视图")
    mb.append_assistant_with_tool_calls(
        "",
        [ToolCall(id="call_1", name="blender.viewport_screenshot", arguments={})],
    )
    mb.append_tool_result(
        "call_1",
        "blender.viewport_screenshot",
        {"ok": True, "image_base64": PNG_BASE64, "format": "png"},
    )
    return mb


def test_openai_viewport_screenshot_becomes_image_user_message():
    messages = _builder_with_screenshot().to_openai(include_image_results=True)

    assert messages[-2] == {
        "role": "tool",
        "tool_call_id": "call_1",
        "content": "Viewport screenshot captured. The next message contains the PNG image for visual analysis.",
    }
    assert messages[-1]["role"] == "user"
    content = messages[-1]["content"]
    assert content[0]["type"] == "text"
    assert "current Blender viewport screenshot" in content[0]["text"]
    assert content[1] == {
        "type": "image_url",
        "image_url": {"url": f"data:image/png;base64,{PNG_BASE64}"},
    }


def test_anthropic_viewport_screenshot_becomes_tool_result_image_block():
    _system, messages = _builder_with_screenshot().to_anthropic(
        include_image_results=True
    )

    result_message = messages[-1]
    assert result_message["role"] == "user"
    block = result_message["content"][0]
    assert block["type"] == "tool_result"
    assert block["tool_use_id"] == "call_1"
    assert block["content"][0]["type"] == "text"
    assert block["content"][1] == {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": "image/png",
            "data": PNG_BASE64,
        },
    }


def test_viewport_screenshot_stays_text_without_image_results():
    messages = _builder_with_screenshot().to_openai(include_image_results=False)

    assert messages[-1]["role"] == "tool"
    assert json.loads(messages[-1]["content"]) == {
        "ok": True,
        "image_base64": PNG_BASE64,
        "format": "png",
    }


def test_openai_user_images_are_sent_with_prompt_when_enabled():
    mb = MessageBuilder()
    mb.append_user(
        "分析这张图",
        images=[{"media_type": "image/png", "data": PNG_BASE64}],
    )

    messages = mb.to_openai(include_image_results=True)

    assert messages == [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "分析这张图"},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{PNG_BASE64}"},
                },
            ],
        }
    ]


def test_anthropic_user_images_are_sent_with_prompt_when_enabled():
    mb = MessageBuilder()
    mb.append_user(
        "分析这张图",
        images=[{"media_type": "image/png", "data": PNG_BASE64}],
    )

    _system, messages = mb.to_anthropic(include_image_results=True)

    assert messages == [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "分析这张图"},
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": PNG_BASE64,
                    },
                },
            ],
        }
    ]


def test_user_images_are_ignored_when_multimodal_is_disabled():
    mb = MessageBuilder()
    mb.append_user(
        "只发文字",
        images=[{"media_type": "image/png", "data": PNG_BASE64}],
    )

    assert mb.to_openai(include_image_results=False) == [
        {"role": "user", "content": "只发文字"}
    ]


def test_from_history_limits_to_recent_enabled_non_error_items():
    history = [
        _HistoryItem("newest", "answer newest"),
        _HistoryItem("disabled", "answer disabled", is_enabled=False),
        _HistoryItem("middle", "answer middle"),
        _HistoryItem("error", "answer error", is_error=True),
        _HistoryItem("oldest", "answer oldest"),
    ]

    mb = MessageBuilder.from_history(history, max_items=2)

    assert mb.to_openai() == [
        {"role": "user", "content": "middle"},
        {"role": "assistant", "content": "answer middle"},
        {"role": "user", "content": "newest"},
        {"role": "assistant", "content": "answer newest"},
    ]


def run():
    test_openai_viewport_screenshot_becomes_image_user_message()
    test_anthropic_viewport_screenshot_becomes_tool_result_image_block()
    test_viewport_screenshot_stays_text_without_image_results()
    test_openai_user_images_are_sent_with_prompt_when_enabled()
    test_anthropic_user_images_are_sent_with_prompt_when_enabled()
    test_user_images_are_ignored_when_multimodal_is_disabled()
    test_from_history_limits_to_recent_enabled_non_error_items()
    print("test_vision_message_builder OK")
    return True


if __name__ == "__main__":
    run()
