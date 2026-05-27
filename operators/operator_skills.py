"""
Skill list panel operators: toggle disabled state and clear session trust.
"""

# pyright: reportInvalidTypeForm=false

import bpy
from bpy.props import StringProperty
from bpy.types import Operator

from ..agent_core import skill_registry
from ..agent_core.confirm_dialog import clear_session_trust


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
