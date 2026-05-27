
import bpy
import os

from .utils import cc_globals
from .utils.async_loop import AsyncLoopModalOperator, setup_asyncio_executor
from .utils.dependencies import Dependencies
from .agent_core.main_thread import shutdown_main_thread
from .agent_core import skill_registry as _skill_registry
from .agent_core.confirm_dialog import POPAGENT_OT_confirm_skill, clear_session_trust
from .agent_core.reverse_pull import pull_already_loaded_agent_skills
from . import builtin_skills as _builtin_skills

# classes that need to be registered
from .properties.addon_preferences import ChatCompanionPreferences
from .properties.properties import ChatCompanionProperties
from .panels.panel_prompt import CHAT_COMPANION_PT_prompt
from .panels.panel_attachments import CHAT_COMPANION_PT_attachments
from .panels.panel_output import CHAT_COMPANION_PT_output
from .panels.panel_history import CHAT_COMPANION_PT_history
from .panels.panel_links import CHAT_COMPANION_PT_links
from .panels.panel_tokens import CHAT_COMPANION_PT_tokens
from .properties.item_history import CHAT_COMPANION_UL_item_history
from .properties.item_history import HistoryPropertyGroup
from .properties.item_usage import UsagePropertyGroup
from .menus.menu_add_attachment import CHAT_COMPANION_MT_add_attachment
from .properties.item_attachment import CHAT_COMPANION_UL_item_attachment
from .properties.item_attachment import AttachmentPropertyGroup
from .operators.operator_ask import CHAT_COMPANION_OT_ask
from .operators.operator_enter import CHAT_COMPANION_OT_process_prompt_input
from .operators.operator_copy import CHAT_COMPANION_OT_copy
from .operators.operator_copy_error import CHAT_COMPANION_OT_copy_error
from .operators.operator_answer_view import CHAT_COMPANION_OT_open_answer_text
from .operators.operator_answer_view import CHAT_COMPANION_OT_toggle_answer_code
from .operators.operator_open_prefs import CHAT_COMPANION_OT_open_prefs
from .operators.operator_website import CHAT_COMPANION_OT_website
from .operators.operator_full_version import CHAT_COMPANION_OT_full_version
from .operators.operator_full_version import CHAT_COMPANION_OT_context_menu_full
from .operators.operator_history import CHAT_COMPANION_OT_add_history_item
from .operators.operator_history import CHAT_COMPANION_OT_favorite_history_item
from .operators.operator_history import CHAT_COMPANION_OT_delete_history_item
from .operators.operator_history import CHAT_COMPANION_OT_clear_history
from .operators.operator_history import CHAT_COMPANION_OT_move_history
from .operators.operator_usage import CHAT_COMPANION_OT_clear_usage
from .operators.operator_usage import CHAT_COMPANION_OT_export_usage_csv
from .operators.operator_install_deps import CHAT_COMPANION_OT_install_deps
from .operators.operator_change_llm import CHAT_COMPANION_OT_select_open_ai
from .operators.operator_select_anthropic import CHAT_COMPANION_OT_select_anthropic
from .operators.operator_skills import (
    POPAGENT_OT_toggle_skill,
    POPAGENT_OT_clear_session_trust,
)
from .menus.context_interface_help import WM_MT_button_context
from .menus.context_interface_help import chat_companion_button_menu
from .menus.context_autocomplete import TEXT_PT_MT_chat_companion_custom_context
from .menus.context_autocomplete import chat_companion_text_context

