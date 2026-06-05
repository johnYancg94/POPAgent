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
