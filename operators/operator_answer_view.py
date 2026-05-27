# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.

# pyright: reportInvalidTypeForm=false


import bpy
from bpy import props
from bpy.types import Operator


ANSWER_TEXT_NAME = "POPAgent Answer.md"


class CHAT_COMPANION_OT_open_answer_text(Operator):
    bl_idname = "chat_companion.open_answer_text"
    bl_label = "Open Full Answer"
    bl_description = "Open the full answer in a Blender text datablock."
    bl_options = {"REGISTER", "INTERNAL"}

    content: props.StringProperty(options={"HIDDEN"})

    def execute(self, context):
        answer = self.content
        if not answer:
            answer = context.scene.chat_companion_properties.answer

        if not answer:
            self.report({"WARNING"}, "There is no answer to open.")
            return {"CANCELLED"}

        text_block = bpy.data.texts.get(ANSWER_TEXT_NAME)
        if text_block is None:
            text_block = bpy.data.texts.new(ANSWER_TEXT_NAME)
        text_block.from_string(answer)

        text_area = self._find_text_area(context)
        if text_area is not None:
            text_area.spaces.active.text = text_block
            self.report({"INFO"}, "Full answer opened in the Text Editor.")
        else:
            self.report({"INFO"}, "Full answer saved as a Blender text datablock.")

        return {"FINISHED"}

    def _find_text_area(self, context):
        screen = getattr(context, "screen", None)
        if screen is None:
            return None
        for area in screen.areas:
            if area.type == "TEXT_EDITOR":
                return area
        return None


class CHAT_COMPANION_OT_toggle_answer_code(Operator):
    bl_idname = "chat_companion.toggle_answer_code"
    bl_label = "Toggle Code Block"
    bl_description = "Expand or collapse this answer code block."
    bl_options = {"REGISTER", "INTERNAL"}

    index: props.IntProperty(options={"HIDDEN"})

    def execute(self, context):
        props = context.scene.chat_companion_properties
        indices = _parse_indices(props.expanded_answer_code_indices)
        if self.index in indices:
            indices.remove(self.index)
        else:
            indices.add(self.index)
        props.expanded_answer_code_indices = ",".join(str(i) for i in sorted(indices))
        return {"FINISHED"}


def _parse_indices(value: str) -> set:
    indices = set()
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            indices.add(int(item))
        except ValueError:
            pass
    return indices
