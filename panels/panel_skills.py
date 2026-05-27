# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.

from bpy.types import Panel, UILayout
from .panel import POLYGONINGENIEUR_panel
from ..agent_core import skill_registry
from ..agent_core.confirm_dialog import session_trust_list


def _group_by_owner(items):
    groups: dict[str, list[tuple[dict, bool]]] = {}
    for skill, disabled in items:
        owner = skill.get("owner", "unknown")
        groups.setdefault(owner, []).append((skill, disabled))
    return groups


_LEVEL_ICON = {
    "never": "CHECKMARK",
    "first": "QUESTION",
    "always": "ERROR",
}


def _metadata_summary(meta: dict) -> str:
    parts = []
    if meta.get("writes_files"):
        parts.append("writes files")
    if meta.get("modifies_scene"):
        parts.append("modifies scene")
    if meta.get("launches_external_process"):
        parts.append("external process")

    if meta.get("undoable"):
        parts.append("undoable")
    elif meta.get("modifies_scene") or meta.get("writes_files"):
        parts.append("no undo")

    level = meta.get("requires_confirmation", "never")
    if level == "always":
        parts.append("always confirm")
    elif level == "first":
        parts.append("first confirm")
    else:
        parts.append("auto")

    return " / ".join(parts)


def draw_skills_ui(layout: UILayout):
    items = skill_registry.all_skills_including_disabled()
    if not items:
        layout.label(text="(no skills registered)", icon="INFO")
        return

    layout.label(text=f"{len(items)} skill(s) registered")

    groups = _group_by_owner(items)
    for owner in sorted(groups.keys()):
        box = layout.box()
        header = box.row(align=True)
        header.label(text=f"owner: {owner}", icon="OUTLINER_OB_GROUP_INSTANCE")

        for skill, disabled in groups[owner]:
            meta = skill.get("metadata", {})
            level = meta.get("requires_confirmation", "never")
            icon = _LEVEL_ICON.get(level, "DOT")

            row = box.row(align=True)
            toggle_op = row.operator(
                "popagent.toggle_skill",
                text="",
                icon="HIDE_OFF" if not disabled else "HIDE_ON",
                emboss=False,
            )
            toggle_op.owner = owner
            toggle_op.name = skill.get("name", "?")

            label_col = row.column()
            label_col.enabled = not disabled
            label_col.label(text=skill.get("name", "?"), icon=icon)
            summary = _metadata_summary(meta)
            if summary:
                sub = label_col.row()
                sub.scale_y = 0.65
                sub.label(text=summary)

    layout.separator()

    trust = session_trust_list()
    trust_box = layout.box()
    trust_row = trust_box.row(align=True)
    trust_row.label(text=f"Session trust ({len(trust)})", icon="LOCKED")
    trust_row.operator(
        "popagent.clear_session_trust", text="", icon="X", emboss=False
    )
    if trust:
        col = trust_box.column(align=True)
        col.scale_y = 0.7
        for name in trust:
            col.label(text=f"  {name}")


class CHAT_COMPANION_PT_skills(POLYGONINGENIEUR_panel, Panel):
    bl_idname = "CHAT_COMPANION_PT_skills"
    bl_label = "Skills"
    bl_order = 4
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header(self, context):
        self.layout.label(text="", icon="TOOL_SETTINGS")

    def draw(self, context):
        draw_skills_ui(self.layout)
