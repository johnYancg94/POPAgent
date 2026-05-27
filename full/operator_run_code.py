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


import sys
import re
import bpy
import json
from bpy import props
from bpy.types import Operator


class CHAT_COMPANION_OT_run_code(Operator):
    bl_idname = "chat_companion.run_code"
    bl_label = "Run at your own risk!"
    bl_description = "Runs the code immediately from a new text data-block"
    bl_options = {"REGISTER", "INTERNAL"}

    # properties
    content: props.StringProperty(options={"HIDDEN"})
    index: props.IntProperty(options={"HIDDEN"})

    def execute(self, context):
        chat_properties = context.scene.chat_companion_properties

        code_array = json.loads(self.content)
        code = "\n".join(code_array)
        is_splitted = False

        stripped_code = code.lstrip()
        if stripped_code.startswith("{") or stripped_code.startswith("["):
            self.report(
                {"WARNING"},
                "This block looks like JSON, not Python. It was not executed.",
            )
            return {"CANCELLED"}

        # ! create script
        file_name = "Chat Script"
        run_text_data_block = bpy.data.texts.new(file_name)
        run_text_data_block.write(code)
        run_text_data_block.use_fake_user = False

        # ! make sure text editor is a visible area
        # * and we need the text area to overwrite the context
        # * in order to execute the script within that context
        # editor not visible, split area
        if not any(area.type == "TEXT_EDITOR" for area in bpy.context.screen.areas):
            start_areas = bpy.context.screen.areas[:]

            is_splitted = True

            # If it's not visible, split the current area
            bpy.ops.screen.area_split(direction="VERTICAL", factor=0.0)

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

        # ! make created text file visible
        for area in bpy.context.screen.areas:
            if area.type == "TEXT_EDITOR":
                area.spaces.active.text = run_text_data_block

        # ! run code
        # # run_text_data_block.use_module = True
        with context.temp_override(area=text_area):
            answer_parts = json.loads(chat_properties.answer_parts)
            try:
                bpy.ops.text.run_script()
                # reset error attributes for answer part
                answer_parts[self.index]["error"] = ""
                answer_parts[self.index]["error_line_number"] = None
            except Exception as e:
                last_error_string = sys.exc_info()[-2]

                # get line number
                pattern = r"line (\d+)"
                line_match = re.search(pattern, repr(last_error_string))
                if line_match:
                    answer_parts[self.index]["error_line_number"] = int(
                        line_match.group(1)
                    )

                print("Error during script execution:\n", str(e))

                # insert error message into answer part
                answer_parts[self.index]["error"] = str(e)
                chat_properties.answer_parts = json.dumps(answer_parts)

                self.report({"WARNING"}, "Script had errors. You can ask to fix them.")
            # ! close created text_area again
            if is_splitted:
                bpy.ops.screen.area_close()

        self.report({"INFO"}, "Code executed")
        return {"FINISHED"}
