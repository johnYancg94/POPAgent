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
from bpy.types import UILayout, Context
from .property_updates import PropertyUpdates
from ..utils import cc_globals


class HistoryPropertyGroup(bpy.types.PropertyGroup):
    display_name: bpy.props.StringProperty()

    user_prompt: bpy.props.StringProperty()
    answer: bpy.props.StringProperty()
    answer_parts: bpy.props.StringProperty()
    icon: bpy.props.StringProperty()
    is_favorite: bpy.props.BoolProperty()
    is_enabled: bpy.props.BoolProperty(
        name="Enable this history as context for your next prompt?",
        description="If this prompt and answer should be sent along your next prompt or not",
        default=True,
        update=PropertyUpdates.update_history_item_is_enabled,
    )
    llm_organization: bpy.props.StringProperty(
        name="LLM Organization",
        description="The organization that was used for this history entry",
        default="",
    )

    # Agent mode: JSON-serialized list of tool calls made during this turn.
    # Empty string = plain chat turn (no tools called).
    tool_calls_json: bpy.props.StringProperty(
        name="Tool Calls",
        description="JSON list of tool calls made during this agent turn",
        default="",
    )

    is_error: bpy.props.BoolProperty()
    error_button_icon: bpy.props.StringProperty()
    error_button_text: bpy.props.StringProperty()
    error_button_content: bpy.props.StringProperty()
    error_button_url: bpy.props.StringProperty()
    error_title: bpy.props.StringProperty()
    error_info: bpy.props.StringProperty()
    error_message: bpy.props.StringProperty()


class CHAT_COMPANION_UL_item_history(bpy.types.UIList):

    def draw_item(
        self,
        context: Context,
        layout: UILayout,
        data,
        item: HistoryPropertyGroup,
        icon,
        active_data,
        active_propname,
    ):

        pcoll = cc_globals.preview_collections["main"]

        # draw_item must handle the three layout types...
        # Usually 'DEFAULT' and 'COMPACT' can share the same code
        if self.layout_type in {"DEFAULT", "COMPACT"}:

            llm_org_icon: int
            if item.llm_organization == "openai":
                llm_org_icon = pcoll["openai_icon"].icon_id
            elif item.llm_organization == "deepseek":
                llm_org_icon = pcoll["deepseek_icon"].icon_id
            else:
                llm_org_icon = pcoll["chat_companion_icon"].icon_id

            layout.prop(
                data=item,
                property="display_name",
                text="",
                icon_value=llm_org_icon,
                emboss=False,
            )

            if item.is_favorite:
                layout.label(icon="SOLO_ON")

            if item.is_error:
                layout.label(icon="ERROR")

            if not item.is_error:
                icon = "CHECKBOX_HLT" if item.is_enabled else "CHECKBOX_DEHLT"
                layout.prop(item, "is_enabled", text="", icon=icon, emboss=False)
