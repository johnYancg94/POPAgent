"""Static guards for skill permission controls."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_confirm_dialog_uses_permission_helper():
    text = (ROOT / "agent_core" / "confirm_dialog.py").read_text(encoding="utf-8")

    assert "get_permission_level" in text


def test_skill_panel_exposes_permission_controls_in_developer_mode():
    text = (ROOT / "panels" / "panel_skills.py").read_text(encoding="utf-8")

    assert "developer_mode" in text
    assert "popagent.set_skill_permission" in text
    assert "popagent.reset_skill_permissions" in text


def test_skill_permission_operators_are_registered():
    operators = (ROOT / "operators" / "operator_skills.py").read_text(encoding="utf-8")
    init = (ROOT / "__init__.py").read_text(encoding="utf-8")

    assert "POPAGENT_OT_set_skill_permission" in operators
    assert "POPAGENT_OT_reset_skill_permissions" in operators
    assert "POPAGENT_OT_apply_quick_permission_preset" in operators
    assert "POPAGENT_OT_set_skill_permission" in init
    assert "POPAGENT_OT_reset_skill_permissions" in init
    assert "POPAGENT_OT_apply_quick_permission_preset" in init


def run():
    test_confirm_dialog_uses_permission_helper()
    test_skill_panel_exposes_permission_controls_in_developer_mode()
    test_skill_permission_operators_are_registered()
    print("test_skill_permission_wiring OK")
    return True


if __name__ == "__main__":
    run()
