"""Static guards for the add-on preferences tab layout."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PREFERENCES = ROOT / "properties" / "addon_preferences.py"


def test_preferences_define_function_tabs():
    text = PREFERENCES.read_text(encoding="utf-8")

    assert "preferences_tab: props.EnumProperty(" in text
    for tab_id in ("MODELS", "AGENT", "SKILLS", "INTERFACE", "LOGS", "SYSTEM"):
        assert f'("{tab_id}",' in text


def test_preferences_draw_only_dispatches_the_active_tab():
    text = PREFERENCES.read_text(encoding="utf-8")

    assert 'tabs.prop(self, "preferences_tab", expand=True)' in text
    assert "drawers[self.preferences_tab](layout, context)" in text


def test_tabs_keep_all_previously_visible_settings():
    text = PREFERENCES.read_text(encoding="utf-8")
    visible_settings = (
        "open_ai_api_key",
        "open_ai_base_url",
        "mimo_api_key",
        "mimo_base_url",
        "mimo_model",
        "deepseek_api_key",
        "deepseek_base_url",
        "minimax_api_key",
        "minimax_base_url",
        "minimax_model",
        "agent_context_1m_enabled",
        "text_width_adjust",
        "answer_display_mode",
        "answer_code_preview_lines",
        "agent_mode_enabled",
        "agent_max_iters",
        "max_history_context",
        "blender_api_docs_url",
        "blender_api_docs_path",
        "blender_api_docs_prefer_local",
        "web_search_enabled",
        "tavily_api_key",
        "tavily_endpoint",
        "trace_log_enabled",
        "trace_log_dir",
        "trace_log_full",
        "developer_mode",
        "use_streaming",
        "timeout",
        "quick_permission_preset",
    )

    for setting in visible_settings:
        assert setting in text


def test_home_tab_exposes_quick_permission_presets():
    text = PREFERENCES.read_text(encoding="utf-8")

    assert 'default="AUTO"' in text
    assert '"popagent.apply_quick_permission_preset"' in text
    assert '"默认权限"' in text
    assert '"自动权限"' in text


def run():
    test_preferences_define_function_tabs()
    test_preferences_draw_only_dispatches_the_active_tab()
    test_tabs_keep_all_previously_visible_settings()
    test_home_tab_exposes_quick_permission_presets()
    print("test_preferences_tabs OK")
    return True


if __name__ == "__main__":
    run()
