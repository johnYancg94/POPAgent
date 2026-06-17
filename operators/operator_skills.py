"""
Skill list panel operators: toggle disabled state and clear session trust.
"""

# pyright: reportInvalidTypeForm=false

import bpy
import json
from bpy.props import StringProperty
from bpy.types import Operator

from ..agent_core import skill_registry
from ..agent_core.confirm_dialog import clear_session_trust
from .. import __package__ as base_package


def _prefs_from_context(context):
    return context.preferences.addons[base_package].preferences


def _read_override_json(prefs) -> dict:
    raw = getattr(prefs, "skill_permission_overrides_json", "") or "{}"
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def apply_quick_permission_preset(prefs, preset: str) -> None:
    if preset == "DEFAULT":
        prefs.skill_permission_overrides_json = "{}"
        skill_registry.clear_permission_overrides()
        return

    if preset == "AUTO":
        data = {}
        for skill in skill_registry.all_skills():
            owner = skill.get("owner", "unknown")
            name = skill.get("name", "")
            if name:
                data[skill_registry.permission_key(owner, name)] = "never"
                skill_registry.set_permission_override(owner, name, "never")
        prefs.skill_permission_overrides_json = json.dumps(
            data,
            ensure_ascii=False,
            sort_keys=True,
        )


class POPAGENT_OT_toggle_skill(Operator):
    """Enable or disable a registered skill (session-scoped)."""

    bl_idname = "popagent.toggle_skill"
    bl_label = "Toggle Skill"
    bl_options = {"INTERNAL"}

    owner: StringProperty(default="")
    name: StringProperty(default="")

    def execute(self, context):
        if not self.owner or not self.name:
            return {"CANCELLED"}
        was = skill_registry.is_disabled(self.owner, self.name)
        skill_registry.set_disabled(self.owner, self.name, not was)
        return {"FINISHED"}


class POPAGENT_OT_clear_session_trust(Operator):
    """Clear the in-memory session trust list."""

    bl_idname = "popagent.clear_session_trust"
    bl_label = "Clear Session Trust"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        clear_session_trust()
        self.report({"INFO"}, "Session trust cleared.")
        return {"FINISHED"}


class POPAGENT_OT_set_skill_permission(Operator):
    """Set a persistent per-skill confirmation override."""

    bl_idname = "popagent.set_skill_permission"
    bl_label = "Set Skill Permission"
    bl_options = {"INTERNAL"}

    owner: StringProperty(default="")
    name: StringProperty(default="")
    level: StringProperty(default="never")

    def execute(self, context):
        if not self.owner or not self.name:
            return {"CANCELLED"}
        if self.level not in {"never", "first", "always"}:
            return {"CANCELLED"}

        prefs = _prefs_from_context(context)
        data = _read_override_json(prefs)
        data[skill_registry.permission_key(self.owner, self.name)] = self.level
        prefs.skill_permission_overrides_json = json.dumps(
            data,
            ensure_ascii=False,
            sort_keys=True,
        )
        skill_registry.set_permission_override(self.owner, self.name, self.level)
        return {"FINISHED"}


class POPAGENT_OT_apply_quick_permission_preset(Operator):
    """Apply the global quick permission preset from addon preferences."""

    bl_idname = "popagent.apply_quick_permission_preset"
    bl_label = "Apply Quick Permission Preset"
    bl_options = {"INTERNAL"}

    preset: StringProperty(default="AUTO")

    def execute(self, context):
        if self.preset not in {"DEFAULT", "AUTO"}:
            return {"CANCELLED"}

        prefs = _prefs_from_context(context)
        prefs.quick_permission_preset = self.preset
        apply_quick_permission_preset(prefs, self.preset)
        if self.preset == "DEFAULT":
            self.report({"INFO"}, "Skill permissions restored to presets.")
        else:
            self.report({"INFO"}, "Skill permissions set to auto.")
        return {"FINISHED"}


class POPAGENT_OT_reset_skill_permissions(Operator):
    """Restore all skills to their preset metadata confirmation levels."""

    bl_idname = "popagent.reset_skill_permissions"
    bl_label = "Restore Preset Skill Permissions"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        prefs = _prefs_from_context(context)
        prefs.quick_permission_preset = "DEFAULT"
        apply_quick_permission_preset(prefs, "DEFAULT")
        self.report({"INFO"}, "Skill permissions restored to presets.")
        return {"FINISHED"}
