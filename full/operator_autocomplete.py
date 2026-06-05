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
from ..utils import utils
from bpy.types import Text, Space, SpaceTextEditor
from ..properties.properties import ChatCompanionProperties
from ..properties.addon_preferences import ChatCompanionPreferences
from ..utils import dependencies
from .. import __package__ as base_package


class CHAT_COMPANION_OT_autocomplete(bpy.types.Operator):
    bl_idname = "chat_companion.autocomplete"
    bl_label = "Turn Comments into Code"
    bl_description = ""
    bl_options = {"REGISTER", "INTERNAL"}

    @classmethod
    def description(cls, context, properties):
        addon_preferences: ChatCompanionPreferences = context.preferences.addons[
            base_package
        ].preferences
        chat_properties: ChatCompanionProperties = (
            context.scene.chat_companion_properties
        )

        api_key: str | None = None
        if addon_preferences.llm_organization == "openai":
            api_key = addon_preferences.open_ai_api_key
        elif addon_preferences.llm_organization == "deepseek":
            api_key = addon_preferences.deepseek_api_key
        elif addon_preferences.llm_organization == "minimax":
            api_key = addon_preferences.minimax_api_key

        no_api_key = api_key is None or len(api_key) == 0 or api_key == ""
        desciption = "Ask POPAgent to turn your selected comments into code. A comment is for example: # add cube"
        if no_api_key:
            desciption = "Please enter your API key in the addons preferences first"
        if chat_properties.waiting_for_answer or chat_properties.is_streaming:
            desciption = "Please wait for the current answer before asking again"
        return desciption

    @classmethod
    def poll(cls, context):
        if context.space_data is None:
            return False
        if not isinstance(context.space_data, SpaceTextEditor):
            return False
        space: SpaceTextEditor = context.space_data
        if space.text is None:
            return False
        return utils.can_send_prompt(context)

    def execute(self, context):
        props = context.scene.chat_companion_properties
        prefs: ChatCompanionPreferences = context.preferences.addons[
            base_package
        ].preferences

        # print selected text of text editor
        text_block = context.space_data.text
        props.code_completion_text_name = text_block.name
        lines = text_block.lines

        # start and end index of lines in selection if one exists
        start_line_index = text_block.current_line_index
        end_line_index = text_block.select_end_line_index

        # start and end lines
        start_line = text_block.current_line
        end_line = text_block.select_end_line

        # sort and
        if start_line_index > end_line_index:
            tmp_id = start_line_index
            start_line_index = end_line_index
            end_line_index = tmp_id
            start_line = text_block.select_end_line
            end_line = text_block.current_line

        # extent end by one to get correct selection
        end_line_index += 1

        # build selection string
        selection = ""
        for index, line in enumerate(lines):
            if index not in range(start_line_index, end_line_index):
                continue
            selection += "\n" + line.body

        if selection.strip() == "":
            self.report(
                {"WARNING"}, "Empty line(s). Please select line(s) with content"
            )
            return {"FINISHED"}

        prompt = (
            "This is my python code in Blender:\n"
            + text_block.as_string()
            + "\n\nTurn the comments in the following lines "
            + "into working blender python text editor code:\n"
            + selection
        )

        # ! enter placeholder strings
        # set cursor to begin of selection and insert placeholder string
        if start_line != end_line:
            start_line.body = (
                start_line.body + " " + props.code_completion_placeholder_begin
            )
            end_line.body = end_line.body + " " + props.code_completion_placeholder_end
        else:
            start_line.body = start_line.body + " " + props.code_completion_placeholder

        view3D_area = utils.get_view3D_area(context)

        # ! add data path as prompt
        props.user_prompt = prompt

        # ! ask
        # # run_text_data_block.use_module = True
        with context.temp_override(area=view3D_area):
            bpy.ops.chat_companion.ask(
                user_prompt=prompt,
                is_code_completion=True,
                use_streaming=prefs.use_streaming
                and dependencies.dependencies_installed,
            )
            # ! close created text_area again
            if props.view_was_splitted:
                bpy.ops.screen.area_close()
                props.view_was_splitted = False

        self.report({"INFO"}, "Code Completion prompt sent...")
        return {"FINISHED"}
