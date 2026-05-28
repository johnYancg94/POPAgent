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
from ..utils.utils import parse_llm_content
from ..utils.utils import wrap_non_code_parts
from ..utils.utils import parts_to_pretty_string


class CHAT_COMPANION_OT_copy(Operator):
    bl_idname = "chat_companion.copy"
    bl_label = "Copy answer"
    bl_description = "Copy the whole answer to the clipboard."
    bl_options = {"REGISTER", "INTERNAL"}

    # properties
    content_type: props.StringProperty(options={"HIDDEN"})
    content: props.StringProperty(options={"HIDDEN"})

    def execute(self, context):

        # ! copy full answer (with lineseps for long text lines) to clipboard
        if self.content_type == "RAW":
            bpy.context.window_manager.clipboard = self.content
            report_message = "Content copied to clipboard"
        elif self.content_type == "FULL":
            answer_parts = parse_llm_content(self.content)
            pretty_wrapped_parts = wrap_non_code_parts(answer_parts)
            pretty_wrapped_str = parts_to_pretty_string(pretty_wrapped_parts)
            bpy.context.window_manager.clipboard = pretty_wrapped_str
            report_message = "Answer copied to clipboard"

        self.report({"INFO"}, report_message)
        return {"FINISHED"}
