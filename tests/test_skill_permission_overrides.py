"""Pure Python tests for skill confirmation permission overrides."""

from pathlib import Path
import importlib.util
import sys


ROOT = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location(
    "skill_registry", ROOT / "agent_core" / "skill_registry.py"
)
skill_registry = importlib.util.module_from_spec(spec)
sys.modules["skill_registry"] = skill_registry
spec.loader.exec_module(skill_registry)


class FakePrefs:
    def __init__(self, raw: str, quick_permission_preset: str = "DEFAULT"):
        self.skill_permission_overrides_json = raw
        self.quick_permission_preset = quick_permission_preset


def make_skill():
    return {
        "owner": "test.owner",
        "name": "do_work",
        "description": "test skill",
        "parameters": {},
        "handler": lambda **kwargs: kwargs,
        "metadata": {"requires_confirmation": "first"},
    }


def test_permission_level_uses_skill_metadata_by_default():
    skill_registry.clear_all()
    skill = make_skill()
    skill_registry.register_skill(skill)

    assert skill_registry.get_permission_level(skill) == "first"


def test_permission_override_can_change_and_reset_to_preset():
    skill_registry.clear_all()
    skill = make_skill()
    skill_registry.register_skill(skill)

    skill_registry.set_permission_override("test.owner", "do_work", "always")
    assert skill_registry.get_permission_level(skill) == "always"

    skill_registry.clear_permission_overrides()
    assert skill_registry.get_permission_level(skill) == "first"


def test_permission_level_can_read_persistent_preferences_json():
    skill_registry.clear_all()
    skill = make_skill()
    prefs = FakePrefs('{"test.owner::do_work": "never"}')

    assert skill_registry.get_permission_level(skill, prefs=prefs) == "never"


def test_auto_quick_permission_preset_allows_skill_without_confirmation():
    skill_registry.clear_all()
    skill = make_skill()
    prefs = FakePrefs("{}", quick_permission_preset="AUTO")

    assert skill_registry.get_permission_level(skill, prefs=prefs) == "never"


def test_auto_quick_permission_preset_takes_priority_over_json():
    skill_registry.clear_all()
    skill = make_skill()
    prefs = FakePrefs(
        '{"test.owner::do_work": "always"}',
        quick_permission_preset="AUTO",
    )

    assert skill_registry.get_permission_level(skill, prefs=prefs) == "never"


def run():
    test_permission_level_uses_skill_metadata_by_default()
    test_permission_override_can_change_and_reset_to_preset()
    test_permission_level_can_read_persistent_preferences_json()
    test_auto_quick_permission_preset_allows_skill_without_confirmation()
    test_auto_quick_permission_preset_takes_priority_over_json()
    print("test_skill_permission_overrides OK")
    return True


if __name__ == "__main__":
    run()
