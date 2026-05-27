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
from bpy.types import Menu, UILayout
from ..utils import cc_globals
from ..operators.operator_full_version import chat_companion_features


class CHAT_COMPANION_MT_add_attachment(Menu):
    bl_idname = "CHAT_COMPANION_MT_add_attachment"
    bl_label = "Add"
    bl_description = "Add an attachment"

    def draw(self, context):
        props = context.scene.chat_companion_properties
        layout: UILayout = self.layout

        layout.separator()

        # full variant
        if cc_globals.cc_full:
            # ! attach internal text
            column: UILayout = layout.column(align=True)
            column.label(text="Attach Internal Text", icon="TEXT")
            column.prop_search(
                data=props,
                property="selected_text_block",
                search_data=bpy.data,
                search_property="texts",
                text="",
                icon="DOWNARROW_HLT",
            )

            layout.separator()

            # ! import external text
            from ..full.operator_attachments import CHAT_COMPANION_OT_add_external_text

            layout.operator(
                CHAT_COMPANION_OT_add_external_text.bl_idname,
                icon="FILEBROWSER",
                text="Attach File...",
            )
        # free variant
        else:
            layout.label(text="Full version:")
            full_texts: list = chat_companion_features.get("attachments").split("\n")
            for full_text in full_texts:
                layout.label(text=full_text)

        # TODO add buttons for quick actions
        # Blender Changelog since GPT lost knowledge
        # info about this blender file (version, object names and hierarchy) -> sensitive information!
