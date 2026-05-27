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
from bpy.types import Context, UILayout, Menu
from ..utils import cc_globals
from ..operators.operator_full_version import CHAT_COMPANION_OT_context_menu_full


class WM_MT_button_context(Menu):
    # class to add a context menu entry
    bl_label = ""

    @classmethod
    def poll(cls, context: Context):
        # TODO show on even more places
        has_data_path: bool = bpy.ops.ui.copy_data_path_button.poll()
        has_python_command: bool = bpy.ops.ui.copy_python_command_button.poll()
        has_source: bool = bpy.ops.ui.editsource.poll()
        return has_data_path or has_python_command

    def draw(self, context: Context):
        pass


def chat_companion_button_menu(self, context: Context):

    layout: UILayout = self.layout
    layout.separator()
    pcoll = cc_globals.preview_collections["main"]

    if cc_globals.cc_full:
        from ..full.operator_interface_help import CHAT_COMPANION_OT_interface_help

        layout.operator(
            CHAT_COMPANION_OT_interface_help.bl_idname,
            icon_value=pcoll["chat_companion_icon"].icon_id,
        )
    else:
        help_full_op = layout.operator(
            CHAT_COMPANION_OT_context_menu_full.bl_idname,
            icon_value=pcoll["chat_companion_icon"].icon_id,
        )
        help_full_op.feature = "ui_help"
