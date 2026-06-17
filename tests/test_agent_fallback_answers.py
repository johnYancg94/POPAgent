"""Tests for deterministic Agent fallback answers after tool success."""

import importlib.util
import os
import sys
from pathlib import Path


ROOT = Path(os.environ.get("POPAGENT_ROOT", str(Path(__file__).resolve().parents[1])))


def _load_module():
    path = ROOT / "agent_core" / "fallback_answers.py"
    spec = importlib.util.spec_from_file_location("popagent_fallback_answers", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_renderset_inspect_fallback_reports_blocker_and_no_writes():
    mod = _load_module()
    trace = {
        "iterations": [
            {
                "tool_calls": [
                    {
                        "name": "agent.activate_skill",
                        "ok": True,
                        "arguments_preview": '{"name": "prepare-renderset-contexts"}',
                        "result_preview": '{"ok": true}',
                    }
                ]
            },
            {
                "tool_calls": [
                    {
                        "name": "renderset.inspect",
                        "ok": True,
                        "arguments_preview": "{}",
                        "result_preview": (
                            '{"status": "needs_input", '
                            '"blocking_ambiguities": [{"kind": "missing_region_camera", "target": "区域一"}], '
                            '"warnings": [{"kind": "skipped_front_layer_parent_contains_objects", "target": "区域二/动物路标"}], '
                            '"created": [], "updated": [], "migrated": [], "skipped": [], "failed": [], '
                            '"duplicate_contexts": [], "unmatched_contexts": [], '
                            '"validation_results": [], "saved": false, "render_started": false}'
                        ),
                    }
                ]
            },
        ],
        "summary": {"tool_count": 2},
    }

    answer = mod.fallback_answer_for_trace(
        trace,
        error_kind="model_final_timeout",
        error_message="final model turn timed out",
    )

    assert answer is not None
    assert "model_final_timeout" in answer
    assert "renderset.inspect" in answer
    assert "missing_region_camera" in answer
    assert "区域一" in answer
    assert "skipped_front_layer_parent_contains_objects" in answer
    assert "created: []" in answer
    assert "updated: []" in answer
    assert "migrated: []" in answer
    assert "failed: []" in answer
    assert "saved: false" in answer
    assert "render_started: false" in answer


def test_fallback_refuses_trace_with_forbidden_renderset_followup():
    mod = _load_module()
    trace = {
        "iterations": [
            {
                "tool_calls": [
                    {
                        "name": "renderset.inspect",
                        "ok": True,
                        "result_preview": '{"status": "needs_input"}',
                    },
                    {
                        "name": "dev.run_python",
                        "ok": True,
                        "result_preview": "{}",
                    },
                ]
            }
        ]
    }

    assert mod.fallback_answer_for_trace(trace, error_kind="timeout") is None


def test_execution_trace_keeps_bounded_renderset_result_for_fallback():
    path = ROOT / "agent_core" / "execution_trace.py"
    spec = importlib.util.spec_from_file_location("popagent_execution_trace_test", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    trace = module.create_trace()
    iteration = module.record_iteration(
        trace,
        index=0,
        stream=False,
        latency_ms=1,
        status_code=200,
        finish_reason="tool_calls",
    )
    module.record_tool_call(
        trace,
        iteration,
        name="renderset.inspect",
        arguments={},
        result={
            "status": "needs_input",
            "blocking_ambiguities": [
                {"kind": "missing_region_camera", "target": f"区域{i}"}
                for i in range(30)
            ],
            "saved": False,
            "render_started": False,
            "extra_large_key": "not needed",
        },
    )

    call = trace["iterations"][0]["tool_calls"][0]
    assert call["result"]["status"] == "needs_input"
    assert len(call["result"]["blocking_ambiguities"]) == 20
    assert call["result"]["saved"] is False
    assert call["result"]["render_started"] is False
    assert "extra_large_key" not in call["result"]


def test_operator_agent_loop_wires_fallback_and_bounded_tool_followup_timeout():
    text = (ROOT / "operators" / "operator_ask.py").read_text(encoding="utf-8")

    assert "fallback_answer_for_trace" in text
    assert "_finish_agent_with_fallback" in text
    assert "record_abort(trace, error_kind)" in text
    assert 'agent_status="INTERRUPTED"' in text
    assert "return min(timeout, 90.0)" in text


def run():
    for name, value in sorted(globals().items()):
        if name.startswith("test_") and callable(value):
            value()
    print("test_agent_fallback_answers OK")


if __name__ == "__main__":
    run()
