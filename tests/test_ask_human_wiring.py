import importlib.util, pathlib
_ROOT = pathlib.Path(__file__).resolve().parents[1]

def test_handler_timeout_recognizes_awaits_user():
    src = (_ROOT / "agent_core/executor.py").read_text(encoding="utf-8")
    assert 'meta.get("awaits_user")' in src
    assert "_LONG_RUNNING_HANDLER_TIMEOUT" in src


def test_ask_human_skill_definition():
    src = (_ROOT / "builtin_skills/agent_interact.py").read_text(encoding="utf-8")
    assert '"name": "agent.ask_human"' in src
    assert '"awaits_user": True' in src
    assert '"requires_confirmation": "never"' in src
    assert '"requires_main_thread": False' in src
    assert '"owner": "builtin.agent"' in src

def test_ask_human_registered_in_builtins():
    src = (_ROOT / "builtin_skills/__init__.py").read_text(encoding="utf-8")
    assert "ASK_HUMAN" in src


def test_ask_human_uses_single_full_readable_dialog():
    src = (_ROOT / "agent_core/ask_human_dialog.py").read_text(encoding="utf-8")

    assert "event_simulate" not in src
    assert "EnumProperty" not in src
    assert "invoke_search_popup(self)" not in src
    assert "invoke_popup(self, width=460)" not in src
    assert "invoke_props_dialog(self, width=560)" in src
    assert 'col.label(text="或自由输入（点击 OK 提交）:")' in src
    assert "POPAGENT_OT_ask_human_custom" not in src
    assert "POPAGENT_OT_ask_human_confirm_option" not in src
    assert "POPAGENT_OT_ask_human_pick" in src


def test_option_dialog_wraps_full_option_text_and_keeps_click_targets_short():
    src = (_ROOT / "agent_core/ask_human_dialog.py").read_text(encoding="utf-8")

    assert "def _wrap_dialog_text(" in src
    assert 'box.label(text=f"选项 {index}:")' in src
    assert "_wrap_dialog_text(option)" in src
    assert 'box.operator("popagent.ask_human_pick", text="选择此项")' in src
    assert "op.value = option" in src


def test_options_are_passed_as_json_to_preserve_multiline_text():
    src = (_ROOT / "agent_core/ask_human_dialog.py").read_text(encoding="utf-8")

    assert "import json" in src
    assert "options_json: StringProperty" in src
    assert "def _dialog_options(" in src
    assert "json.loads(operator.options_json)" in src
    assert "json.dumps(options or [], ensure_ascii=False)" in src
