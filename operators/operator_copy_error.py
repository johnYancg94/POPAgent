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
from bpy import props
from bpy.types import Operator


class CHAT_COMPANION_OT_copy_error(Operator):
    bl_idname = "chat_companion.copy_error"
    bl_label = "Copy error message"
    bl_description = "Copy the whole error message to the clipboard"
    bl_options = {"REGISTER", "INTERNAL"}

    # properties
    content: props.StringProperty(options={"HIDDEN"})

    def execute(self, context):
        bpy.context.window_manager.clipboard = self.content

        self.report({"INFO"}, "Error message copied to clipboard")
        return {"FINISHED"}
