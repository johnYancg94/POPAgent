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
            "minimax",
            "minimax",
            "Anthropic Messages API compatible (M3 / M2.7)",
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
        "MiniMax-M3": 200000,
        "MiniMax-M2.7": 200000,
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

    _preferences_tabs = (
        ("MODELS", "Models", "API keys, provider endpoints, and model context"),
        ("AGENT", "Agent", "Agent behavior, documentation, and web search"),
        ("SKILLS", "Skills", "Agent Skills and callable tools"),
        ("INTERFACE", "Interface", "Answer and panel display settings"),
        ("LOGS", "Logs", "Agent usage logging"),
        ("SYSTEM", "System", "Dependencies, connection, and advanced settings"),
    )

    _quick_permission_presets = (
        ("DEFAULT", "默认权限", "Use each callable tool's default permission preset"),
        ("AUTO", "自动权限", "Allow callable tools to run automatically"),
    )

    # endregion

    preferences_tab: props.EnumProperty(
        name="Preferences Tab",
        description="Choose which POPAgent settings module to display",
        items=_preferences_tabs,
        default="MODELS",
    )

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

    minimax_api_key: props.StringProperty(
        name="API Key",
        description="Your minimax API key (Anthropic Messages API compatible)",
    )

    minimax_base_url: props.StringProperty(
        name="Base URL",
        description=(
            "minimax Anthropic-compatible base URL. The addon appends "
            "/messages, so the path must end with the API version (e.g. /v1) "
            "to match the Anthropic SDK's behavior."
        ),
        default="https://api.minimaxi.com/anthropic/v1",
    )

    _minimax_models = (
        ("MiniMax-M3", "MiniMax-M3", "MiniMax-M3 (flagship)"),
        ("MiniMax-M2.7", "MiniMax-M2.7", "MiniMax-M2.7 (fast)"),
    )

    minimax_model: props.EnumProperty(
        name="Select minimax model:",
        description="Choose which minimax model to use",
        items=_minimax_models,
        default="MiniMax-M3",
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

    quick_permission_preset: props.EnumProperty(
        name="Quick Permissions",
        description="Fast global permission preset for Agent callable tools",
        items=_quick_permission_presets,
        default="AUTO",
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
        description=(
            "Maximum tool-calling iterations per agent turn before the loop is aborted. "
            "Raise for long multi-step pipelines. Hard cap 200 enforced in code."
        ),
        min=1,
        max=100,
        default=20,
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
        description="When the number of enabled skills exceeds this, expose only core skills as tools and offer the rest as an on-demand catalog. Default 80 keeps all skills directly callable for typical setups.",
        min=1,
        max=500,
        default=80,
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

    web_search_enabled: props.BoolProperty(
        name="Enable Web Search",
        description="Allow POPAgent to call Tavily when the user asks for online or current information.",
        default=True,
    )

    tavily_api_key: props.StringProperty(
        name="Tavily API Key",
        description="Tavily API key used by web.search.",
        subtype="PASSWORD",
        default="",
    )

    tavily_endpoint: props.StringProperty(
        name="Tavily Endpoint",
        description="Tavily Search API endpoint.",
        default="https://api.tavily.com/search",
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
        layout: UILayout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

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

        tabs = layout.row(align=True)
        tabs.use_property_split = False
        tabs.prop(self, "preferences_tab", expand=True)
        layout.separator()

        drawers = {
            "MODELS": self._draw_models_tab,
            "AGENT": self._draw_agent_tab,
            "SKILLS": self._draw_skills_tab,
            "INTERFACE": self._draw_interface_tab,
            "LOGS": self._draw_logs_tab,
            "SYSTEM": self._draw_system_tab,
        }
        drawers[self.preferences_tab](layout, context)

    def _draw_models_tab(self, layout: UILayout, _context: Context):
        pcoll = cc_globals.preview_collections["main"]
        self._draw_quick_permissions(layout)

        settings = layout.column(align=True)
        settings.label(text="API Keys and Providers", icon="KEYINGSET")

        providers = (
            (
                "OpenAI",
                "openai_icon",
                "open_ai_api_key",
                "open_ai_base_url",
                None,
                "https://platform.openai.com/account/api-keys",
                "https://developers.openai.com/api/docs",
            ),
            (
                "MiMo",
                "mimo_icon",
                "mimo_api_key",
                "mimo_base_url",
                "mimo_model",
                "https://platform.xiaomimimo.com/",
                "https://platform.xiaomimimo.com/docs/en-US/api/chat/openai-api",
            ),
            (
                "DeepSeek",
                "deepseek_icon",
                "deepseek_api_key",
                "deepseek_base_url",
                None,
                "https://platform.deepseek.com/api_keys",
                "https://api-docs.deepseek.com/",
            ),
            (
                "minimax",
                "anthropic_icon",
                "minimax_api_key",
                "minimax_base_url",
                "minimax_model",
                "https://platform.minimaxi.com/user-center/payment/token-plan",
                None,
            ),
        )
        for name, icon, api_key, base_url, model, key_url, docs_url in providers:
            split = settings.split(align=True, factor=2 / 5)
            label = split.row(align=True)
            label.alignment = "RIGHT"
            label.label(text=f"{name} API key", icon_value=pcoll[icon].icon_id)
            fields = split.column(align=True)
            fields.prop(self, api_key, text="")
            fields.prop(self, base_url, text="Base URL")
            if model:
                fields.prop(self, model, text="Model")
            buttons = fields.row(align=True)
            key_button: CHAT_COMPANION_OT_website = buttons.operator(
                operator=CHAT_COMPANION_OT_website.bl_idname,
                text="Get key",
                icon="KEY_HLT",
            )
            key_button.url = key_url
            if docs_url:
                docs_button: CHAT_COMPANION_OT_website = buttons.operator(
                    operator=CHAT_COMPANION_OT_website.bl_idname,
                    text="API Docs",
                    icon="QUESTION",
                )
                docs_button.url = docs_url
            settings.separator()

        context_settings = layout.column(align=True)
        context_settings.label(text="Context", icon="ALIGN_JUSTIFY")
        context_settings.prop(
            self, "agent_context_1m_enabled", text="Enable 1M Context"
        )

    def _draw_quick_permissions(self, layout: UILayout):
        quick = layout.column(align=True)
        quick.label(text="Agent Permissions", icon="LOCKED")
        row = quick.row(align=True)
        row.use_property_split = False
        for preset, label, _description in self._quick_permission_presets:
            button = row.operator(
                "popagent.apply_quick_permission_preset",
                text=label,
                depress=self.quick_permission_preset == preset,
            )
            button.preset = preset
        quick.separator()

    def _draw_agent_tab(self, layout: UILayout, _context: Context):
        settings = layout.column(align=True)
        settings.label(text="Agent Mode", icon="ARMATURE_DATA")
        settings.prop(self, "agent_mode_enabled", text="Enable Agent")

        agent_body = settings.column(align=True)
        agent_body.enabled = self.agent_mode_enabled
        agent_body.prop(self, "agent_max_iters", text="Max Iterations")
        agent_body.label(text="1-100 (hard cap 200)")
        agent_body.prop(self, "max_history_context", text="Max History Context")

        settings.separator()
        settings.label(text="Blender API Documentation", icon="HELP")
        settings.prop(self, "blender_api_docs_url", text="URL")
        settings.prop(self, "blender_api_docs_path", text="Local")
        settings.prop(self, "blender_api_docs_prefer_local", text="Prefer Local")

        settings.separator()
        settings.label(text="Web Search", icon="URL")
        settings.prop(self, "web_search_enabled", text="Enable")
        web_search_body = settings.column(align=True)
        web_search_body.enabled = self.web_search_enabled
        web_search_body.prop(self, "tavily_api_key", text="Tavily API Key")
        web_search_body.prop(self, "tavily_endpoint", text="Endpoint")

    def _draw_skills_tab(self, layout: UILayout, _context: Context):
        settings = layout.column(align=True)
        settings.label(text="Agent Skills and Callable Tools", icon="TOOL_SETTINGS")
        draw_skills_ui(settings, prefs=self, developer_mode=self.developer_mode)

    def _draw_interface_tab(self, layout: UILayout, _context: Context):
        settings = layout.column(align=True)
        settings.label(text="Display", icon="RESTRICT_VIEW_ON")
        settings.prop(self, "text_width_adjust", text="Adjust Text Width")
        settings.prop(self, "answer_display_mode", text="Answer")
        settings.prop(self, "answer_code_preview_lines", text="Code Preview")

    def _draw_logs_tab(self, layout: UILayout, _context: Context):
        settings = layout.column(align=True)
        settings.label(text="Usage Log", icon="FILE_TEXT")
        settings.prop(self, "trace_log_enabled", text="Log Agent Usage")
        log_body = settings.column(align=True)
        log_body.enabled = self.trace_log_enabled
        log_body.prop(self, "trace_log_dir", text="Log Folder")
        log_body.prop(self, "trace_log_full", text="Log Full Request Text")

    def _draw_system_tab(self, layout: UILayout, context: Context):
        props: ChatCompanionProperties = context.scene.chat_companion_properties
        settings = layout.column(align=True)
        settings.label(text="System", icon="PLUGIN")
        settings.prop(self, "developer_mode", text="Developer Mode")

        dependencies_box = settings.box()
        dependencies_box.label(text="Dependencies", icon="PACKAGE")
        self._draw_dependencies(dependencies_box)

        connection = settings.column(align=True)
        connection.enabled = not props.is_streaming
        connection.label(text="Connection", icon="LINKED")
        stream_row = connection.row(align=True)
        stream_row.use_property_split = False
        stream_row.prop(self, "use_streaming", toggle=True, expand=True)
        stream_row.prop(
            self,
            "use_streaming",
            toggle=True,
            invert_checkbox=True,
            text="All At Once",
            expand=True,
        )
        connection.prop(self, "timeout", text="Request Timeout")

        settings.separator()
        disclaimer: UILayout = settings.column(align=True)
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

    def _draw_dependencies(self, layout: UILayout):
        if not self.dependencies_checked:
            deps_button = layout.operator(
                operator=CHAT_COMPANION_OT_install_deps.bl_idname,
                text="Check Dependencies",
                icon="QUESTION",
            )
            deps_button.install_deps = False
            return

        if dependencies.dependencies_installed:
            layout.label(text="Dependencies installed.")
            deps_button = layout.operator(
                operator=CHAT_COMPANION_OT_install_deps.bl_idname,
                text="Reinstall Dependencies",
                icon="KEYTYPE_JITTER_VEC",
            )
            deps_button.install_deps = True
            deps_button.force_install = True
            return

        missing = layout.column(align=True)
        missing.alert = True
        if not dependencies.pip_installed:
            missing.label(text="Python installer pip not installed.")
        if not dependencies.httpx_installed:
            missing.label(text="Python module httpx not installed.")
        if not dependencies.yaml_installed:
            missing.label(text="Python module PyYAML not installed.")
        layout.label(text="Streaming not available, using All at Once.")
        deps_button = layout.operator(
            operator=CHAT_COMPANION_OT_install_deps.bl_idname,
            text="Install Dependencies",
            icon="KEYTYPE_EXTREME_VEC",
        )
        deps_button.install_deps = True
        layout.separator()
        layout.label(text="Or install it manually")
        dependency_links = (
            (
                dependencies.pip_installed,
                "How to install pip",
                "https://pip.pypa.io/en/stable/installation/",
            ),
            (
                dependencies.httpx_installed,
                "How to install httpx",
                "https://www.python-httpx.org/",
            ),
            (
                dependencies.yaml_installed,
                "PyYAML documentation",
                "https://pyyaml.org/wiki/PyYAMLDocumentation",
            ),
        )
        for installed, text, url in dependency_links:
            if installed:
                continue
            link: CHAT_COMPANION_OT_website = layout.operator(
                operator=CHAT_COMPANION_OT_website.bl_idname,
                text=text,
                icon="URL",
            )
            link.url = url

    # endregion
