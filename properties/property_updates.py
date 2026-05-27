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
import json
from bpy.types import Context
from ..utils.dependencies import Dependencies  # keep for update_use_streaming
from ..utils import utils
from ..utils import cc_globals
from .. import __package__ as base_package


class PropertyUpdates:

    def update_ui(self, context: Context) -> None:
        """Necessary to trigger ui update when prop changes."""
        pass

    def update_user_prompt(self, context):
        # TODO catch if enter was pressed
        # thanks to https://blender.stackexchange.com/questions/3465/how-do-i-catch-keyboard-input-for-a-blender-plugin
        # bpy.ops.chat_companion.process_prompt_input('INVOKE_DEFAULT')

        # count tokens for prompt
        tokens = round(utils.string_to_tokens_float(self.user_prompt))
        if len(self.user_prompt) > 0 and tokens == 0:
            tokens = 1
        self.user_prompt_tokens = tokens
        pass

    def update_code_completion(self, context):
        cp = context.scene.chat_companion_properties

        if cp.update_code_completion:
            cp.update_code_completion = False
        else:
            # do nothing if the flag was False
            return

        # get the code from the answer
        # check if answer has code parts
        code_completion_list = None
        for part in json.loads(cp.answer_parts):
            # get the first code part as code completion answer
            if part["type"] == "code":
                code_completion_list = part["content"]
        # no code part was present
        if code_completion_list is None:
            # assume the whole answer is code
            for part in json.loads(cp.answer_parts):
                # get the first text part as code completion answer
                if part["type"] == "text":
                    code_completion_list = part["content"]

        text_area = utils.get_text_editor_area(context)
        # with statement in function to be able to return from it

        def operate_in_text_block():
            with context.temp_override(area=text_area):
                try:
                    # look for text, could be deleted, renamed, ...
                    text_block = bpy.data.texts[cp.code_completion_text_name]
                except KeyError as e:
                    print("Text block not found", e)
                    cp.code_completion_text_not_found = True
                    return

                text_list = []
                for index, line in enumerate(text_block.lines):
                    text_list.append(line.body)
                    if cp.code_completion_placeholder in line.body:
                        start_line = index
                        end_line = index
                    if cp.code_completion_placeholder_begin in line.body:
                        start_line = index
                    if cp.code_completion_placeholder_end in line.body:
                        end_line = index

                # remove "old" lines
                if start_line == end_line:
                    del text_list[start_line]
                else:
                    del text_list[start_line : end_line + 1]

                # insert new code
                for new_line in reversed(code_completion_list):
                    text_list.insert(start_line, new_line)

                new_text_block = "\n".join(text_list)
                text_block.from_string(new_text_block)

        operate_in_text_block()

    def update_selected_history_item(self, context):
        history = context.scene.chat_companion_history

        if len(history) > 0:
            # the index is the key (history_item.name)
            history_item = history.get(str(self.selected_history_item))

            self.display_name = history_item.display_name
            self.user_prompt = history_item.user_prompt
            self.answer = history_item.answer
            self.answer_parts = history_item.answer_parts
            self.expanded_answer_code_indices = ""

            cc_globals.request_failed = history_item.is_error
            self.error_button_icon = history_item.error_button_icon
            self.error_button_text = history_item.error_button_text
            self.error_button_content = history_item.error_button_content
            self.error_button_url = history_item.error_button_url
            self.error_title = history_item.error_title
            self.error_info = history_item.error_info
            self.error_message = history_item.error_message

        # update view_3d (where addon is located in (context))
        try:
            # it sometimes doesn't exist when view3D isn't current area
            context.area.tag_redraw()
        except Exception as e:
            pass

    def update_selected_text_block(self, context):
        if self.selected_text_block != "":
            bpy.ops.chat_companion.add_internal_text(file_name=self.selected_text_block)

    def update_use_streaming(self, context):
        """Not in use currently"""
        pass
        # upon enabling, check if httpx is installed
        # if self.use_streaming and not Dependencies.check_dependencies():
        #     Dependencies.install_dependencies()

    def update_history_item_is_enabled(self, context):
        PropertyUpdates.update_selected_history_tokens(self, context)

    def update_selected_history_tokens(self, context):
        history = context.scene.chat_companion_history
        chat_properties = context.scene.chat_companion_properties
        tokens = 0
        for history_item in history:
            if history_item.is_enabled:
                tokens += utils.string_to_tokens_float(history_item.answer)
                tokens += utils.string_to_tokens_float(history_item.user_prompt)

        chat_properties.selected_history_tokens = round(tokens)

    def update_attachment_item_is_enabled(self, context):
        chat_properties = context.scene.chat_companion_properties
        if self.is_enabled:
            chat_properties.selected_attachment_tokens += self.tokens
        else:
            chat_properties.selected_attachment_tokens -= self.tokens

    def update_llm_details(self, context: Context):
        """Updates header and payload depending on selected ai organization and model."""

        from .properties import ChatCompanionProperties
        from .addon_preferences import ChatCompanionPreferences
        from ..providers import OpenAICompatProvider, AnthropicProvider

        props: ChatCompanionProperties = context.scene.chat_companion_properties
        prefs: ChatCompanionPreferences = context.preferences.addons[
            base_package
        ].preferences

        org: str = prefs.llm_organization

        if org == "openai":
            provider = OpenAICompatProvider("openai")
        elif org == "deepseek":
            provider = OpenAICompatProvider("deepseek")
        elif org == "anthropic":
            provider = AnthropicProvider()
        else:
            # Fallback: try full-version handler for unknown providers, then bail.
            if cc_globals.cc_full:
                from ..full import utils
                headers, payload = utils.set_full_llms(context)
                props.api_headers = json.dumps(headers)
                props.api_payload = json.dumps(payload)
                props.api_details_updated = True
            return

        provider.apply_to_props(prefs, props)
        print(
            f"Setting LLM details: org={org} url={props.api_url}"
        )

    def update_developer_mode(self, context: Context):
        """Re-register or unregister dev.run_python when developer_mode toggles."""
        try:
            from ..builtin_skills.dev_skills import RUN_PYTHON
            from ..agent_core import skill_registry
            if self.developer_mode:
                skill_registry.register_skill(RUN_PYTHON)
            else:
                skill_registry.unregister_namespace("builtin.dev")
        except Exception as exc:
            print(f"[POPAgent] developer_mode update error: {exc}")
