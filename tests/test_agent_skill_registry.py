import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load_module():
    path = ROOT / "agent_core" / "agent_skill_registry.py"
    spec = importlib.util.spec_from_file_location("popagent_agent_skill_registry", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_skill(root: Path, name: str, description: str, body: str = "# Body") -> Path:
    skill_dir = root / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        f"name: {name}\n"
        f"description: {description}\n"
        "license: MIT\n"
        "compatibility: Blender 5.1+\n"
        "metadata:\n"
        "  author: tests\n"
        'allowed-tools: "Read"\n'
        "---\n\n"
        f"{body}\n",
        encoding="utf-8",
    )
    return skill_dir


def test_parse_frontmatter_and_optional_fields(tmp_path):
    registry = _load_module()
    skill_dir = _write_skill(
        tmp_path,
        "valid-skill",
        "Use this skill when testing valid frontmatter.",
    )

    record, diagnostics = registry.parse_skill_file(
        skill_dir / "SKILL.md",
        source="bundled",
    )

    assert diagnostics == []
    assert record["name"] == "valid-skill"
    assert record["description"].startswith("Use this skill")
    assert record["license"] == "MIT"
    assert record["compatibility"] == "Blender 5.1+"
    assert record["metadata"] == {"author": "tests"}
    assert record["allowed_tools"] == "Read"
    assert record["body"] == "# Body"


def test_missing_description_and_unparseable_yaml_are_skipped(tmp_path):
    registry = _load_module()
    missing = tmp_path / "missing"
    missing.mkdir()
    (missing / "SKILL.md").write_text(
        "---\nname: missing\n---\n\nBody\n",
        encoding="utf-8",
    )
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "SKILL.md").write_text(
        "---\nname: [broken\n---\n\nBody\n",
        encoding="utf-8",
    )

    missing_record, missing_diagnostics = registry.parse_skill_file(
        missing / "SKILL.md",
        source="user",
    )
    broken_record, broken_diagnostics = registry.parse_skill_file(
        broken / "SKILL.md",
        source="user",
    )

    assert missing_record is None
    assert any(item["code"] == "missing_description" for item in missing_diagnostics)
    assert broken_record is None
    assert any(item["code"] == "invalid_yaml" for item in broken_diagnostics)


def test_quoted_and_multiline_yaml_values_are_supported(tmp_path):
    registry = _load_module()
    skill_dir = tmp_path / "multiline-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: multiline-skill\n"
        "description: |\n"
        "  Use this skill when: a multiline description is needed.\n"
        "  Preserve the second line.\n"
        'compatibility: "Blender: 5.1+"\n'
        "---\n\nBody\n",
        encoding="utf-8",
    )

    record, diagnostics = registry.parse_skill_file(
        skill_dir / "SKILL.md",
        source="user",
    )

    assert diagnostics == []
    assert "Preserve the second line." in record["description"]
    assert record["compatibility"] == "Blender: 5.1+"


def test_invalid_name_and_directory_mismatch_warn_but_load(tmp_path):
    registry = _load_module()
    skill_dir = tmp_path / "folder-name"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: Invalid_Name\n"
        "description: Use this skill for warning coverage.\n"
        "---\n\nBody\n",
        encoding="utf-8",
    )

    record, diagnostics = registry.parse_skill_file(
        skill_dir / "SKILL.md",
        source="project",
    )

    assert record["name"] == "Invalid_Name"
    codes = {item["code"] for item in diagnostics}
    assert "invalid_name" in codes
    assert "name_directory_mismatch" in codes


def test_discovery_precedence_and_dynamic_refresh(tmp_path):
    registry = _load_module()
    bundled = tmp_path / "bundled"
    user = tmp_path / "home" / ".agents" / "skills"
    project = tmp_path / "project" / ".agents" / "skills"
    _write_skill(bundled, "shared-skill", "bundled description")
    _write_skill(user, "shared-skill", "user description")
    _write_skill(project, "shared-skill", "project description")
    _write_skill(bundled, "_template", "must be skipped")
    _write_skill(bundled, ".hidden", "must be skipped")

    state = registry.AgentSkillRegistry()
    state.register_bundled_root("tests", bundled)
    state.refresh(user_home=tmp_path / "home", blend_file=tmp_path / "project" / "a.blend")

    assert state.get("shared-skill")["description"] == "project description"
    assert state.get("_template") is None
    assert state.get(".hidden") is None
    assert any(item["code"] == "name_collision" for item in state.diagnostics())

    (project / "shared-skill" / "SKILL.md").write_text(
        "---\nname: shared-skill\n"
        "description: refreshed project description\n---\n\nUpdated\n",
        encoding="utf-8",
    )
    state.refresh(user_home=tmp_path / "home", blend_file=tmp_path / "project" / "a.blend")
    assert state.get("shared-skill")["description"] == "refreshed project description"


