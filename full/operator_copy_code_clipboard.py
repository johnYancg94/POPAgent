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


class CHAT_COMPANION_OT_copy_code_clipboard(Operator):
    bl_idname = "chat_companion.copy_code_clipboard"
    bl_label = "Copy Code"
    bl_description = "Copy the Code to the Clipboard"
    bl_options = {"REGISTER", "INTERNAL"}

    # properties
    content: props.StringProperty(options={"HIDDEN"})

    def execute(self, context):
        code_array = json.loads(self.content)
        code = "\n".join(code_array)

        # ! copy code segment to clipboard
        bpy.context.window_manager.clipboard = code
        report_icon = "INFO"
        report_message = "Code segment copied to clipboard."

        self.report({report_icon}, report_message)
        return {"FINISHED"}
