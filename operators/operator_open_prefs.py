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
from bpy.types import Operator
from ..utils.dependencies import Dependencies
from .. import __package__ as base_package


class CHAT_COMPANION_OT_open_prefs(Operator):
    bl_idname = "chat_companion.open_prefs"
    bl_label = "Open Preferences"
    bl_description = "Open the preferences for POPAgent"
    bl_options = {"REGISTER"}

    def execute(self, context):

        bpy.ops.screen.userpref_show()
        bpy.context.preferences.active_section = "ADDONS"
        bpy.data.window_managers["WinMan"].addon_search = "POPAgent"

        # check dependency installation
        # Dependencies.check_dependencies()
        # reset Check Dependencies button
        addon_preferences = context.preferences.addons[base_package].preferences
        addon_preferences.dependencies_checked = False

        return {"FINISHED"}