# ! variant enable/disable
if cc_globals.cc_full:
    # classes of full variant the need to be registered
    from .full.operator_copy_code_clipboard import CHAT_COMPANION_OT_copy_code_clipboard
    from .full.operator_copy_code_cursor import CHAT_COMPANION_OT_copy_code_cursor
    from .full.operator_copy_code_text import CHAT_COMPANION_OT_copy_code_text
    from .full.operator_run_code import CHAT_COMPANION_OT_run_code
    from .full.operator_interface_help import CHAT_COMPANION_OT_interface_help
    from .full.operator_autocomplete import CHAT_COMPANION_OT_autocomplete
    from .full.operator_attachments import CHAT_COMPANION_OT_add_internal_text
    from .full.operator_attachments import CHAT_COMPANION_OT_add_external_text
    from .full.operator_attachments import CHAT_COMPANION_OT_remove_attachment
    from .full.operator_attachments import CHAT_COMPANION_OT_move_attachment
    from .full.operator_attachments import CHAT_COMPANION_OT_favorite_attachment
    from .full.operator_attachments import CHAT_COMPANION_OT_clear_attachments
    from .full.operator_change_llm import CHAT_COMPANION_OT_select_deepseek_ai

bl_info = {
    # ! variant name
    "name": "POPAgent",
    "author": "JhonYan",
    "description": "A Blender Agent based on OpenAI and DeepSeek.",
    "blender": (5, 1, 0),
    "version": (1, 0, 0),
    "location": "View3D",
    "warning": "",
    "doc_url": "",
    "support": "COMMUNITY",
    "category": "AI",
}

classes = (
    AsyncLoopModalOperator,
    ChatCompanionPreferences,
    ChatCompanionProperties,
    CHAT_COMPANION_PT_prompt,
    CHAT_COMPANION_PT_attachments,
    CHAT_COMPANION_PT_output,
    CHAT_COMPANION_PT_history,
    CHAT_COMPANION_UL_item_history,
    HistoryPropertyGroup,
    UsagePropertyGroup,
    CHAT_COMPANION_MT_add_attachment,
    CHAT_COMPANION_UL_item_attachment,
    AttachmentPropertyGroup,
    CHAT_COMPANION_PT_links,
    CHAT_COMPANION_PT_tokens,
    CHAT_COMPANION_OT_ask,
    CHAT_COMPANION_OT_process_prompt_input,
    CHAT_COMPANION_OT_copy,
    CHAT_COMPANION_OT_copy_error,
    CHAT_COMPANION_OT_open_answer_text,
    CHAT_COMPANION_OT_toggle_answer_code,
    CHAT_COMPANION_OT_open_prefs,
    CHAT_COMPANION_OT_website,
    CHAT_COMPANION_OT_full_version,
    CHAT_COMPANION_OT_context_menu_full,
    CHAT_COMPANION_OT_add_history_item,
    CHAT_COMPANION_OT_favorite_history_item,
    CHAT_COMPANION_OT_delete_history_item,
    CHAT_COMPANION_OT_clear_history,
    CHAT_COMPANION_OT_move_history,
    CHAT_COMPANION_OT_clear_usage,
    CHAT_COMPANION_OT_export_usage_csv,
    CHAT_COMPANION_OT_install_deps,
    CHAT_COMPANION_OT_select_open_ai,
    CHAT_COMPANION_OT_select_anthropic,
    POPAGENT_OT_confirm_skill,
    POPAGENT_OT_toggle_skill,
    POPAGENT_OT_clear_session_trust,
    WM_MT_button_context,
    TEXT_PT_MT_chat_companion_custom_context,
)

# ! variant enable/disable
if cc_globals.cc_full:
    classes += (
        CHAT_COMPANION_OT_copy_code_clipboard,
        CHAT_COMPANION_OT_copy_code_cursor,
        CHAT_COMPANION_OT_copy_code_text,
        CHAT_COMPANION_OT_run_code,
        CHAT_COMPANION_OT_interface_help,
        CHAT_COMPANION_OT_autocomplete,
        CHAT_COMPANION_OT_add_internal_text,
        CHAT_COMPANION_OT_add_external_text,
        CHAT_COMPANION_OT_remove_attachment,
        CHAT_COMPANION_OT_move_attachment,
        CHAT_COMPANION_OT_favorite_attachment,
        CHAT_COMPANION_OT_clear_attachments,
        CHAT_COMPANION_OT_select_deepseek_ai,
    )


