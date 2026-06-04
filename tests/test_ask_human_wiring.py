import importlib.util, pathlib
_ROOT = pathlib.Path(__file__).resolve().parents[1]

def test_handler_timeout_recognizes_awaits_user():
    src = (_ROOT / "agent_core/executor.py").read_text(encoding="utf-8")
    assert 'meta.get("awaits_user")' in src
    assert "_LONG_RUNNING_HANDLER_TIMEOUT" in src
