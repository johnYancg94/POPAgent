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


def test_quick_pick_uses_native_search_popup():
    src = (_ROOT / "agent_core/ask_human_dialog.py").read_text(encoding="utf-8")

    assert "event_simulate" not in src
    assert "EnumProperty" in src
    assert 'bl_property = "choice"' in src
    assert "invoke_search_popup(self)" in src
    assert "invoke_popup(self, width=460)" not in src
    assert "invoke_props_dialog(self, width=460)" in src
    assert '"__CUSTOM__", "自由输入..."' in src
    assert "POPAGENT_OT_ask_human_pick" not in src