def test_unsaved_blend_does_not_scan_project_skills(tmp_path):
    registry = _load_module()
    user = tmp_path / "home" / ".agents" / "skills"
    project = tmp_path / "project" / ".agents" / "skills"
    _write_skill(user, "shared-skill", "user description")
    _write_skill(project, "shared-skill", "project description")

    state = registry.AgentSkillRegistry()
    state.refresh(user_home=tmp_path / "home", blend_file="")

    assert state.get("shared-skill")["description"] == "user description"


def test_catalog_contains_metadata_not_body(tmp_path):
    registry = _load_module()
    root = tmp_path / "skills"
    _write_skill(root, "catalog-skill", "catalog description", body="SECRET BODY")
    state = registry.AgentSkillRegistry()
    state.register_bundled_root("tests", root)
    state.refresh(user_home=tmp_path / "empty-home", blend_file="")

    catalog = state.render_catalog()

    assert "catalog-skill" in catalog
    assert "catalog description" in catalog
    assert "bundled:tests" in catalog
    assert "SECRET BODY" not in catalog


def test_activation_reads_body_and_safe_resources(tmp_path):
    registry = _load_module()
    root = tmp_path / "skills"
    skill_dir = _write_skill(root, "activate-skill", "activation description")
    references = skill_dir / "references"
    references.mkdir()
    (references / "guide.md").write_text("guide text", encoding="utf-8")
    assets = skill_dir / "assets"
    assets.mkdir()
    (assets / "data.bin").write_bytes(b"\x00\x01\x02")

    state = registry.AgentSkillRegistry(max_resource_bytes=64)
    state.register_bundled_root("tests", root)
    state.refresh(user_home=tmp_path / "empty-home", blend_file="")

    first = state.activate("activate-skill")
    text_resource = state.activate("activate-skill", "references/guide.md")
    binary_resource = state.activate("activate-skill", "assets/data.bin")

    assert first["ok"] is True
    assert first["body"] == "# Body"
    assert "references/guide.md" in first["resources"]
    assert text_resource["content"] == "guide text"
    assert binary_resource["binary"] is True
    assert "content" not in binary_resource


def test_activation_rejects_escape_unknown_and_oversized_resources(tmp_path):
    registry = _load_module()
    root = tmp_path / "skills"
    skill_dir = _write_skill(root, "safe-skill", "safety description")
    (skill_dir / "large.txt").write_text("x" * 20, encoding="utf-8")
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")

    state = registry.AgentSkillRegistry(max_resource_bytes=10)
    state.register_bundled_root("tests", root)
    state.refresh(user_home=tmp_path / "empty-home", blend_file="")

    assert state.activate("missing")["error_kind"] == "agent_skill_not_found"
    assert state.activate("safe-skill", "../outside.txt")["error_kind"] == "invalid_resource_path"
    assert state.activate("safe-skill", "missing.txt")["error_kind"] == "resource_not_found"
    assert state.activate("safe-skill", "large.txt")["error_kind"] == "resource_too_large"


def run():
    import tempfile

    tests = [
        test_parse_frontmatter_and_optional_fields,
        test_missing_description_and_unparseable_yaml_are_skipped,
        test_quoted_and_multiline_yaml_values_are_supported,
        test_invalid_name_and_directory_mismatch_warn_but_load,
        test_discovery_precedence_and_dynamic_refresh,
        test_unsaved_blend_does_not_scan_project_skills,
        test_catalog_contains_metadata_not_body,
        test_activation_reads_body_and_safe_resources,
        test_activation_rejects_escape_unknown_and_oversized_resources,
    ]
    for test in tests:
        with tempfile.TemporaryDirectory() as tmp:
            test(Path(tmp))
    print("test_agent_skill_registry OK")


if __name__ == "__main__":
    run()
