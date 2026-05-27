# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

# pyright: reportInvalidTypeForm=false


import bpy
import json
from bpy import props
from bpy.types import Operator


class CHAT_COMPANION_OT_copy_code_cursor(Operator):
    bl_idname = "chat_companion.copy_code_cursor"
    bl_label = "Copy Code to Cursor"
    bl_description = (
        "Copy the code to the current cursor position in the current text data-block"
    )
    bl_options = {"REGISTER", "INTERNAL"}

    # properties
    content: props.StringProperty(options={"HIDDEN"})

    def execute(self, context):
        code_array = json.loads(self.content)
        code = "\n".join(code_array)

        # ! copy code segment to current cursor location in text data block
        # editor not visible, split area
        if not any(area.type == "TEXT_EDITOR" for area in bpy.context.screen.areas):
            start_areas = bpy.context.screen.areas[:]

            # If it's not visible, split the current area
            bpy.ops.screen.area_split(direction="VERTICAL", factor=0.7)

            # change space to text editor
            for area in context.screen.areas:
                if area not in start_areas:
                    area.type = "TEXT_EDITOR"

            # Get the new active area (which should now be the text editor)
            text_area = next(
                area for area in bpy.context.screen.areas if area.type == "TEXT_EDITOR"
            )
        # editor visible, get area
        else:
            # If the text editor is already visible, just get its area
            text_area = next(
                area for area in bpy.context.screen.areas if area.type == "TEXT_EDITOR"
            )

        # https://docs.blender.org/api/3.2/bpy.types.Context.html#bpy.types.Context.temp_override
        with context.temp_override(area=text_area):
            for space in text_area.spaces:
                if space.type == "TEXT_EDITOR":
                    text_block = space.text
                    # paste code into cursor location
                    if text_block is not None:
                        curr_line = text_block.current_line_index
                        curr_character = text_block.current_character
                        text_block.write(code)
                        text_block.cursor_set(
                            line=curr_line + len(code_array),
                            character=curr_character,
                            select=False,
                        )
                        report_icon = "INFO"
                        report_message = (
                            "Code pasted at current cursor location in "
                            + text_block.name
                        )
                    else:
                        file_name = "Chat Script"
                        new_text_block = bpy.data.texts.new(file_name)
                        new_text_block.write(code)
                        new_text_block.use_fake_user = False
                        # make created text file visible
                        for area in bpy.context.screen.areas:
                            if area.type == "TEXT_EDITOR":
                                area.spaces.active.text = new_text_block
                        report_icon = "INFO"
                        report_message = (
                            "No active text in text editor, "
                            + new_text_block.name
                            + " was created"
                        )

        self.report({report_icon}, report_message)
        return {"FINISHED"}
