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


from bpy.types import PropertyGroup
from bpy.props import StringProperty, BoolProperty, IntProperty
from .property_updates import PropertyUpdates
from ..operators.operator_full_version import chat_companion_features


class ChatCompanionProperties(PropertyGroup):

    # region ui
    waiting_for_answer: BoolProperty(
        name="Waiting",
        description="Waiting for an answer from the LLM API server",
        default=False,
        update=PropertyUpdates.update_ui,
    )

    is_connecting: BoolProperty(
        name="Connecting",
        description="If POPAgent is currently connecting to an API",
        default=False,
        update=PropertyUpdates.update_ui,
    )

    waiting_string: StringProperty(
        name="Waiting String",
        description="The string that is being printed while waiting for the LLM API answer",
        default="",
        update=PropertyUpdates.update_ui,
    )

    waiting_icon: StringProperty(
        name="Waiting Icon", default="ALIGN_TOP", update=PropertyUpdates.update_ui
    )

    answering_string: StringProperty(
        name="Answer String",
        description="The string that is being printed while AI is answering",
        default="",
        update=PropertyUpdates.update_ui,
    )

    answering_icon: StringProperty(
        name="Answer Icon", default="WORDWRAP_ON", update=PropertyUpdates.update_ui
    )

    view_was_splitted: BoolProperty(
        name="View was splitted",
        description="If the view was splitted",
        default=False,
        update=PropertyUpdates.update_ui,
    )
    # endregion

    # region request
    user_prompt: StringProperty(
        name="Prompt Text field",
        description="Talk with the AI through here",
        options={"TEXTEDIT_UPDATE"},
        update=PropertyUpdates.update_user_prompt,
        maxlen=10000,
    )

    user_prompt_tokens: IntProperty(update=PropertyUpdates.update_ui)

    answer: StringProperty(
        name="AI Answer",
        description="Answer from LLM API server",
        default="",
        update=PropertyUpdates.update_ui,
    )

    answer_parts: StringProperty(
        name="Answer in Parts",
        description="Array of Answer in parts serialized",
        default="",
        update=PropertyUpdates.update_ui,
    )

    is_streaming: BoolProperty(
        name="Streaming",
        description="If answer is currently being streamed",
        default=False,
        update=PropertyUpdates.update_ui,
    )
    # endregion

    # region LLM model
    api_details_updated: BoolProperty(
        name="API Details Updated",
        description="If the API details like key, url, headers and payload where already updated or not",
        default=False,
        update=PropertyUpdates.update_ui,
    )

    api_key: StringProperty(
        name="API Key",
        description="The API key of the currently used LLM",
        update=PropertyUpdates.update_ui,
    )

    api_url: StringProperty(
        name="API URL",
        description="The API url for currently selected LLM organization and model, sometimes different if streaming or not",
        update=PropertyUpdates.update_ui,
    )

    api_headers: StringProperty(
        name="HTTP Header",
        description="HTTP Header for the API call",
        update=PropertyUpdates.update_ui,
    )

    api_payload: StringProperty(
        name="API Payload",
        description="Payload for the API call",
        update=PropertyUpdates.update_ui,
    )
    # endregion

    # region request schema
    # naming follows the API schema
    req_schema_contents: StringProperty(
        name="Schema contents name",
        description="Name for the contents key that contains the API answer",
        update=PropertyUpdates.update_ui,
    )

    req_schema_role_system: StringProperty(
        name="Schema systems role name",
        description="Name for the system role key",
        update=PropertyUpdates.update_ui,
    )

    req_schema_role_user: StringProperty(
        name="Schema user role name",
        description="Name for the user role key",
        update=PropertyUpdates.update_ui,
    )

    req_schema_role_assistant: StringProperty(
        name="Schema assistent role name",
        description="Name for the assistent role key",
        update=PropertyUpdates.update_ui,
    )

    req_schema_parts: StringProperty(
        name="Schema parts name",
        description="Name for the parts key, inside the contents dictionary",
        update=PropertyUpdates.update_ui,
    )
    # endregion

    # region response schema
    # naming follows the API schema
    res_schema_root: StringProperty(
        name="´Response schema root name",
        description="Name for the root key",
        update=PropertyUpdates.update_ui,
    )

    res_schema_content: StringProperty(
        name="Response schema content name",
        description="Name for the content key",
        update=PropertyUpdates.update_ui,
    )

    res_schema_finish_reason: StringProperty(
        name="Response schema finish reason name",
        description="Name for the finish reason key",
        update=PropertyUpdates.update_ui,
    )
    # endregion

    # region attachments
    selected_attachment_item: IntProperty(
        name="Selected Attachment",
        description="Currently selected attachment",
        default=0,
        update=PropertyUpdates.update_ui,
    )

    selected_text_block: StringProperty(
        name="Select Text Block",
        description="The selected text block will be added as an attachment",
        update=PropertyUpdates.update_selected_text_block,
    )
    # endregion

    selected_attachment_tokens: IntProperty()

    # region history
    selected_history_item: IntProperty(
        name="Selected History Item",
        description="Currently selected history item",
        default=0,
        update=PropertyUpdates.update_selected_history_item,
    )
    # endregion

    selected_history_tokens: IntProperty()

    # region code completion
    update_code_completion: BoolProperty(
        name="Update Code Completion",
        description="Call the update function for code completion",
        update=PropertyUpdates.update_code_completion,
    )

    code_completion_text_name: StringProperty(
        name="Text Block Name",
        description="Name of Text Block where Code Completion was started from",
        default="",
        update=PropertyUpdates.update_ui,
    )

    code_completion_text_not_found: BoolProperty(
        name="Text Block Not Found",
        description="If the Text Block was not found",
        default=False,
        update=PropertyUpdates.update_ui,
    )

    code_completion_placeholder: StringProperty(
        name="Placeholder",
        description="Single line placeholder for inserted Code from Code Completion",
        default="# Waiting for code completion...",
        update=PropertyUpdates.update_ui,
    )

    code_completion_placeholder_begin: StringProperty(
        name="Placeholder Begin",
        description="Begin of placeholder for inserted Code from Code Completion",
        default="# Code Completion Begin",
        update=PropertyUpdates.update_ui,
    )

    code_completion_placeholder_end: StringProperty(
        name="Placeholder End",
        description="End of placeholder for inserted Code from Code Completion",
        default="# Code Completion End",
        update=PropertyUpdates.update_ui,
    )
    # endregion

    # region errors
    error_button_icon: StringProperty(
        name="Error Button Icon",
        description="Icon for Error Button",
        default="BLANK1",
        update=PropertyUpdates.update_ui,
    )

    error_button_text: StringProperty(
        name="Error Website URL",
        description="URL to website with more information about error",
        default=" ",
        update=PropertyUpdates.update_ui,
    )

    error_button_content: StringProperty(
        name="Content of error",
        description="Content to send when reporting Error",
        default="",
        update=PropertyUpdates.update_ui,
    )

    error_button_url: StringProperty(
        name="Error Website URL",
        description="URL to website with more information about error",
        default="https://platform.openai.com/docs/guides/error-codes",
        update=PropertyUpdates.update_ui,
    )

    error_title: StringProperty(
        name="Error Title",
        description="Title for Error",
        default="Error",
        update=PropertyUpdates.update_ui,
    )

    error_info: StringProperty(
        name="Error Information",
        description="Additional information about the error",
        default=" ",
        update=PropertyUpdates.update_ui,
    )

    error_message: StringProperty(
        name="Error message",
        description="Error message",
        default=" ",
        update=PropertyUpdates.update_ui,
    )
    # endregion

