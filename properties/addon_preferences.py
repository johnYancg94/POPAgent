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
from ..panels.panel_skills import draw_skills_ui
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
            "mimo",
            "MiMo",
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
        ("gpt-5.3-codex", "GPT-5.3 Codex", "GPT-5.3 Codex"),
        ("gpt-5.5", "GPT-5.5", "GPT-5.5"),
        ("gpt-5.4-mini", "GPT-5.4 Mini", "GPT-5.4 Mini"),
    )

    _mimo_models = (
        ("mimo-v2.5-pro", "MiMo V2.5 Pro", "MiMo V2.5 Pro"),
        ("mimo-v2.5", "MiMo V2.5", "MiMo V2.5"),
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
        "mimo-v2.5-pro": 1000000,
        "mimo-v2.5": 1000000,
        "gpt-5.3-codex": 128000,
        "gpt-5.5": 128000,
        "gpt-5.4-mini": 128000,
        "deepseek-v4-pro": 128000,
        "deepseek-v4-flash": 128000,
        "claude-sonnet-4-6": 200000,
        "claude-opus-4-7": 200000,
        "claude-haiku-4-5-20251001": 200000,
    }

    _answer_display_modes = (
        (
            "READABLE",
            "Readable",
            "Render common Markdown as clean panel blocks.",
        ),
        (
            "COMPACT",
            "Compact",
            "Use shorter previews for narrow or dense panel reading.",
        ),
        (
            "RAW",
            "Raw Markdown",
            "Show the original Markdown text in the panel.",
        ),
    )

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

    mimo_api_key: props.StringProperty(
        name="API Key.",
        description="Your MiMo API key",
        # subtype="PASSWORD",
    )

    mimo_base_url: props.StringProperty(
        name="Base URL",
        description="MiMo OpenAI-compatible API base URL",
        default="https://api.xiaomimimo.com/v1",
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

    mimo_model: props.EnumProperty(
        name="Select MiMo model:",
        description="Choose what MiMo model you want to use",
        items=_mimo_models,
        default=_mimo_models[0][0],
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

    answer_display_mode: props.EnumProperty(
        name="Answer Display Mode",
        description="Choose how AI answers are displayed in the Answer panel",
        items=_answer_display_modes,
        default="READABLE",
    )

    answer_code_preview_lines: props.IntProperty(
        name="Code Preview Lines",
        description="Number of code lines shown before a code block is collapsed",
        min=1,
        max=80,
        default=12,
    )

    developer_mode: props.BoolProperty(
        name="Developer Mode",
        description="Show execution traces, detailed usage records, and advanced skill permission controls.",
        default=False,
    )

    skill_permission_overrides_json: props.StringProperty(
        name="Skill Permission Overrides",
        description="Persistent JSON overrides for per-skill confirmation behavior.",
        default="{}",
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

    max_history_context: props.IntProperty(
        name="Max History Context",
        description="Maximum enabled history turns sent as context for each prompt. Set to 0 to start each prompt without history context.",
        min=0,
        max=50,
        default=5,
    )

    agent_context_window: props.IntProperty(
        name="Context Window (tokens)",
        description="Model context window in tokens; history is trimmed to fit a budget derived from this. Default 256k.",
        min=8000,
        max=2_000_000,
        default=256000,
    )

    agent_context_1m_enabled: props.BoolProperty(
        name="Enable 1M Context",
        description="Use a 1,000,000-token budget ceiling for models that support million-token context. Only effective if the selected model actually supports it.",
        default=False,
    )

    agent_skill_triage_threshold: props.IntProperty(
        name="Skill Triage Threshold",
        description="When the number of enabled skills exceeds this, expose only core skills as tools and offer the rest as an on-demand catalog. Default 60 keeps all skills directly callable for typical setups.",
        min=1,
        max=500,
        default=60,
    )

    # region usage log (append-only JSONL sink for team-wide aggregation)
    trace_log_enabled: props.BoolProperty(
        name="Log Agent Usage",
        description="Append one JSON line per finished agent turn to disk (skill names, outcomes, signals). Used to pool team usage and find failure modes, denied skills, and unmatched requests. Metadata only by default — no scene data or asset paths.",
        default=True,
    )

    trace_log_dir: props.StringProperty(
        name="Usage Log Folder",
        description="Folder for per-day usage logs, written as <folder>/<user id>/<YYYY-MM-DD>.jsonl. Point team members at a synced/NAS folder to pool logs. Empty = ~/POPAgent_traces.",
        subtype="DIR_PATH",
        default="",
    )

    trace_log_user_id: props.StringProperty(
        name="Usage Log User ID",
        description="Pseudonymous, stable per-install id used to namespace this user's log files. Auto-generated on first log if empty; reveals nothing about the host.",
        default="",
    )

    trace_log_full: props.BoolProperty(
        name="Log Full Request Text",
        description="Also store full prompt text and tool argument/result previews in each log line. Off by default to avoid leaking client asset paths or scene details. Only enable for trusted internal aggregation.",
        default=True,
    )
    # endregion

    blender_api_docs_url: props.StringProperty(
        name="Blender API Docs URL",
        description="Official Blender Python API documentation root used by blender.api_search.",
        default="https://docs.blender.org/api/5.1/",
    )

    blender_api_docs_path: props.StringProperty(
        name="Local Blender API Docs",
        description="Optional local Blender Python API HTML documentation folder used as fallback or preferred source.",
        subtype="DIR_PATH",
        default="",
    )

    blender_api_docs_prefer_local: props.BoolProperty(
        name="Prefer Local API Docs",
        description="Search the configured local Blender API docs before official online docs.",
        default=False,
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
        description="Maximum seconds to wait for a complete LLM response (read timeout). Connection timeout is fixed at 5 s. Increase for slow reasoning models (e.g. 300–600 s)",
        subtype="TIME",
        unit="TIME_ABSOLUTE",
        soft_min=0.001,
        soft_max=10000,
        step=1,
        precision=3,
        default=300,
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

        # ! mimo
        mimo_split: UILayout = api_keys_text_fields.split(align=True, factor=2 / 5)
        mimo_left: UILayout = mimo_split.row(align=True)
        mimo_left.alignment = "RIGHT"
        mimo_left.label(text="MiMo API key", icon_value=pcoll["mimo_icon"].icon_id)
        mimo_right: UILayout = mimo_split.column(align=True)
        mimo_right.prop(self, "mimo_api_key", text="")
        mimo_right.prop(self, "mimo_base_url", text="Base URL")
        mimo_right.prop(self, "mimo_model", text="Model")
        mimo_buttons: UILayout = mimo_right.row(align=True)
        mimo_key_website: CHAT_COMPANION_OT_website = mimo_buttons.operator(
            operator=CHAT_COMPANION_OT_website.bl_idname, text="Get key", icon="KEY_HLT"
        )
        mimo_key_website.url = "https://platform.xiaomimimo.com/"
        mimo_docs: CHAT_COMPANION_OT_website = mimo_buttons.operator(
            operator=CHAT_COMPANION_OT_website.bl_idname,
            text="API Docs",
            icon="QUESTION",
        )
        mimo_docs.url = "https://platform.xiaomimimo.com/docs/en-US/api/chat/openai-api"

        api_keys_text_fields.separator()

        # ! deepseek
        deepseek_split: UILayout = api_keys_text_fields.split(align=True, factor=2 / 5)
        deepseek_left: UILayout = deepseek_split.row(align=True)
        deepseek_left.alignment = "RIGHT"
        deepseek_left.label(text="DeepSeek API key", icon_value=pcoll["deepseek_icon"].icon_id)
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
        answer_mode_container = display_settings.row(align=True)
        answer_mode_container.prop(self, "answer_display_mode", text="Answer")
        code_preview_container = display_settings.row(align=True)
        code_preview_container.prop(self, "answer_code_preview_lines", text="Code Preview")

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
        agent_history_split: UILayout = agent_settings.split(align=True, factor=2 / 5)
        agent_history_left: UILayout = agent_history_split.row(align=True)
        agent_history_left.alignment = "RIGHT"
        agent_history_left.label(text="Max History Context")
        agent_history_right: UILayout = agent_history_split.column(align=True)
        agent_history_right.prop(self, "max_history_context", text="")
        api_docs_split: UILayout = agent_settings.split(align=True, factor=2 / 5)
        api_docs_left: UILayout = api_docs_split.row(align=True)
        api_docs_left.alignment = "RIGHT"
        api_docs_left.label(text="Blender API Docs")
        api_docs_right: UILayout = api_docs_split.column(align=True)
        api_docs_right.prop(self, "blender_api_docs_url", text="URL")
        api_docs_right.prop(self, "blender_api_docs_path", text="Local")
        api_docs_right.prop(self, "blender_api_docs_prefer_local", text="Prefer Local")

        layout.box()

        # ! usage log
        usage_settings = layout.column(align=True)
        usage_settings.label(text="Usage Log", icon="FILE_TEXT")
        usage_enable_split: UILayout = usage_settings.split(align=True, factor=2 / 5)
        usage_enable_left: UILayout = usage_enable_split.row(align=True)
        usage_enable_left.alignment = "RIGHT"
        usage_enable_left.label(text="Log Agent Usage")
        usage_enable_right: UILayout = usage_enable_split.column(align=True)
        usage_enable_right.prop(self, "trace_log_enabled", text="")
        usage_body: UILayout = usage_settings.column(align=True)
        usage_body.enabled = self.trace_log_enabled
        usage_dir_split: UILayout = usage_body.split(align=True, factor=2 / 5)
        usage_dir_left: UILayout = usage_dir_split.row(align=True)
        usage_dir_left.alignment = "RIGHT"
        usage_dir_left.label(text="Log Folder")
        usage_dir_right: UILayout = usage_dir_split.column(align=True)
        usage_dir_right.prop(self, "trace_log_dir", text="")
        usage_dir_right.prop(self, "trace_log_full", text="Log Full Request Text")

        layout.box()

        # ! skills
        skills_settings = layout.column(align=True)
        skills_settings.label(text="Skills", icon="TOOL_SETTINGS")
        draw_skills_ui(skills_settings, prefs=self, developer_mode=self.developer_mode)

        layout.box()

        # ! system
        system_settings = layout.column(align=True)
        system_settings.label(text="System", icon="PLUGIN")
        system_settings.prop(self, "developer_mode", text="Developer Mode")

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
