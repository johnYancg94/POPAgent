"""Static guards for developer-mode-only diagnostics."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_preferences_define_developer_mode_and_skill_override_storage():
    text = (ROOT / "properties" / "addon_preferences.py").read_text(encoding="utf-8")

    assert "developer_mode" in text
    assert "skill_permission_overrides_json" in text


def test_answer_execution_trace_is_gated_by_developer_mode():
    text = (ROOT / "panels" / "panel_output.py").read_text(encoding="utf-8")

    assert "developer_mode" in text
    assert "draw_selected_execution_trace" in text


def test_error_traceback_details_are_gated_by_developer_mode():
    text = (ROOT / "panels" / "panel_output.py").read_text(encoding="utf-8")

    assert "draw_error_details" in text
    assert "developer_mode" in text


def test_usage_panel_has_compact_non_developer_summary():
    text = (ROOT / "panels" / "panel_tokens.py").read_text(encoding="utf-8")

    assert "developer_mode" in text
    assert "_draw_compact_summary" in text
    assert "Total tokens" in text
    assert "RMB cost" in text


def run():
    test_preferences_define_developer_mode_and_skill_override_storage()
    test_answer_execution_trace_is_gated_by_developer_mode()
    test_error_traceback_details_are_gated_by_developer_mode()
    test_usage_panel_has_compact_non_developer_summary()
    print("test_developer_mode_wiring OK")
    return True


if __name__ == "__main__":
    run()
