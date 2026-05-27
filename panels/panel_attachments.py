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


from bpy.types import Panel, UILayout, Context
from ..utils import cc_globals
from .panel import POLYGONINGENIEUR_panel
from ..operators.operator_full_version import CHAT_COMPANION_OT_full_version
from ..menus.menu_add_attachment import CHAT_COMPANION_MT_add_attachment


class CHAT_COMPANION_PT_attachments(POLYGONINGENIEUR_panel, Panel):
    bl_idname = "CHAT_COMPANION_PT_attachments"
    bl_label = ""
    bl_parent_id = "CHAT_COMPANION_PT_prompt"
    bl_order = 1
    bl_options = {"DEFAULT_CLOSED", "HEADER_LAYOUT_EXPAND"}

    def draw_header(self, context: Context):
        attachments = context.scene.chat_companion_attachments

        layout: UILayout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        split: UILayout = layout.split(align=True, factor=4 / 5)
        split.scale_y = 1.1

        left: UILayout = split.row()
        left.alignment = "LEFT"
        left.label(text="Attachments", icon="APPEND_BLEND")
        # ! add attachment menu button
        left.menu(CHAT_COMPANION_MT_add_attachment.bl_idname, icon="ADD", text=" ")

        right: UILayout = split.row()
        right.alignment = "RIGHT"

        # enabled attachments / all attachments display
        enabled_attachments: int = len([1 for x in attachments if x.is_enabled])
        attachments_used_str: str = (
            str(enabled_attachments) + "/" + str(len(attachments))
        )
        right.label(text=attachments_used_str)
        right.separator(factor=1)

    def draw(self, context: Context):
        chat_properties = context.scene.chat_companion_properties
        attachments = context.scene.chat_companion_attachments

        layout: UILayout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        split: UILayout = layout.grid_flow(columns=2, align=True)
        left: UILayout = split.column(align=True)
        right: UILayout = split.row(align=False)
        right.alignment = "RIGHT"

        rows: int = 1
        if len(attachments) > 1:
            rows = 2

        left.template_list(
            listtype_name="CHAT_COMPANION_UL_item_attachment",
            list_id="",
            dataptr=context.scene,
            propname="chat_companion_attachments",
            active_dataptr=chat_properties,
            active_propname="selected_attachment_item",
            type="DEFAULT",
            sort_reverse=False,
            sort_lock=False,
            rows=rows,
            maxrows=4,
        )

        col: UILayout = right.column(align=True)

        # ! move up and down buttons
        if len(attachments) > 1:
            col.separator()
            col.operator(
                "CHAT_COMPANION_OT_move_attachment", icon="TRIA_UP", text=""
            ).move_up = True
            col.operator(
                "CHAT_COMPANION_OT_move_attachment", icon="TRIA_DOWN", text=""
            ).move_up = False

        # workaround so list doesn't appear bugged when there are no attachments
        col.label(text="", icon="BLANK1")

        footer: UILayout = left.column_flow(columns=2, align=True)
        footer.enabled = cc_globals.cc_full

        # ! favorite
        favorite_container: UILayout = footer.row(align=True)
        favorite_container.alignment = "LEFT"
        if len(attachments) > 0:
            attachment_item = attachments.get(
                str(chat_properties.selected_attachment_item)
            )
            is_favorite: bool = attachment_item.is_favorite
            favorite_icon: str = "SOLO_ON" if is_favorite else "SOLO_OFF"
        else:
            is_favorite = False
            favorite_icon = "SOLO_OFF"
        if cc_globals.cc_full:
            from ..full.operator_attachments import (
                CHAT_COMPANION_OT_favorite_attachment,
            )

            favorite_container.operator(
                operator=CHAT_COMPANION_OT_favorite_attachment.bl_idname,
                text="",
                icon=favorite_icon,
                depress=is_favorite,
            )
        else:
            fav_full_op = favorite_container.operator(
                operator=CHAT_COMPANION_OT_full_version.bl_idname,
                text="",
                icon=favorite_icon,
                depress=is_favorite,
            )
            fav_full_op.feature = "attachments"

        # ! delete
        delete_container: UILayout = footer.row(align=True)
        delete_container.alignment = "RIGHT"
        if cc_globals.cc_full:
            from ..full.operator_attachments import CHAT_COMPANION_OT_remove_attachment

            delete_container.operator(
                operator=CHAT_COMPANION_OT_remove_attachment.bl_idname,
                text="",
                icon="TRASH",
            )
        else:
            del_full_op = delete_container.operator(
                operator=CHAT_COMPANION_OT_full_version.bl_idname, text="", icon="TRASH"
            )
            del_full_op.feature = "attachments"

        # ! clear all except favorites
        delete_container.separator()
        if cc_globals.cc_full:
            from ..full.operator_attachments import CHAT_COMPANION_OT_clear_attachments

            delete_container.operator(
                operator=CHAT_COMPANION_OT_clear_attachments.bl_idname,
                text="All",
                icon="TRASH",
            )
        else:
            del_all_full_op = delete_container.operator(
                operator=CHAT_COMPANION_OT_full_version.bl_idname,
                text="All",
                icon="TRASH",
            )
            del_all_full_op.feature = "attachments"
