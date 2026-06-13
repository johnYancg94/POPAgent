import importlib.util
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_activate_tool_schema_and_metadata():
    registry = _load_module(
        "popagent_agent_skill_registry_dependency",
        "agent_core/agent_skill_registry.py",
    )
    fake_agent_core = types.ModuleType("agent_core")
    fake_agent_core.agent_skill_registry = registry
    sys.modules["agent_core"] = fake_agent_core
    module = _load_module(
        "popagent_agent_skill_activation",
        "builtin_skills/agent_skill_activation.py",
    )
    tool = module.ACTIVATE_AGENT_SKILL

    assert tool["name"] == "agent.activate_skill"
    assert tool["owner"] == "builtin.agent-skills"
    assert tool["parameters"]["required"] == ["name"]
    assert tool["metadata"]["modifies_scene"] is False
    assert tool["metadata"]["writes_files"] is False
    assert tool["metadata"]["requires_confirmation"] == "never"
    assert tool["metadata"]["requires_main_thread"] is False


def test_active_instruction_rendering_is_deduplicated():
    registry = _load_module(
        "popagent_agent_skill_registry_for_activation",
        "agent_core/agent_skill_registry.py",
    )
    active = registry.ActiveAgentSkills()
    record = {
        "name": "sample-skill",
        "description": "sample",
        "source": "bundled:tests",
        "location": "C:/skills/sample-skill/SKILL.md",
        "root": "C:/skills/sample-skill",
        "body": "# Sample\n\nFollow this.",
    }

    assert active.add(record) is True
    assert active.add(record) is False
    rendered = active.render_instructions()
    assert rendered.count("# Sample") == 1
    assert "sample-skill" in rendered


def test_operator_refreshes_catalog_and_persists_active_instructions():
    operator_text = (ROOT / "operators" / "operator_ask.py").read_text(
        encoding="utf-8"
    )

    assert "agent_skill_registry.registry.refresh(blend_file=blend_file)" in operator_text
    assert "agent_skill_registry.registry.render_catalog()" in operator_text
    assert "active_agent_skills = agent_skill_registry.ActiveAgentSkills()" in operator_text
    assert "active_agent_skills.render_instructions()" in operator_text
    assert 'tc.name == "agent.activate_skill"' in operator_text


def run():
    test_activate_tool_schema_and_metadata()
    test_active_instruction_rendering_is_deduplicated()
    test_operator_refreshes_catalog_and_persists_active_instructions()
    print("test_agent_skill_activation OK")


if __name__ == "__main__":
    run()
