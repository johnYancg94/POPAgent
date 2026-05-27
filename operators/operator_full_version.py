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


from bpy.types import Operator, Context
from bpy.props import StringProperty

chat_companion_features: dict = {
    "neutral": "Please Upgrade to the Full Version of the addon to use all its features",
    "attachments": "\u2765 POPAgent allows you to attach text documents\n\u2765 You can attach text files from disc or from within Blender\n\u2765 They get sent along with your question to the AI\n\u2765 Attachments can be favored, sorted, deleted, included and excluded",
    "run_code": "\u2765 You can immediately run this code\n\u2765 If there are errors, the erroneous line will be highlighted\n\u2765 Then you can click 'Ask to Fix Error' to directly ask for a solution",
    "list_button": "\u2765 With one click you can directly ask POPAgent about this list item",
    "copy_code": "\u2765 You can copy this code block\n\u2765 There are three possibilities:\n     \u25E6 Copy code to your current cursor position in your Blender-internal text file\n     \u25E6 Copy code to a new Blender-internal text file\n     \u25E6 Copy code to clipboard",
    "ui_help": "\u2765 One-click to ask POPAgent about this Blender UI element\n\u2765 The AI will give you a TL;DR, a comprehensive explanation and a code example",
    "autocomplete": "\u2765 POPAgent can turn your comments into code",
    "llms": "\u2765 Select OpenAI or DeepSeek models",
}


class CHAT_COMPANION_OT_full_version(Operator):
    bl_idname = "chat_companion.full_version"
    bl_label = ""
    bl_description = (
        "Please upgrade to the full version of POPAgent to use all its features"
    )
    bl_options = {"REGISTER", "INTERNAL"}

    feature: StringProperty()

    @classmethod
    def description(cls, context: Context, properties) -> str:
        """Dynamicall get description for disabled operator to show user the feature of the full version."""

        feature_desc: str = chat_companion_features.get(properties.feature)
        if feature_desc:
            return "Full version:\n" + feature_desc
        else:
            return "Please upgrade to the full version of POPAgent to use all its features"

    def execute(self, context):
        return {"FINISHED"}


class CHAT_COMPANION_OT_context_menu_full(Operator):
    bl_idname = "chat_companion.context_menu_full"
    bl_label = "Ask POPAgent about this"
    bl_description = (
        "Please Upgrade to the Full Version of the addon to use all its features"
    )

    feature: StringProperty()

    @classmethod
    def poll(cls, context):
        return False

    @classmethod
    def description(cls, context: Context, properties) -> str:
        """Dynamicall get description for disabled operator to show user the feature of the full version."""

        feature_desc: str = chat_companion_features.get(properties.feature)
        if feature_desc:
            return "Full version only:\n" + feature_desc
        else:
            return "Please upgrade to the full version of POPAgent to use all its features"

    def execute(self, context):
        return {"FINISHED"}
