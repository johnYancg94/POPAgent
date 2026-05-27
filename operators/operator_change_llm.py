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


class CHAT_COMPANION_OT_select_open_ai(Operator):
    bl_idname = "chat_companion.select_open_ai"
    bl_label = "OpenAI"
    bl_description = "American artificial intelligence research organization OpenAI. Has models such as GPT 4"
    bl_options = {"REGISTER", "INTERNAL"}

    def execute(self, context):
        prefs: ChatCompanionPreferences = context.preferences.addons[
            base_package
        ].preferences

        # triggers ProperyUpdate.update_llm_details
        prefs.llm_organization = "openai"

        return {"FINISHED"}


class CHAT_COMPANION_OT_select_mimo(Operator):
    bl_idname = "chat_companion.select_mimo"
    bl_label = "MiMo"
    bl_description = "MiMo models via the OpenAI-compatible chat API"
    bl_options = {"REGISTER", "INTERNAL"}

    def execute(self, context):
        prefs: ChatCompanionPreferences = context.preferences.addons[
            base_package
        ].preferences

        # triggers ProperyUpdate.update_llm_details
        prefs.llm_organization = "mimo"

        return {"FINISHED"}
