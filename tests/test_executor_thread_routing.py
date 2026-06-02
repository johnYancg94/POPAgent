"""Pure Python tests for executor main-thread routing policy."""

from pathlib import Path
import asyncio
import importlib.util
import sys
import types


ROOT = Path(__file__).resolve().parents[1]

pkg = types.ModuleType("popagent_test")
pkg.__path__ = [str(ROOT)]
sys.modules["popagent_test"] = pkg

agent_pkg = types.ModuleType("popagent_test.agent_core")
agent_pkg.__path__ = [str(ROOT / "agent_core")]
sys.modules["popagent_test.agent_core"] = agent_pkg

providers_pkg = types.ModuleType("popagent_test.providers")
providers_pkg.__path__ = [str(ROOT / "providers")]
sys.modules["popagent_test.providers"] = providers_pkg


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


base = _load("popagent_test.providers.base", ROOT / "providers" / "base.py")
skill_registry = _load("popagent_test.agent_core.skill_registry", ROOT / "agent_core" / "skill_registry.py")
schema_validation = _load("popagent_test.agent_core.schema_validation", ROOT / "agent_core" / "schema_validation.py")

main_thread = types.ModuleType("popagent_test.agent_core.main_thread")
main_thread.run_on_main = lambda _fn, *args, **kwargs: None
sys.modules["popagent_test.agent_core.main_thread"] = main_thread

confirm_dialog = types.ModuleType("popagent_test.agent_core.confirm_dialog")

async def _approve(_skill, _args):
    return {"approved": True}

confirm_dialog.ask_confirmation = _approve
sys.modules["popagent_test.agent_core.confirm_dialog"] = confirm_dialog

executor = _load("popagent_test.agent_core.executor", ROOT / "agent_core" / "executor.py")


ToolCallRaw = base.ToolCallRaw


def _register_skill(name, handler, metadata):
    skill_registry.clear_all()
    skill_registry.register_skill(
        {
            "name": name,
            "description": "",
            "parameters": {"type": "object", "properties": {}},
            "owner": "test",
            "handler": handler,
            "metadata": metadata,
        }
    )


def test_executor_defaults_to_main_thread_dispatch():
    calls = []

    def fake_run_on_main(fn, *args, **kwargs):
        calls.append(("main", fn.__name__))
        future = asyncio.get_running_loop().create_future()
        future.set_result(fn(*args, **kwargs))
        return future

    def handler(context=None):
        return {"ok": True, "route": "main"}

    original = executor.run_on_main
    executor.run_on_main = fake_run_on_main
    try:
        _register_skill("test.main", handler, {"requires_confirmation": "never"})
        result = asyncio.run(executor.run(ToolCallRaw(id="1", name="test.main", arguments={}), None))
    finally:
        executor.run_on_main = original
        skill_registry.clear_all()

    assert result["route"] == "main"
    assert calls == [("main", "handler")]


def test_executor_can_run_declared_background_skill_off_main_thread():
    calls = []

    def fake_run_on_main(fn, *args, **kwargs):
        calls.append(("main", fn.__name__))
        future = asyncio.get_running_loop().create_future()
        future.set_result(fn(*args, **kwargs))
        return future

    def handler(context=None):
        return {"ok": True, "route": "background"}

    original = executor.run_on_main
    executor.run_on_main = fake_run_on_main
    try:
        _register_skill(
            "test.background",
            handler,
            {"requires_confirmation": "never", "requires_main_thread": False},
        )
        result = asyncio.run(executor.run(ToolCallRaw(id="1", name="test.background", arguments={}), None))
    finally:
        executor.run_on_main = original
        skill_registry.clear_all()

    assert result["route"] == "background"
    assert calls == []


def run():
    test_executor_defaults_to_main_thread_dispatch()
    test_executor_can_run_declared_background_skill_off_main_thread()
    print("test_executor_thread_routing OK")
    return True


if __name__ == "__main__":
    run()
