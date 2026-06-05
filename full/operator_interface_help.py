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
from ..properties.properties import ChatCompanionProperties
from ..properties.addon_preferences import ChatCompanionPreferences
from .. import __package__ as base_package


class CHAT_COMPANION_OT_interface_help(bpy.types.Operator):
    bl_idname = "chat_companion.interface_help"
    bl_label = "Ask POPAgent about this"
    bl_description = "This will automatically ask POPAgent about this setting/tool, what it is for and how to use it in python"
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
        desciption = "This will automatically ask POPAgent about this setting/tool, what it is for and how to use it in python"
        if no_api_key:
            desciption = "Please enter your API key in the addons preferences first"
        if chat_properties.waiting_for_answer or chat_properties.is_streaming:
            desciption = "Please wait for the current answer before asking again"
        return desciption

    @classmethod
    def poll(cls, context):
        return utils.can_send_prompt(context)

    def execute(self, context):
        chat_properties = context.scene.chat_companion_properties
        addon_preferences = context.preferences.addons[
            base_package
        ].preferences

        has_data_path = bpy.ops.ui.copy_data_path_button.poll()
        has_python_command = bpy.ops.ui.copy_python_command_button.poll()
        has_source = bpy.ops.ui.editsource.poll()

        area_type = context.area.type
        region_type = context.region.type
        name = ""
        python_command = ""
        prompt = ""

        # ! get full data path
        if has_data_path:
            bpy.ops.ui.copy_data_path_button(full_path=True)
            python_command = context.window_manager.clipboard
            bpy.ops.ui.copy_data_path_button(full_path=False)
            name = context.window_manager.clipboard
            prompt = (
                "In Blender there is a setting/option in the "
                + region_type
                + " of the area "
                + area_type
                + ", called "
                + name
                + ". "
                + "The python command for this is "
                + python_command
                + ". "
                + "Explain this setting and what effects changing it has. "
                + "Also include a short python bpy code example. "
                + "Include a one sentence long TL:DR summary at the very top."
            )

        # ! get python command
        elif has_python_command:
            bpy.ops.ui.copy_python_command_button()
            python_command = context.window_manager.clipboard
            prompt = (
                "In Blender there is a setting/option in the "
                + region_type
                + " of the area "
                + area_type
                + ". "
                "The python command for this is "
                + python_command
                + ". "
                + "Explain this setting and what effects changing it has. "
                + "Also include a short python bpy code example. "
                + "Include a one sentence long TL:DR summary at the very top."
            )

        # ! get source information
        # elif has_source:
        #     pass

        # ! try to get context information
        # TODO need more information under cursor
        else:
            print("-------------------CONTEXT--------------------")
            print("area type", area_type)
            print("region", context.region.type)
            prompt = (
                "In Blender there is a setting/option in the "
                + region_type
                + " of the area "
                + area_type
                + ". "
            )
        view3D_area = utils.get_view3D_area(context)

        # ! add data path as prompt
        chat_properties.user_prompt = prompt

        # ! ask
        # # run_text_data_block.use_module = True
        with context.temp_override(area=view3D_area):
            bpy.ops.chat_companion.ask(
                user_prompt=prompt,
                is_context_menu=True,
                use_streaming=addon_preferences.use_streaming,
            )
            # ! close created text_area again
            if chat_properties.view_was_splitted:
                bpy.ops.screen.area_close()
                chat_properties.view_was_splitted = False

        return {"FINISHED"}
