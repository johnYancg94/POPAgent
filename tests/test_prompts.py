import importlib.util, pathlib

_ROOT = pathlib.Path(__file__).resolve().parents[1]

def _load(mod_name, rel_path):
    spec = importlib.util.spec_from_file_location(mod_name, _ROOT / rel_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

prompts = _load("popagent_prompts", "agent_core/prompts.py")

def test_base_principles_nonempty():
    assert isinstance(prompts.BASE_PRINCIPLES, str)
    assert "POPAgent" in prompts.BASE_PRINCIPLES


def test_all_rules_present():
    for const in ("RULE_LIVE_STATE", "RULE_PYTHON_API", "RULE_NODE_EXPERT",
                  "RULE_WEB_SEARCH", "RULE_PLANNING", "RULE_EVIDENCE",
                  "RULE_VISION_ENABLED", "RULE_VISION_DISABLED"):
        assert getattr(prompts, const).strip(), f"{const} empty"


def test_vision_rules_distinct():
    assert prompts.RULE_VISION_ENABLED != prompts.RULE_VISION_DISABLED
    assert "Multimodal" in prompts.RULE_VISION_DISABLED
    assert "viewport_screenshot" in prompts.RULE_VISION_ENABLED


def test_build_multimodal_on_includes_vision_enabled():
    out = prompts.build_system_prompt(base="BASE", multimodal=True)
    assert prompts.RULE_VISION_ENABLED in out
    assert prompts.RULE_VISION_DISABLED not in out
    assert "BASE" in out and prompts.RULE_EVIDENCE in out


def test_build_multimodal_off_includes_vision_disabled():
    out = prompts.build_system_prompt(base="BASE", multimodal=False)
    assert prompts.RULE_VISION_DISABLED in out
    assert prompts.RULE_VISION_ENABLED not in out


def test_build_appends_scene_summary_and_catalog():
    out = prompts.build_system_prompt(
        base="BASE", multimodal=False,
        scene_summary="SCENE_X", skill_catalog="CATALOG_Y")
    assert "SCENE_X" in out and "CATALOG_Y" in out


def test_build_omits_empty_optional_sections():
    out = prompts.build_system_prompt(base="BASE", multimodal=False)
    # 空 scene_summary / catalog 不应留下空段
    assert "\n\n\n" not in out


def test_ask_human_rule_present_and_wired():
    assert "agent.ask_human" in prompts.RULE_ASK_HUMAN
    out = prompts.build_system_prompt(base="BASE", multimodal=False)
    assert "agent.ask_human" in out


if __name__ == "__main__":
    # Standalone harness: pytest can't collect this file because importing the
    # POPAgent package triggers `import bpy` (see CLAUDE.md). The test itself
    # loads prompts.py by file path, so running this module directly works.
    import sys
    _fns = sorted(
        (n, f) for n, f in globals().items()
        if n.startswith("test_") and callable(f)
    )
    _passed = _failed = 0
    for _name, _fn in _fns:
        try:
            _fn()
        except Exception as _exc:  # noqa: BLE001
            _failed += 1
            print(f"FAIL {_name}: {type(_exc).__name__}: {_exc}")
        else:
            _passed += 1
            print(f"PASS {_name}")
    print(f"\n{_passed} passed, {_failed} failed")
    sys.exit(1 if _failed else 0)
