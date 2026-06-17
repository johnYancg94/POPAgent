from pathlib import Path
import importlib.util


ROOT = Path(__file__).resolve().parents[1]
PROPERTIES = ROOT / "properties" / "properties.py"
PANEL_OUTPUT = ROOT / "panels" / "panel_output.py"
ANSWER_VIEW = ROOT / "operators" / "operator_answer_view.py"
INIT = ROOT / "__init__.py"
PROCESS_EVENTS = ROOT / "agent_core" / "process_events.py"


def test_answer_process_properties_exist():
    text = PROPERTIES.read_text(encoding="utf-8")
    assert "agent_process_events_json" in text
    assert "agent_process_collapsed" in text


def test_answer_process_ui_wiring_exists():
    panel = PANEL_OUTPUT.read_text(encoding="utf-8")
    answer_view = ANSWER_VIEW.read_text(encoding="utf-8")
    init_text = INIT.read_text(encoding="utf-8")

    assert "draw_agent_process" in panel
    assert "elif props.agent_process_events_json" in panel
    assert "CHAT_COMPANION_OT_toggle_agent_process" in answer_view
    assert "CHAT_COMPANION_OT_toggle_agent_process" in init_text


def test_trace_can_be_summarized_as_process_steps():
    spec = importlib.util.spec_from_file_location("process_events", PROCESS_EVENTS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    trace = {
        "version": 2,
        "iterations": [
            {
                "index": 0,
                "latency_ms": 120,
                "status_code": 200,
                "finish_reason": "tool_calls",
                "tool_calls": [
                    {
                        "name": "dev.run_python",
                        "ok": True,
                        "duration_ms": 42,
                        "error_kind": "",
                    }
                ],
            }
        ],
        "summary": {"tool_count": 1, "error_count": 0, "aborted": False},
    }

    events = module.events_from_trace(trace)

    assert events[0]["message"] == "Iter 0 planned next step (120 ms)"
    assert events[1]["message"] == "Finished: dev.run_python (42 ms)"
    assert events[1]["icon"] == "CHECKMARK"


def run():
    test_answer_process_properties_exist()
    test_answer_process_ui_wiring_exists()
    test_trace_can_be_summarized_as_process_steps()
    print("test_answer_process_ui OK")
    return True


if __name__ == "__main__":
    run()
