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


from ..utils import dependencies
from bpy.types import AddonPreferences, Context, UILayout
from bpy import props
from ..operators.operator_website import CHAT_COMPANION_OT_website
from .property_updates import PropertyUpdates
from ..operators.operator_install_deps import CHAT_COMPANION_OT_install_deps
from .properties import ChatCompanionProperties
from .property_updates import PropertyUpdates
from ..utils import cc_globals
from .. import __package__ as base_package


class ChatCompanionPreferences(AddonPreferences):
    # this must match the addon name, use '__package__'
    # when defining this in a submodule of a python package.
    bl_idname = base_package

    # region enums
    _llm_organizations: set = (
        (
            "openai",
            "OpenAI",
            "...",
        ),
        (
            "deepseek",
            "DeepSeek",
            "...",
        ),
        (
            "anthropic",
            "Anthropic (Claude)",
            "...",
        ),
    )

    _open_ai_models = (
        ("gpt-5.3-codex", "GPT-5.3 Codex - 128,000 token", "GPT-5.3 Codex - 128,000 token"),
        ("gpt-5.5", "GPT-5.5 - 128,000 token", "GPT-5.5 - 128,000 token"),
        ("gpt-5.4-mini", "GPT-5.4 Mini - 128,000 token", "GPT-5.4 Mini - 128,000 token"),
    )

    _deepseek_models = (
        (
            "deepseek-v4-pro",
            "DeepSeek V4 Pro",
            "DeepSeek V4 Pro - thinking model that also supports function calling, usable as an agent",
        ),
        (
            "deepseek-v4-flash",
            "DeepSeek V4 Flash",
            "DeepSeek V4 Flash - thinking model (high), faster and more efficient",
        ),
    )

    tokens_dict = {
        "gpt-5.3-codex": 128000,
        "gpt-5.5": 128000,
        "gpt-5.4-mini": 128000,
        "deepseek-v4-pro": 128000,
        "deepseek-v4-flash": 128000,
        "claude-sonnet-4-6": 200000,
        "claude-opus-4-7": 200000,
        "claude-haiku-4-5-20251001": 200000,
    }

    # endregion

    # region LLMs
    open_ai_api_key: props.StringProperty(
        name="API Key.",
        description="Your OpenAI API key to use OpenAIs GPT models",
        # subtype="PASSWORD",
    )

    open_ai_base_url: props.StringProperty(
        name="Base URL",
        description="OpenAI-compatible API base URL",
        default="https://api.openai.com/v1",
    )

    deepseek_api_key: props.StringProperty(
        name="API Key.",
        description="Your DeepSeek API key",
        # subtype="PASSWORD",
    )

    deepseek_base_url: props.StringProperty(
        name="Base URL",
        description="DeepSeek-compatible API base URL",
        default="https://api.deepseek.com",
    )

    anthropic_api_key: props.StringProperty(
        name="API Key",
        description="Your Anthropic API key for Claude models",
    )

    anthropic_base_url: props.StringProperty(
        name="Base URL",
        description="Anthropic API base URL",
        default="https://api.anthropic.com/v1",
    )

    _anthropic_models = (
        ("claude-sonnet-4-6", "Claude Sonnet 4.6", "claude-sonnet-4-6"),
        ("claude-opus-4-7", "Claude Opus 4.7", "claude-opus-4-7"),
        ("claude-haiku-4-5-20251001", "Claude Haiku 4.5", "claude-haiku-4-5-20251001"),
    )

    anthropic_model: props.EnumProperty(
        name="Select Claude model:",
        description="Choose which Anthropic Claude model to use",
        items=_anthropic_models,
        default="claude-sonnet-4-6",
        update=PropertyUpdates.update_llm_details,
    )

    llm_organization: props.EnumProperty(
        name="LLM organization",
        description="Select the organization for your LLMs",
        items=_llm_organizations,
        default="openai",
        update=PropertyUpdates.update_llm_details,
    )

    open_ai_model: props.EnumProperty(
        name="Select OpenAI GPT model:",
        description="Choose what OpenAI model you want to use",
        items=_open_ai_models,
        default=_open_ai_models[0][0],
        update=PropertyUpdates.update_llm_details,
    )

    deepseek_model: props.EnumProperty(
        name="Select DeepSeek model:",
        description="Choose what DeepSeek model you want to use",
        items=_deepseek_models,
        default=_deepseek_models[0][0],
        update=PropertyUpdates.update_llm_details,
    )
    # endregion

    # region display
    text_width_adjust: props.FloatProperty(
        name="Adjusts the text width of the Addon Panel.",
        description="If the text in the addon panel is not displayed fully, adjust this to make each line fully readable (no dots inbetween). Default is 0",
        soft_min=-5,
        soft_max=5,
        step=0.1,
        precision=3,
        default=0,
        subtype="FACTOR",
    )
    # endregion

    # region agent mode
    agent_mode_enabled: props.BoolProperty(
        name="Agent Mode",
        description="Enable the tool-calling agent loop. When disabled, POPAgent behaves as a plain chat assistant.",
        default=True,
    )

    agent_max_iters: props.IntProperty(
        name="Max Iterations",
        description="Maximum tool-calling iterations per agent turn before the loop is aborted.",
        min=1,
        max=30,
        default=10,
    )

    developer_mode: props.BoolProperty(
        name="Developer Mode",
        description="Unlock the dev.run_python skill, which lets the agent execute arbitrary Python code. Enable only when testing in a safe environment.",
        default=False,
        update=PropertyUpdates.update_developer_mode,
    )
    # endregion

    # region connection
    use_streaming: props.BoolProperty(
        name="Stream",
        description="If you stream the answer, it will be generated word by word. This way you get an answer earlier and can read along while the answer is being generated.\nAll At Once generates the answer in one go, where you potentially need to wait a little bit longer until you see a result",
        default=True,
        update=PropertyUpdates.update_llm_details,
    )

    dependencies_checked: props.BoolProperty(
        name="Check Dependencies",
        description="Checks if all necessarry python modules for POPAgent have been installed",
        default=False,
    )

    timeout: props.FloatProperty(
        name="Timeout for API requests.",
        description="How many seconds does the addon try to get an answer from the LLM servers. You can adjust this if the servers are under heavy load",
        subtype="TIME",
        unit="TIME_ABSOLUTE",
        soft_min=0.001,
        soft_max=10000,
        step=1,
        precision=3,
        default=30,
    )
    # endregion

    # region DRAW
    def draw(self, context: Context):
        pcoll = cc_globals.preview_collections["main"]
        props: ChatCompanionProperties = context.scene.chat_companion_properties

        layout: UILayout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        # ! header
        header_box: UILayout = layout.box()
        header: UILayout = header_box.row(align=True)
        header.alignment = "CENTER"
        header.scale_y = 1.3
        header.label(
            text="POPAgent",
            icon_value=pcoll["chat_companion_icon"].icon_id,
        )
        version: UILayout = header_box.row(align=True)
        version.alignment = "CENTER"
        version.label(text="Blender 5.1 Agent", icon="KEYTYPE_JITTER_VEC")
        header_box.separator(factor=0.1)

        # ! api keys
        api_keys_container: UILayout = layout.column(align=True)
        api_keys_container.label(text="API keys", icon="KEYINGSET")
        api_keys_text_fields: UILayout = layout.column(align=False)

        # ! openai
        openai_split: UILayout = api_keys_text_fields.split(align=True, factor=2 / 5)
        openai_left: UILayout = openai_split.row(align=True)
        openai_left.alignment = "RIGHT"
        openai_left.label(
            text="OpenAI API key", icon_value=pcoll["openai_icon"].icon_id
        )
        openai_right: UILayout = openai_split.column(align=True)
        # api key
        openai_right.prop(self, "open_ai_api_key", text="")
        openai_right.prop(self, "open_ai_base_url", text="Base URL")
        # buttons below
        openai_buttons: UILayout = openai_right.row(align=True)
        openai_key_website: CHAT_COMPANION_OT_website = openai_buttons.operator(
            operator=CHAT_COMPANION_OT_website.bl_idname, text="Get key", icon="KEY_HLT"
        )
        openai_key_website.url = "https://platform.openai.com/account/api-keys"
        openai_docs: CHAT_COMPANION_OT_website = openai_buttons.operator(
            operator=CHAT_COMPANION_OT_website.bl_idname,
            text="API Docs",
            icon="QUESTION",
        )
        openai_docs.url = "https://developers.openai.com/api/docs"

        api_keys_text_fields.separator()

        # ! deepseek
        deepseek_split: UILayout = api_keys_text_fields.split(align=True, factor=2 / 5)
        deepseek_left: UILayout = deepseek_split.row(align=True)
        deepseek_left.alignment = "RIGHT"
        deepseek_left.label(text="DeepSeek API key", icon="OUTLINER_OB_LIGHT")
        deepseek_right: UILayout = deepseek_split.column(align=True)
        deepseek_right.prop(self, "deepseek_api_key", text="")
        deepseek_right.prop(self, "deepseek_base_url", text="Base URL")
        deepseek_buttons: UILayout = deepseek_right.row(align=True)
        deepseek_key_website: CHAT_COMPANION_OT_website = deepseek_buttons.operator(
            operator=CHAT_COMPANION_OT_website.bl_idname, text="Get key", icon="KEY_HLT"
        )
        deepseek_key_website.url = "https://platform.deepseek.com/api_keys"
        deepseek_docs: CHAT_COMPANION_OT_website = deepseek_buttons.operator(
            operator=CHAT_COMPANION_OT_website.bl_idname,
            text="API Docs",
            icon="QUESTION",
        )
        deepseek_docs.url = "https://api-docs.deepseek.com/"

        api_keys_text_fields.separator()

        # ! anthropic claude
        claude_split: UILayout = api_keys_text_fields.split(align=True, factor=2 / 5)
        claude_left: UILayout = claude_split.row(align=True)
        claude_left.alignment = "RIGHT"
        claude_left.label(text="Anthropic (Claude) API key", icon_value=pcoll["anthropic_icon"].icon_id)
        claude_right: UILayout = claude_split.column(align=True)
        claude_right.prop(self, "anthropic_api_key", text="")
        claude_right.prop(self, "anthropic_base_url", text="Base URL")
        claude_right.prop(self, "anthropic_model", text="Model")
        claude_buttons: UILayout = claude_right.row(align=True)
        claude_key_website: CHAT_COMPANION_OT_website = claude_buttons.operator(
            operator=CHAT_COMPANION_OT_website.bl_idname, text="Get key", icon="KEY_HLT"
        )
        claude_key_website.url = "https://console.anthropic.com/account/keys"

        # ! display
        display_settings = layout.column(align=True)
        display_settings.label(text="Display", icon="RESTRICT_VIEW_ON")
        offset_container = display_settings.row(align=True)
        offset_container.prop(self, "text_width_adjust", text="Adjust Text Width")

        layout.box()

        # ! agent mode
        agent_settings = layout.column(align=True)
        agent_settings.label(text="Agent Mode", icon="ARMATURE_DATA")
        agent_split: UILayout = agent_settings.split(align=True, factor=2 / 5)
        agent_left: UILayout = agent_split.row(align=True)
        agent_left.alignment = "RIGHT"
        agent_left.label(text="Enable Agent")
        agent_right: UILayout = agent_split.column(align=True)
        agent_right.prop(self, "agent_mode_enabled", text="")
        agent_iter_split: UILayout = agent_settings.split(align=True, factor=2 / 5)
        agent_iter_left: UILayout = agent_iter_split.row(align=True)
        agent_iter_left.alignment = "RIGHT"
        agent_iter_left.label(text="Max Iterations")
        agent_iter_right: UILayout = agent_iter_split.column(align=True)
        agent_iter_right.enabled = self.agent_mode_enabled
        agent_iter_right.prop(self, "agent_max_iters", text="")
        agent_dev_split: UILayout = agent_settings.split(align=True, factor=2 / 5)
        agent_dev_left: UILayout = agent_dev_split.row(align=True)
        agent_dev_left.alignment = "RIGHT"
        agent_dev_left.label(text="Developer Mode")
        agent_dev_right: UILayout = agent_dev_split.column(align=True)
        agent_dev_right.alert = self.developer_mode
        agent_dev_right.prop(self, "developer_mode", text="Unlock dev.run_python")

        layout.box()

        # ! system
        system_settings = layout.column(align=True)
        system_settings.label(text="System", icon="PLUGIN")

        # ! dependencies
        streaming_layout = system_settings.split(factor=2 / 5, align=True)
        streaming_layout.row()  # empty left side
        streaming_container = streaming_layout.column(align=True)

        # check dependencies
        if not self.dependencies_checked:
            deps_button = streaming_container.operator(
                operator=CHAT_COMPANION_OT_install_deps.bl_idname,
                text="Check Dependencies",
                icon="QUESTION",
            )
            deps_button.install_deps = False

        # deps installed, reinstall button
        elif dependencies.dependencies_installed:
            streaming_container.label(text="Dependencies installed.")
            deps_button = streaming_container.operator(
                operator=CHAT_COMPANION_OT_install_deps.bl_idname,
                text="Reinstall Dependencies",
                icon="KEYTYPE_JITTER_VEC",
            )
            deps_button.install_deps = True
            deps_button.force_install = True

        # deps not installed, install button
        else:
            not_installed_text = streaming_container.row(align=True)
            not_installed_text.alert = True
            if not dependencies.pip_installed:
                not_installed_text.label(text="Python installer pip not installed.")
            if not dependencies.httpx_installed:
                not_installed_text.label(text="Python module httpx not installed.")
            streaming_container.label(
                text="Streaming not available, using All at Once."
            )
            deps_button = streaming_container.operator(
                operator=CHAT_COMPANION_OT_install_deps.bl_idname,
                text="Install Dependencies",
                icon="KEYTYPE_EXTREME_VEC",
            )
            deps_button.install_deps = True
            streaming_container.separator()
            streaming_container.label(text="Or install it manually")
            if not dependencies.pip_installed:
                pip_link = streaming_container.operator(
                    operator=CHAT_COMPANION_OT_website.bl_idname,
                    text="How to install pip",
                    icon="URL",
                )
                pip_link.url = "https://pip.pypa.io/en/stable/installation/"
            if not dependencies.httpx_installed:
                httpx_link = streaming_container.operator(
                    operator=CHAT_COMPANION_OT_website.bl_idname,
                    text="How to install httpx",
                    icon="URL",
                )
                httpx_link.url = "https://www.python-httpx.org/"

        system_settings.separator()

        # ! connection
        stream_no_stream_split: UILayout = system_settings.split(
            align=True, factor=2 / 5
        )

        stream_no_stream_left: UILayout = stream_no_stream_split.row(align=True)
        stream_no_stream_left.alignment = "RIGHT"
        stream_no_stream_left.label(text="Answer")

        stream_no_stream_right: UILayout = stream_no_stream_split.row(align=True)
        stream_no_stream_right.use_property_split = False
        stream_no_stream_right.prop(self, "use_streaming", toggle=True, expand=True)
        stream_no_stream_right.prop(
            self,
            "use_streaming",
            toggle=True,
            invert_checkbox=True,
            text="All At Once",
            expand=True,
        )

        system_settings.separator()
        system_settings.enabled = True
        if props.is_streaming:
            system_settings.enabled = False

        # ! timeout
        timeout_container = system_settings.column(align=False)
        timeout_container.prop(
            self,
            "timeout",
            text="Request Timeout",
        )

        layout.box()

        disclaimer: UILayout = layout.column(align=True)
        disclaimer.label(text="Disclaimer", icon="INFO")
        disclaimer_text: UILayout = disclaimer.column(align=True)
        disclaimer_text.alignment = "RIGHT"
        disclaimer_text.label(
            text="POPAgent enables the use of LLMs from various providers."
        )
        disclaimer_text.label(
            text="You must obtain your own API keys from them and therefore comply"
        )
        disclaimer_text.label(
            text="with their terms and privacy policies. The developer of this addon"
        )
        disclaimer_text.label(
            text="assumes no responsibility or liability for any misuse or damages"
        )
        disclaimer_text.label(text="resulting from its use.")

    # endregion
