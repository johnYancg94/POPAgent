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
from ..utils import dependencies
from ..utils import cc_globals
from .panel import POLYGONINGENIEUR_panel
from ..operators.operator_ask import CHAT_COMPANION_OT_ask
from ..utils.utils import wrap_string_to_panel, can_send_prompt
from ..operators.operator_open_prefs import CHAT_COMPANION_OT_open_prefs
from ..operators.operator_website import CHAT_COMPANION_OT_website
from ..operators.operator_change_llm import CHAT_COMPANION_OT_select_mimo
from ..operators.operator_change_llm import CHAT_COMPANION_OT_select_open_ai
from ..operators.operator_select_minimax import CHAT_COMPANION_OT_select_minimax
from ..operators.operator_full_version import CHAT_COMPANION_OT_full_version
from ..operators.operator_image_attachments import (
    CHAT_COMPANION_OT_add_blender_image,
    CHAT_COMPANION_OT_add_image_file,
    CHAT_COMPANION_OT_clear_image_attachments,
    CHAT_COMPANION_OT_paste_image_attachment,
    CHAT_COMPANION_OT_remove_image_attachment,
)
from ..properties.properties import ChatCompanionProperties
from ..properties.addon_preferences import ChatCompanionPreferences
from ..providers import OpenAICompatProvider, AnthropicProvider
from .. import __package__ as base_package


