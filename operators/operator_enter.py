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

import bpy


class CHAT_COMPANION_OT_process_prompt_input(bpy.types.Operator):
    """Process input while Control key is pressed."""

    bl_idname = "chat_companion.process_prompt_input"
    bl_label = "Process Input"
    bl_options = {"REGISTER", "INTERNAL"}

    def modal(self, context, event):
        if event.type == "RET":
            chat_properties = context.scene.chat_companion_properties
            bpy.ops.chat_companion.ask(user_prompt=chat_properties.user_prompt)
            return {"FINISHED"}
        elif event.ctrl:
            pass  # Input processing code.

        return {"PASS_THROUGH"}

    def invoke(self, context, event):
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}
