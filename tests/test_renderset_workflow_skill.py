"""Tests for the bundled RenderSet Pro Agent Skill package."""

import importlib.util
import os
import sys
from pathlib import Path


ROOT = Path(os.environ.get("POPAGENT_ROOT", str(Path(__file__).resolve().parents[1])))


def _load_registry():
    path = ROOT / "agent_core" / "agent_skill_registry.py"
    spec = importlib.util.spec_from_file_location("popagent_renderset_registry", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _discover():
    module = _load_registry()
    state = module.AgentSkillRegistry()
    state.register_bundled_root("popagent", ROOT / "builtin_skills" / "resources")
    state.refresh(user_home=ROOT / "tests" / "_no_user_skills", blend_file="")
    return state


def test_renderset_skill_is_discovered_from_bundled_root():
    record = _discover().get("prepare-renderset-contexts")

    assert record is not None
    assert record["source"] == "bundled:popagent"
    assert record["compatibility"].startswith("Blender 5.1+")
    assert record["metadata"] == {
        "author": "t7597-team",
        "version": "2.4.0",
    }
    assert "Never click `Render All`" in record["body"]
    assert "`renderset.prepare`" in record["body"]
    assert "`mcp__blender.execute_blender_code`" in record["body"]
    assert "POPAgent.builtin_skills.renderset_tools" in record["body"]
    assert "⚠️" in record["body"]
    assert "dev.run_python" in record["body"]


def test_renderset_references_are_activatable():
    state = _discover()

    contexts = state.activate(
        "prepare-renderset-contexts",
        "references/context-rules.md",
    )
    settings = state.activate(
        "prepare-renderset-contexts",
        "references/render-settings.md",
    )
    validation = state.activate(
        "prepare-renderset-contexts",
        "references/validation-and-reporting.md",
    )
    assert "One combined context per region" in contexts["content"]
    assert "material_override" in settings["content"]
    assert "100 / 0.005" in validation["content"]
    assert "## ⚠️ 裁切区域异常建筑" in validation["content"]


def test_renderset_openai_metadata_has_default_prompt():
    metadata = (
        ROOT
        / "builtin_skills"
        / "resources"
        / "prepare-renderset-contexts"
        / "agents"
        / "openai.yaml"
    ).read_text(encoding="utf-8")

    assert "display_name:" in metadata
    assert "short_description:" in metadata
    assert "default_prompt:" in metadata


def test_native_renderset_callable_tools_are_wired():
    init_text = (ROOT / "builtin_skills" / "__init__.py").read_text(encoding="utf-8")

    assert "RENDERSET_INSPECT" in init_text
    assert "RENDERSET_PREPARE" in init_text
    assert "RENDERSET_AUDIT" in init_text
    assert (ROOT / "builtin_skills" / "renderset_tools.py").exists()


def run():
    test_renderset_skill_is_discovered_from_bundled_root()
    test_renderset_references_are_activatable()
    test_renderset_openai_metadata_has_default_prompt()
    test_native_renderset_callable_tools_are_wired()
    print("test_renderset_workflow_skill OK")


if __name__ == "__main__":
    run()
