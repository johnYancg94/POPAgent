import importlib.util, pathlib
_ROOT = pathlib.Path(__file__).resolve().parents[1]

def _load(mod_name, rel_path):
    spec = importlib.util.spec_from_file_location(mod_name, _ROOT / rel_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

triage = _load("popagent_skill_triage", "agent_core/skill_triage.py")

def _skill(name, owner, desc="d"):
    return {"name": name, "owner": owner, "description": desc,
            "metadata": {}, "parameters": {}}

def test_should_triage_threshold():
    assert triage.should_triage(61, 60) is True
    assert triage.should_triage(60, 60) is False
    assert triage.should_triage(57, 60) is False

def test_partition_below_threshold_exposes_all():
    skills = [_skill(f"s{i}", "poptools") for i in range(10)]
    exposed, catalog = triage.partition_skills(skills, threshold=60)
    assert len(exposed) == 10
    assert catalog == []

def test_partition_above_threshold_splits_core_and_catalog():
    core = [_skill("agent.list_skills", "builtin.agent"),
            _skill("blender.query_scene", "builtin.query")]
    extra = [_skill(f"poptools.x{i}", "poptools") for i in range(70)]
    exposed, catalog = triage.partition_skills(core + extra, threshold=60)
    exposed_names = {s["name"] for s in exposed}
    assert "agent.list_skills" in exposed_names
    assert "blender.query_scene" in exposed_names
    assert all(s["name"].startswith("poptools") for s in catalog)
    assert len(catalog) == 70

def test_render_catalog_groups_by_owner():
    catalog = [_skill("poptools.a", "poptools", "export a"),
               _skill("poptools.b", "poptools", "export b")]
    text = triage.render_catalog(catalog)
    assert "poptools" in text
    assert "poptools.a" in text and "export a" in text
    assert "list_skills" in text

def test_core_names_are_known_skills():
    assert "agent.list_skills" in triage.CORE_SKILL_NAMES
    assert "agent.ask_human" in triage.CORE_SKILL_NAMES
    assert "renderset.inspect" in triage.CORE_SKILL_NAMES
    assert "renderset.prepare" in triage.CORE_SKILL_NAMES
    assert "renderset.audit" in triage.CORE_SKILL_NAMES

def test_default_threshold_off_for_real_registered_count():
    # Real registry: 33 builtin + 28 poptools = 61 skills. With multimodal ON
    # the screenshot skill stays, so the count the operator triages on can be
    # the full 61. The default must keep triage OFF with margin, not flip on a
    # single new skill or a multimodal toggle.
    real_count = 61
    assert triage.DEFAULT_TRIAGE_THRESHOLD >= real_count
    assert triage.should_triage(real_count, triage.DEFAULT_TRIAGE_THRESHOLD) is False
