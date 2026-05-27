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


class CHAT_COMPANION_OT_copy_code_text(Operator):
    bl_idname = "chat_companion.copy_code_text"
    bl_label = "Copy code to new scipt/text"
    bl_description = "Copy code to new scipt/text."
    bl_options = {"REGISTER", "INTERNAL"}

    # properties
    content: props.StringProperty(options={"HIDDEN"})

    def execute(self, context):
        code_array = json.loads(self.content)
        code = "\n".join(code_array)

        # ! copy code segment to new script file aka text data block
        file_name = "Chat Script"
        new_text_data_block = bpy.data.texts.new(file_name)
        new_text_data_block.write(code)
        new_text_data_block.use_fake_user = False
        # make created text file visible
        for area in bpy.context.screen.areas:
            if area.type == "TEXT_EDITOR":
                area.spaces.active.text = new_text_data_block
        report_icon = "INFO"
        report_message = new_text_data_block.name + " with copied code created"

        self.report({report_icon}, report_message)
        return {"FINISHED"}
