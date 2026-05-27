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


from bpy.types import Context, UILayout, Menu
from ..utils import cc_globals
from ..operators.operator_full_version import CHAT_COMPANION_OT_context_menu_full


class TEXT_PT_MT_chat_companion_custom_context(Menu):
    # class to add a context menu entry
    bl_label = ""

    def draw(self, context: Context):
        pass


def chat_companion_text_context(self, context: Context):

    layout: UILayout = self.layout
    layout.separator()
    pcoll = cc_globals.preview_collections["main"]

    if cc_globals.cc_full:
        from ..full.operator_autocomplete import CHAT_COMPANION_OT_autocomplete

        layout.operator(
            CHAT_COMPANION_OT_autocomplete.bl_idname,
            icon_value=pcoll["chat_companion_icon"].icon_id,
        )
    else:
        complete_full_op = layout.operator(
            CHAT_COMPANION_OT_context_menu_full.bl_idname,
            icon_value=pcoll["chat_companion_icon"].icon_id,
            text="Turn Comments into Code",
        )
        complete_full_op.feature = "autocomplete"
