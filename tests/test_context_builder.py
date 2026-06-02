"""Pure Python tests for compact live Blender context formatting."""

from pathlib import Path
import importlib.util
import sys
import types


ROOT = Path(__file__).resolve().parents[1]

pkg = types.ModuleType("popagent_context_test")
pkg.__path__ = [str(ROOT)]
sys.modules["popagent_context_test"] = pkg

agent_pkg = types.ModuleType("popagent_context_test.agent_core")
agent_pkg.__path__ = [str(ROOT / "agent_core")]
sys.modules["popagent_context_test.agent_core"] = agent_pkg

main_thread = types.ModuleType("popagent_context_test.agent_core.main_thread")
main_thread.run_on_main = lambda _fn, *args, **kwargs: None
sys.modules["popagent_context_test.agent_core.main_thread"] = main_thread

skill_registry = types.ModuleType("popagent_context_test.agent_core.skill_registry")
skill_registry.all_skills = lambda: []
sys.modules["popagent_context_test.agent_core.skill_registry"] = skill_registry

spec = importlib.util.spec_from_file_location(
    "popagent_context_test.agent_core.context_builder",
    ROOT / "agent_core" / "context_builder.py",
)
context_builder = importlib.util.module_from_spec(spec)
sys.modules["popagent_context_test.agent_core.context_builder"] = context_builder
spec.loader.exec_module(context_builder)


def test_format_snapshot_includes_color_management_and_object_count():
    text = context_builder._format_snapshot(
        {
            "scene_name": "Scene",
            "mode": "OBJECT",
            "frame": 1,
            "active": {"name": "Cube", "type": "MESH"},
            "selected_count": 1,
            "selected_sample": ["Cube"],
            "object_count": 3,
            "collections": ["Collection"],
            "color_management": {
                "display": "sRGB",
                "view_transform": "ACES 1.3",
                "look": "None",
                "exposure": 0.0,
                "gamma": 1.0,
                "sequencer": "sRGB",
            },
        },
        owners=[],
    )

    assert "objects=3" in text
    assert "color_management:" in text
    assert "display=sRGB" in text
    assert "view_transform=ACES 1.3" in text
    assert "sequencer=sRGB" in text


def run():
    test_format_snapshot_includes_color_management_and_object_count()
    print("test_context_builder OK")
    return True


if __name__ == "__main__":
    run()