def register():
    """Register everything blender needs registering for."""

    # Note that preview collections returned by bpy.utils.previews
    # are regular py objects - you can use them to store custom data.
    import bpy.utils.previews

    pcoll = bpy.utils.previews.new()
    # path to the folder where the icon is
    # the path is calculated relative to this py file inside the addon folder
    chat_comp_icons_dir = os.path.join(os.path.dirname(__file__), "icons")

    # load a preview thumbnail of a file and store in the previews collection
    pcoll.load(
        "chat_companion_icon",
        os.path.join(chat_comp_icons_dir, "chat_companion_icon.png"),
        "IMAGE",
    )
    pcoll.load(
        "the_inspector_icon", os.path.join(chat_comp_icons_dir, "inspector.png"), "IMAGE"
    )
    pcoll.load(
        "instagram_icon", os.path.join(chat_comp_icons_dir, "instagram.png"), "IMAGE"
    )
    pcoll.load(
        "linkedin_icon", os.path.join(chat_comp_icons_dir, "linkedin.png"), "IMAGE"
    )
    pcoll.load("x_icon", os.path.join(chat_comp_icons_dir, "x.png"), "IMAGE")
    pcoll.load("money_icon", os.path.join(chat_comp_icons_dir, "money.png"), "IMAGE")
    pcoll.load("openai_icon", os.path.join(chat_comp_icons_dir, "openai.png"), "IMAGE")
    pcoll.load(
        "deepseek_icon", os.path.join(chat_comp_icons_dir, "deepseek.png"), "IMAGE"
    )
    pcoll.load(
        "anthropic_icon", os.path.join(chat_comp_icons_dir, "anthropic.png"), "IMAGE"
    )

    cc_globals.preview_collections["main"] = pcoll

    setup_asyncio_executor()

    for c in classes:
        bpy.utils.register_class(c)

    bpy.types.Scene.chat_companion_properties = bpy.props.PointerProperty(
        type=ChatCompanionProperties
    )
    bpy.types.Scene.chat_companion_history = bpy.props.CollectionProperty(
        type=HistoryPropertyGroup
    )
    bpy.types.Scene.chat_companion_usage = bpy.props.CollectionProperty(
        type=UsagePropertyGroup
    )
    bpy.types.Scene.chat_companion_attachments = bpy.props.CollectionProperty(
        type=AttachmentPropertyGroup
    )

    bpy.types.WM_MT_button_context.append(chat_companion_button_menu)
    bpy.types.TEXT_MT_context_menu.prepend(chat_companion_text_context)

    # install dependencies that are not standard python modules
    # (https://docs.python.org/3.10/py-modindex.html)
    # and are also not shipped with the blender python bundle
    # (path\to\blender\version\python\lib\site-packages)
    Dependencies.install_dependencies()

    _builtin_skills.register()
    clear_session_trust()

    # Reverse-pull: pick up sibling addons whose agent_skills.register() ran
    # earlier when POPAgent wasn't importable yet.
    pulled = pull_already_loaded_agent_skills()
    if pulled:
        print(f"POPAgent reverse-pulled agent_skills from: {pulled}")

    print("POPAgent Registered.")


def unregister():
    """Unregister and delete everything that was registered and created."""

    shutdown_main_thread()
    _skill_registry.clear_all()
    _builtin_skills.unregister()
    clear_session_trust()

    del bpy.types.Scene.chat_companion_properties
    del bpy.types.Scene.chat_companion_history
    del bpy.types.Scene.chat_companion_usage
    del bpy.types.Scene.chat_companion_attachments

    for pcoll in cc_globals.preview_collections.values():
        bpy.utils.previews.remove(pcoll)
    cc_globals.preview_collections.clear()

    bpy.types.WM_MT_button_context.remove(chat_companion_button_menu)
    bpy.types.TEXT_MT_context_menu.remove(chat_companion_text_context)

    from bpy.utils import unregister_class

    for c in reversed(classes):
        if c.is_registered:
            unregister_class(c)

    print("POPAgent Unregistered.")
