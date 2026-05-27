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

from bpy.types import Panel, UILayout
from .panel import POLYGONINGENIEUR_panel
from ..utils.utils import wrap_string_to_panel
from ..properties.properties import ChatCompanionProperties
from ..properties.addon_preferences import ChatCompanionPreferences
from .. import __package__ as base_package


class CHAT_COMPANION_PT_tokens(POLYGONINGENIEUR_panel, Panel):
    bl_idname = "CHAT_COMPANION_PT_tokens"
    bl_label = "Token"
    bl_order = 3
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header(self, context):
        self.layout.label(text="", icon="SMALL_CAPS")

    def draw(self, context):
        props: ChatCompanionProperties = context.scene.chat_companion_properties
        prefs: ChatCompanionPreferences = context.preferences.addons[
            base_package
        ].preferences

        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        # ! info text
        wrapped_info_text = wrap_string_to_panel(
            context,
            "LLMs use token to determine pricing, process text and have a technical token limit for each request.",
        )
        for line in wrapped_info_text:
            line_col: UILayout = layout.column()
            line_col.label(text=line)
            line_col.scale_y = 0.6
        wrapped_approx_text = wrap_string_to_panel(
            context, "Numbers here are approximations!"
        )
        for line in wrapped_approx_text:
            line_col: UILayout = layout.column()
            line_col.label(text=line)

        # ! tokens of enabled history
        layout.label(text="Token for next question:")
        token_box = layout.box()
        token_summary = token_box.column(align=True)
        token_summary.scale_y = 0.7
        # system
        token_summary.label(text="    288" + " system")
        # prompt
        token_summary.label(text="+ " + str(props.user_prompt_tokens) + " prompt")
        # attachments
        token_summary.label(
            text="+ " + str(props.selected_attachment_tokens) + " enabled attachments"
        )
        # history
        token_summary.label(
            text="+ " + str(props.selected_history_tokens) + " enabled history"
        )
        # total
        token_summary.separator()
        total_tokens = (
            288
            + props.user_prompt_tokens
            + props.selected_history_tokens
            + props.selected_attachment_tokens
        )
        token_summary.label(text="= " + str(total_tokens) + " total token")
        # left
        token_summary.separator(factor=2)
        max_tokens: int = prefs.tokens_dict.get(prefs.open_ai_model, 8000)
        if prefs.llm_organization == "deepseek":
            max_tokens = prefs.tokens_dict.get(prefs.deepseek_model, 8000)

        left_tokens = max_tokens - total_tokens
        left_tokens_column = token_summary.column(align=True)
        left_tokens_column.alert = left_tokens < 100
        left_tokens_column.label(icon="FORWARD", text=str(left_tokens) + " token")
        left_tokens_column.label(text="left to generate answer")
