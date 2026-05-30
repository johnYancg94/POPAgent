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

from bpy.types import Panel
from .panel import POLYGONINGENIEUR_panel
from ..operators.operator_history import CHAT_COMPANION_OT_favorite_history_item
from ..operators.operator_history import CHAT_COMPANION_OT_delete_history_item
from ..operators.operator_history import CHAT_COMPANION_OT_clear_history
from .. import __package__ as base_package
from ..translations import POPAGENT_CTX


class CHAT_COMPANION_PT_history(POLYGONINGENIEUR_panel, Panel):
    bl_idname = "CHAT_COMPANION_PT_history"
    bl_label = ""
    bl_parent_id = "CHAT_COMPANION_PT_prompt"
    bl_order = 0
    bl_options = {"DEFAULT_CLOSED", "HEADER_LAYOUT_EXPAND"}

    def draw_header(self, context):
        history = context.scene.chat_companion_history

        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        split = layout.split()
        split.scale_y = 1.1
        left = split.row()
        left.alignment = "LEFT"
        left.label(text="History", text_ctxt=POPAGENT_CTX, icon="RECOVER_LAST")
        right = split.row()
        right.alignment = "RIGHT"

        # enabled attachments / all attachments display
        enabled_history = len([1 for x in history if x.is_enabled])
        history_used_str = str(enabled_history) + "/" + str(len(history))
        right.label(text=history_used_str)
        right.separator(factor=1)

    def draw(self, context):
        chat_properties = context.scene.chat_companion_properties
        prefs = context.preferences.addons[base_package].preferences
        history = context.scene.chat_companion_history

        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        split = layout.grid_flow(columns=2, align=True)
        left = split.column(align=True)
        right = split.row(align=False)
        right.alignment = "RIGHT"

        rows = 1
        if len(history) > 1:
            rows = 2

        left.template_list(
            listtype_name="CHAT_COMPANION_UL_item_history",
            list_id="",
            dataptr=context.scene,
            propname="chat_companion_history",
            active_dataptr=chat_properties,
            active_propname="selected_history_item",
            type="DEFAULT",
            sort_reverse=False,
            sort_lock=False,
            rows=rows,
            maxrows=4,
        )

        # ! move up and down buttons
        col = right.column(align=True)
        col.operator(
            "CHAT_COMPANION_OT_move_history", icon="TRIA_UP", text=""
        ).move_up = True
        col.operator(
            "CHAT_COMPANION_OT_move_history", icon="TRIA_DOWN", text=""
        ).move_up = False

        footer = left.column_flow(columns=2, align=True)

        # ! favorite
        favorite_container = footer.row(align=True)
        favorite_container.alignment = "LEFT"
        if len(history) > 0:
            history_item = history.get(str(chat_properties.selected_history_item))
            is_favorite = history_item.is_favorite
            favorite_icon = "SOLO_ON" if is_favorite else "SOLO_OFF"
        else:
            is_favorite = False
            favorite_icon = "SOLO_OFF"
        favorite_button = favorite_container.operator(
            operator=CHAT_COMPANION_OT_favorite_history_item.bl_idname,
            text="",
            icon=favorite_icon,
            depress=is_favorite,
        )

        # ! delete
        delete_container = footer.row(align=True)
        delete_container.alignment = "RIGHT"
        delete_button = delete_container.operator(
            operator=CHAT_COMPANION_OT_delete_history_item.bl_idname,
            text="",
            icon="TRASH",
        )

        # ! clear all except favorites
        delete_container.separator()
        clear_button = delete_container.operator(
            operator=CHAT_COMPANION_OT_clear_history.bl_idname, text="All", icon="TRASH"
        )

        context_row = left.row(align=True)
        context_row.prop(prefs, "max_history_context", text="Max Context")

        # todo add slider to adjust maximum history items
        # todo or even better estimate token and display along with max token of language model
        # https://help.openai.com/en/articles/4936856-what-are-tokens-and-how-to-count-them
        # 1 token ~= 4 chars in English

        # info text
        # wrapped_text = wrap_string_to_panel(
        #     context, "Enable those conversations you want to pass onto the next prompt as context.")
        # for line in wrapped_text:
        #     line_col = layout.column()
        #     line_col.label(text=line)
        #     line_col.scale_y = 0.6
