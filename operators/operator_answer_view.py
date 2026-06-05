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


class CHAT_COMPANION_OT_select_answer_object(Operator):
    bl_idname = "chat_companion.select_answer_object"
    bl_label = "Select Object"
    bl_description = "Select this object and frame it in the 3D View."
    bl_options = {"REGISTER", "INTERNAL"}

    object_name: props.StringProperty(options={"HIDDEN"})

    def execute(self, context):
        obj = bpy.data.objects.get(self.object_name)
        if obj is None:
            self.report({"WARNING"}, f"Object not found: {self.object_name}")
            return {"CANCELLED"}

        if not self._is_in_view_layer(context, obj):
            searched = self._show_in_outliner_file_search(context, obj.name)
            self.report(
                {"WARNING"},
                f"Object is not in the current ViewLayer; searched Outliner: {obj.name}",
            )
            return {"FINISHED"} if searched else {"CANCELLED"}

        if getattr(obj, "hide_select", False):
            searched = self._show_in_outliner_file_search(context, obj.name)
            self.report(
                {"WARNING"},
                f"Object cannot be selected; searched Outliner: {obj.name}",
            )
            return {"FINISHED"} if searched else {"CANCELLED"}

        if context.object and context.object.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")

        bpy.ops.object.select_all(action="DESELECT")
        try:
            obj.select_set(True)
            context.view_layer.objects.active = obj
        except RuntimeError as exc:
            searched = self._show_in_outliner_file_search(context, obj.name)
            self.report({"WARNING"}, f"Could not select object; searched Outliner: {exc}")
            return {"FINISHED"} if searched else {"CANCELLED"}
        self._frame_object(context)
        self._show_view_layer_outliner(context)
        self._focus_active_in_outliner(context)
        self.report({"INFO"}, f"Selected {obj.name}")
        return {"FINISHED"}

    def _is_in_view_layer(self, context, obj) -> bool:
        view_layer = getattr(context, "view_layer", None)
        if view_layer is None:
            return False
        return view_layer.objects.get(obj.name) is not None

    def _show_in_outliner_file_search(self, context, object_name: str) -> bool:
        return self._set_outliner(context, "BLENDER_FILE", object_name)

    def _show_view_layer_outliner(self, context) -> bool:
        return self._set_outliner(context, "VIEW_LAYER", "")

    def _set_outliner(self, context, display_mode: str, filter_text: str) -> bool:
        screen = getattr(context, "screen", None)
        if screen is None:
            return False
        matched = False
        for area in screen.areas:
            if area.type != "OUTLINER":
                continue
            space = next((s for s in area.spaces if s.type == "OUTLINER"), None)
            if space is None:
                continue
            if hasattr(space, "display_mode"):
                try:
                    space.display_mode = display_mode
                except (TypeError, ValueError):
                    pass
            if hasattr(space, "filter_text"):
                space.filter_text = filter_text
            area.tag_redraw()
            matched = True
        return matched

    def _frame_object(self, context):
        screen = getattr(context, "screen", None)
        if screen is None:
            return
        for area in screen.areas:
            if area.type != "VIEW_3D":
                continue
            region = next((r for r in area.regions if r.type == "WINDOW"), None)
            space = next((s for s in area.spaces if s.type == "VIEW_3D"), None)
            if region is None or space is None:
                continue
            with context.temp_override(area=area, region=region, space_data=space):
                bpy.ops.view3d.view_selected(use_all_regions=False)
            return

    def _focus_active_in_outliner(self, context) -> bool:
        screen = getattr(context, "screen", None)
        if screen is None:
            return False
        focused = False
        for area in screen.areas:
            if area.type != "OUTLINER":
                continue
            region = next((r for r in area.regions if r.type == "WINDOW"), None)
            space = next((s for s in area.spaces if s.type == "OUTLINER"), None)
            if region is None or space is None:
                continue
            try:
                with context.temp_override(area=area, region=region, space_data=space):
                    bpy.ops.outliner.show_active()
                focused = True
            except RuntimeError:
                pass
        return focused


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
