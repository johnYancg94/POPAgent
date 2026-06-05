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


from bpy.types import Operator
from ..properties.addon_preferences import ChatCompanionPreferences
from .. import __package__ as base_package


class CHAT_COMPANION_OT_select_minimax(Operator):
    # bl_idname kept as select_anthropic so any pre-existing keymap
    # entries (addon_keymaps / user shortcuts) still resolve after the
    # provider rename.
    bl_idname = "chat_companion.select_anthropic"
    bl_label = "minimax"
    bl_description = "minimax M3 / M2.7 (Anthropic Messages API compatible)"
    bl_options = {"REGISTER", "INTERNAL"}

    def execute(self, context):
        prefs: ChatCompanionPreferences = context.preferences.addons[
            base_package
        ].preferences

        # triggers PropertyUpdate.update_llm_details
        prefs.llm_organization = "minimax"

        return {"FINISHED"}