class CHAT_COMPANION_PT_prompt(POLYGONINGENIEUR_panel, Panel):
    bl_idname = "CHAT_COMPANION_PT_prompt"
    bl_label = "       POPAgent"
    bl_order = 0
    bl_options = {"HEADER_LAYOUT_EXPAND"}

    def draw_header(self, context):
        """Show LLM organization selection."""

        layout: UILayout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        split: UILayout = layout.split(factor=1 / 5)
        left: UILayout = split.row()
        left.alignment = "LEFT"
        pcoll = cc_globals.preview_collections["main"]
        left.label(text="", icon_value=pcoll["chat_companion_icon"].icon_id)

        right: UILayout = split.row()
        right.alignment = "RIGHT"
        right.operator(
            operator=CHAT_COMPANION_OT_open_prefs.bl_idname, text="", icon="PREFERENCES"
        )
        right.separator(factor=1)

    def draw(self, context):
        pcoll = cc_globals.preview_collections["main"]
        props: ChatCompanionProperties = context.scene.chat_companion_properties
        prefs: ChatCompanionPreferences = context.preferences.addons[
            base_package
        ].preferences

        layout: UILayout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        # model selection
        model_selection: UILayout = layout.column(align=True)
        llm_selection: UILayout = model_selection.column(align=True)
        llms: UILayout = llm_selection.row(align=True)
        llms.enabled = not props.waiting_for_answer
        llms.scale_y = 1.1
        llms.use_property_split = False
        # since we want to use custom icons for the enum property,
        # and this doesn't work or I didn't figure it out,
        # as a workaround we use three operators to select the llm organization
        llms.operator(
            operator=CHAT_COMPANION_OT_select_open_ai.bl_idname,
            icon_value=pcoll["openai_icon"].icon_id,
            depress=True if prefs.llm_organization == "openai" else False,
        )
        llms.operator(
            operator=CHAT_COMPANION_OT_select_mimo.bl_idname,
            text="MiMo",
            icon_value=pcoll["mimo_icon"].icon_id,
            depress=True if prefs.llm_organization == "mimo" else False,
        )
        if cc_globals.cc_full:
            from ..full.operator_change_llm import CHAT_COMPANION_OT_select_deepseek_ai

            llms.operator(
                operator=CHAT_COMPANION_OT_select_deepseek_ai.bl_idname,
                text="DeepSeek",
                icon_value=pcoll["deepseek_icon"].icon_id,
                depress=True if prefs.llm_organization == "deepseek" else False,
            )
        else:
            llms_full: UILayout = llms.row(align=True)
            llms_full.enabled = False

        llms.operator(
            operator=CHAT_COMPANION_OT_select_minimax.bl_idname,
            text="minimax",
            icon_value=pcoll["anthropic_icon"].icon_id,
            depress=True if prefs.llm_organization == "minimax" else False,
        )

        # ! API key info
        api_key: str | None = None
        if prefs.llm_organization == "openai":
            api_key = prefs.open_ai_api_key
        elif prefs.llm_organization == "mimo":
            api_key = prefs.mimo_api_key
        elif prefs.llm_organization == "deepseek":
            api_key = prefs.deepseek_api_key
        elif prefs.llm_organization == "minimax":
            api_key = prefs.minimax_api_key

        no_api_key = api_key is None or len(api_key) == 0 or api_key == ""

        def draw_connection_test_button(row: UILayout):
            if no_api_key:
                return
            test_button = row.row(align=True)
            test_button.enabled = (
                not props.waiting_for_answer
                and not props.connection_test_running
            )
            test_button.operator(
                operator="chat_companion.test_connection",
                text="",
                text_ctxt="*",
                icon="LINKED",
            )

        # ! openai
        if prefs.llm_organization == "openai":
            # choose between different models ("gpt-3.5-turbo", "gpt-4", ...)
            gpt_model_container: UILayout = llm_selection.column(align=True)
            model_selection = gpt_model_container.row(align=True)
            model_selection.prop(prefs, "open_ai_model", text="")
            draw_connection_test_button(model_selection)
            # extra model links
            model_info_link = model_selection.operator(
                operator=CHAT_COMPANION_OT_website.bl_idname, text="", icon="QUESTION"
            )
            model_info_link.url = "https://platform.openai.com/docs/models"

        # ! mimo
        elif prefs.llm_organization == "mimo":
            mimo_model_container: UILayout = llm_selection.column(align=True)
            mimo_model_selection = mimo_model_container.row(align=True)
            mimo_model_selection.prop(prefs, "mimo_model", text="")
            draw_connection_test_button(mimo_model_selection)
            model_info_link = mimo_model_selection.operator(
                operator=CHAT_COMPANION_OT_website.bl_idname, text="", icon="QUESTION"
            )
            model_info_link.url = "https://platform.xiaomimimo.com/docs/en-US/api/chat/openai-api"

        # ! deepseek
        elif prefs.llm_organization == "deepseek":
            deepseek_model_container: UILayout = llm_selection.column(align=True)
            deepseek_model_selection = deepseek_model_container.row(align=True)
            deepseek_model_selection.prop(prefs, "deepseek_model", text="")
            draw_connection_test_button(deepseek_model_selection)
            model_info_link = deepseek_model_selection.operator(
                operator=CHAT_COMPANION_OT_website.bl_idname, text="", icon="QUESTION"
            )
            model_info_link.url = "https://api-docs.deepseek.com/api/create-chat-completion"

        # ! minimax (Anthropic-Messages-API compatible)
        elif prefs.llm_organization == "minimax":
            minimax_model_container: UILayout = llm_selection.column(align=True)
            minimax_model_selection = minimax_model_container.row(align=True)
            minimax_model_selection.prop(prefs, "minimax_model", text="")
            draw_connection_test_button(minimax_model_selection)
            model_info_link = minimax_model_selection.operator(
                operator=CHAT_COMPANION_OT_website.bl_idname, text="", icon="QUESTION"
            )
            model_info_link.url = "https://platform.minimaxi.com/docs/llms.txt"

        if no_api_key:
            api_info_container = layout.column(align=True)

            # api info text
            no_api_key_split: UILayout = api_info_container.grid_flow(
                row_major=True, columns=2, align=True
            )
            no_api_key_left: UILayout = no_api_key_split.row(align=True)
            no_api_key_left.alert = True
            no_api_key_left.operator(
                operator=CHAT_COMPANION_OT_open_prefs.bl_idname,
                text="",
                icon="KEYINGSET",
            )
            no_api_key_right: UILayout = no_api_key_split.column(align=True)
            no_api_key_right.alert = True
            text_list = wrap_string_to_panel(
                context, "Please enter your API key in the addon preferences"
            )
            for index, line in enumerate(text_list):
                if index == 0:

                    no_api_key_right.label(text=line)
                else:
                    no_api_key_right.label(text=line)

        # ! connectivity test
        if not no_api_key:
            result = props.connection_test_result
            if result:
                status_row: UILayout = layout.row(align=True)
                if result == "ok":
                    status_row.label(
                        text=props.connection_test_message, icon="CHECKMARK"
                    )
                else:
                    status_row.alert = True
                    status_row.label(
                        text=props.connection_test_message, icon="ERROR"
                    )

        layout.separator()

        # ! prompt
        multimodal_row = layout.row(align=True)
        multimodal_row.enabled = not props.waiting_for_answer
        multimodal_row.prop(props, "multimodal_enabled", text="Multimodal Images", toggle=True)

        prompt: UILayout = layout.row(align=True)
        prompt_text = prompt.column(align=True)
        prompt_text.scale_y = 1.4
        prompt_text.enabled = not props.waiting_for_answer
        prompt_text.prop(props, "user_prompt", text="")

        prompt_icon: UILayout = prompt.column(align=True)
        prompt_icon.scale_y = 1.4
        prompt_icon.scale_x = 1.2
        if props.waiting_for_answer:
            prompt_icon.enabled = True
            prompt_icon.operator(
                operator="chat_companion.cancel_request",
                text="",
                icon="CANCEL",
            )
        else:
            prompt_icon.enabled = can_send_prompt(context)
            ask_operator = prompt_icon.operator(
                operator=CHAT_COMPANION_OT_ask.bl_idname,
                text="",
                icon="RIGHTARROW_THIN",
            )

            ask_operator.user_prompt = props.user_prompt
            ask_operator.use_streaming = (
                prefs.use_streaming and dependencies.dependencies_installed
            )

        preset_row = layout.row(align=True)
        preset_row.enabled = not props.waiting_for_answer
        preset_row.operator(
            operator="chat_companion.set_render_prep_prompt",
            text="准备渲染",
            icon="RENDER_STILL",
        )

        if props.multimodal_enabled:
            self._draw_image_inputs(context, layout, props, prefs)

        # show prompt below text field when it is multiline only
        wrapped_prompt = wrap_string_to_panel(context=context, string=props.user_prompt)
        if len(wrapped_prompt) > 1:
            promt_full = layout.column(align=True)
            for line in wrapped_prompt:
                line_col = promt_full.column()
                line_col.label(text=line)
                line_col.scale_y = 0.8

    def _draw_image_inputs(self, context, layout, props, prefs):
        provider = _provider_for_prefs(prefs)
        image_supported = bool(provider and provider.supports_image_input(prefs))
        images = context.scene.chat_companion_image_attachments

        box = layout.box()
        box.enabled = not props.waiting_for_answer

        header = box.row(align=True)
        header.label(text="Images", icon="IMAGE_DATA")
        header.operator(
            operator=CHAT_COMPANION_OT_paste_image_attachment.bl_idname,
            text="",
            icon="PASTEDOWN",
        )
        header.operator(
            operator=CHAT_COMPANION_OT_add_image_file.bl_idname,
            text="",
            icon="ADD",
        )
        header.operator(
            operator=CHAT_COMPANION_OT_clear_image_attachments.bl_idname,
            text="",
            icon="TRASH",
        )

        if not image_supported:
            warning = box.row(align=True)
            warning.alert = True
            warning.label(text="Current model has image input disabled")

        blender_row = box.row(align=True)
        blender_row.prop_search(
            props,
            "selected_blender_image",
            context.blend_data,
            "images",
            text="",
            icon="IMAGE_DATA",
        )
        blender_row.operator(
            operator=CHAT_COMPANION_OT_add_blender_image.bl_idname,
            text="",
            icon="ADD",
        )

        if len(images) > 0:
            list_row = box.row(align=True)
            list_row.template_list(
                "CHAT_COMPANION_UL_item_image_attachment",
                "",
                context.scene,
                "chat_companion_image_attachments",
                props,
                "selected_image_attachment_item",
                rows=min(3, len(images)),
            )
            list_tools = list_row.column(align=True)
            list_tools.operator(
                operator=CHAT_COMPANION_OT_remove_image_attachment.bl_idname,
                text="",
                icon="REMOVE",
            )
        else:
            empty = box.row(align=True)
            empty.label(text="Paste, choose, or add an image")


def _provider_for_prefs(prefs):
    if prefs.llm_organization == "openai":
        return OpenAICompatProvider("openai")
    if prefs.llm_organization == "mimo":
        return OpenAICompatProvider("mimo")
    if prefs.llm_organization == "deepseek":
        return OpenAICompatProvider("deepseek")
    if prefs.llm_organization == "minimax":
        return AnthropicProvider()
    return None
