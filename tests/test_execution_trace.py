"""Pure Python tests for POPAgent execution trace helpers."""

from pathlib import Path
import importlib.util
import json
import sys


ROOT = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location(
    "execution_trace", ROOT / "agent_core" / "execution_trace.py"
)
execution_trace = importlib.util.module_from_spec(spec)
sys.modules["execution_trace"] = execution_trace
spec.loader.exec_module(execution_trace)


def test_trace_builder_creates_version_2_schema():
    trace = execution_trace.create_trace()

    assert trace["version"] == 2
    assert trace["iterations"] == []
    assert trace["summary"] == {
        "tool_count": 0,
        "error_count": 0,
        "aborted": False,
        "abort_reason": "",
    }


def test_trace_records_success_error_and_abort():
    trace = execution_trace.create_trace()
    iteration = execution_trace.record_iteration(
        trace,
        index=0,
        stream=False,
        latency_ms=123.8,
        status_code=200,
        finish_reason="tool_calls",
        text="assistant text",
        reasoning_content="reasoning text",
    )

    execution_trace.record_tool_call(
        trace,
        iteration,
        name="blender.query",
        arguments={"target": "scene"},
        result={"ok": True, "objects": 2},
        duration_ms=5.4,
    )
    execution_trace.record_tool_call(
        trace,
        iteration,
        name="blender.fail",
        arguments={},
        result={"ok": False, "error_kind": "invalid_arguments", "error": "bad"},
        duration_ms=1,
    )
    execution_trace.record_abort(trace, "anti_loop")

    assert trace["summary"]["tool_count"] == 2
    assert trace["summary"]["error_count"] == 1
    assert trace["summary"]["aborted"] is True
    assert trace["summary"]["abort_reason"] == "anti_loop"
    assert trace["iterations"][0]["tool_calls"][1]["error_kind"] == "invalid_arguments"


def test_parse_trace_supports_legacy_list_and_version_2_dict():
    legacy = [{"name": "old.tool", "result": {"ok": True}}]
    parsed_legacy = execution_trace.parse_trace(json.dumps(legacy))

    assert parsed_legacy["version"] == 1
    assert parsed_legacy["legacy_tool_calls"] == legacy
    assert parsed_legacy["summary"]["tool_count"] == 1

    trace = execution_trace.create_trace()
    parsed_v2 = execution_trace.parse_trace(json.dumps(trace))

    assert parsed_v2 == trace


def run():
    test_trace_builder_creates_version_2_schema()
    test_trace_records_success_error_and_abort()
    test_parse_trace_supports_legacy_list_and_version_2_dict()
    print("test_execution_trace OK")
    return True


if __name__ == "__main__":
    run()
