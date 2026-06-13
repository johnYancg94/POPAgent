import importlib.util
import sys
from pathlib import Path


POPAGENT_ROOT = Path(__file__).resolve().parents[1]
POPTOOLS_ROOT = POPAGENT_ROOT.parent / "poptools"
EXPECTED = {
    "poptools-export-assets": (
        "poptools.export_fbx",
        "poptools.export_obj",
        "poptools.export_gltf",
        "poptools.export_obj_batch",
        "poptools.open_export_dir",
    ),
    "poptools-name-assets": (
        "poptools.apply_action_naming",
        "poptools.apply_generic_naming",
        "poptools.preview_generic_names",
        "poptools.build_texture_name",
        "poptools.retex_name_from_active",
        "poptools.adjust_serial_number",
    ),
    "poptools-retex-workflow": (
        "poptools.check_uvs",
        "poptools.smart_rename",
        "poptools.organize_materials",
        "poptools.mark_high_low",
        "poptools.rename_by_category",
        "poptools.set_texname_of_object",
        "poptools.sync_texture_names",
    ),
    "poptools-marmoset-workflow": (
        "poptools.auto_mark_high_low",
        "poptools.show_polycount",
        "poptools.find_missing_textures",
        "poptools.generate_lowpoly",
        "poptools.secure_texture_resources",
        "poptools.auto_detect_toolbag",
    ),
    "poptools-vertex-baker": (
        "poptools.vtbb_create_empties",
        "poptools.vtbb_bind_vertices",
        "poptools.vtbb_bake_weights",
        "poptools.vtbb_clear_empties",
    ),
}


def _load_registry():
    path = POPAGENT_ROOT / "agent_core" / "agent_skill_registry.py"
    spec = importlib.util.spec_from_file_location("poptools_package_registry", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_poptools_workflow_skills_are_valid_and_cover_tools():
    module = _load_registry()
    state = module.AgentSkillRegistry()
    root = POPTOOLS_ROOT / "agent_skills" / "resources"
    state.register_bundled_root("poptools", root)
    state.refresh(user_home=POPTOOLS_ROOT / "tests" / "_no_user_skills", blend_file="")

    assert {record["name"] for record in state.all()} == set(EXPECTED)
    assert not [
        item
        for item in state.diagnostics()
        if item["code"] in {
            "invalid_name",
            "name_directory_mismatch",
            "invalid_yaml",
            "missing_description",
        }
    ]
    for name, tool_names in EXPECTED.items():
        record = state.get(name)
        for tool_name in tool_names:
            assert tool_name in record["body"], f"{name} does not mention {tool_name}"


def test_poptools_registers_bundled_agent_skill_root():
    init_text = (POPTOOLS_ROOT / "agent_skills" / "__init__.py").read_text(
        encoding="utf-8"
    )

    assert "agent_skill_registry" in init_text
    assert 'register_bundled_root("poptools"' in init_text
    assert 'unregister_bundled_root("poptools")' in init_text


def test_poptools_conventions_distinguish_skills_from_callable_tools():
    conventions = (POPTOOLS_ROOT / "agent_skills" / "CONVENTIONS.md").read_text(
        encoding="utf-8"
    )

    assert "Callable Tool" in conventions
    assert "Agent Skill" in conventions
    assert "SKILL.md" in conventions


def test_poptools_build_does_not_exclude_agent_skill_resources():
    manifest = (POPTOOLS_ROOT / "blender_manifest.toml").read_text(encoding="utf-8")
    package_script = (POPTOOLS_ROOT / "create_package.py").read_text(encoding="utf-8")

    assert "agent_skills/resources" not in manifest
    assert "agent_skills/resources" not in package_script


def run():
    test_poptools_workflow_skills_are_valid_and_cover_tools()
    test_poptools_registers_bundled_agent_skill_root()
    test_poptools_conventions_distinguish_skills_from_callable_tools()
    test_poptools_build_does_not_exclude_agent_skill_resources()
    print("test_poptools_agent_skills_packages OK")


if __name__ == "__main__":
    run()
