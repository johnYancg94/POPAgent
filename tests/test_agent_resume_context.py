import importlib.util
from pathlib import Path
import sys
import types


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "agent_resume_context", ROOT / "agent_core" / "resume_context.py"
)
resume_context = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resume_context)


def _load_message_builder():
    package = types.ModuleType("resume_test_agent_core")
    package.__path__ = [str(ROOT / "agent_core")]
    sys.modules[package.__name__] = package

    cb_spec = importlib.util.spec_from_file_location(
        "resume_test_agent_core.context_budget",
        ROOT / "agent_core" / "context_budget.py",
    )
    context_budget = importlib.util.module_from_spec(cb_spec)
    sys.modules[cb_spec.name] = context_budget
    cb_spec.loader.exec_module(context_budget)

    mb_spec = importlib.util.spec_from_file_location(
        "resume_test_agent_core.message_builder",
        ROOT / "agent_core" / "message_builder.py",
    )
    message_builder = importlib.util.module_from_spec(mb_spec)
    sys.modules[mb_spec.name] = message_builder
    mb_spec.loader.exec_module(message_builder)
    return message_builder


def test_build_resume_context_preserves_progress_and_failure():
    trace = {
        "version": 2,
        "iterations": [
            {
                "index": 0,
                "tool_calls": [
                    {
                        "name": "blender.create_object",
                        "ok": True,
                        "arguments_preview": '{"name":"Cube"}',
                        "result_preview": '{"ok":true}',
                    },
                    {
                        "name": "blender.assign_material",
                        "ok": False,
                        "error_kind": "invalid_input",
                        "arguments_preview": '{"object":"Cube"}',
                        "result_preview": '{"ok":false}',
                    },
                ],
            }
        ],
        "summary": {"aborted": True, "abort_reason": "HTTP 400 Error"},
    }

    checkpoint = resume_context.build_resume_context(
        original_prompt="Create and shade a cube",
        trace=trace,
        error_kind="HTTP 400 Error",
        error_message="Bad Request",
    )

    assert checkpoint["original_prompt"] == "Create and shade a cube"
    assert checkpoint["completed_actions"][0]["name"] == "blender.create_object"
    assert checkpoint["failed_step"]["name"] == "blender.assign_material"
    assert checkpoint["error_kind"] == "HTTP 400 Error"
    assert "continue" in checkpoint["remaining_goal"].lower()


def test_render_resume_context_is_bounded_and_actionable():
    checkpoint = resume_context.build_resume_context(
        original_prompt="Build the scene",
        trace={"version": 2, "iterations": [], "summary": {}},
        error_kind="stream_error",
        error_message="x" * 5000,
    )

    text = resume_context.render_resume_context(checkpoint)

    assert "Build the scene" in text
    assert "stream_error" in text
    assert "Do not repeat completed actions" in text
    assert len(text) < 3000


def test_resume_context_and_new_prompt_share_one_user_message():
    message_builder = _load_message_builder()
    builder = message_builder.MessageBuilder()

    builder.append_resume_context("saved checkpoint", "continue differently")

    assert builder.to_anthropic()[1] == [
        {
            "role": "user",
            "content": (
                "saved checkpoint\n\n"
                "Current user message:\ncontinue differently"
            ),
        }
    ]
