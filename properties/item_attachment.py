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


import bpy
from .property_updates import PropertyUpdates


class AttachmentPropertyGroup(bpy.types.PropertyGroup):
    # also add them in opertator_attachments
    display_name: bpy.props.StringProperty()
    text: bpy.props.StringProperty()
    icon: bpy.props.StringProperty()
    is_favorite: bpy.props.BoolProperty()
    is_enabled: bpy.props.BoolProperty(
        name="Enabled?",
        description="If this attachment should be sent along the prompt, or not",
        default=True,
        update=PropertyUpdates.update_attachment_item_is_enabled,
    )
    tokens: bpy.props.IntProperty(default=0)


class CHAT_COMPANION_UL_item_attachment(bpy.types.UIList):

    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname
    ):

        chat_properties = context.scene.chat_companion_properties
        property_group = item

        # draw_item must handle the three layout types...
        # Usually 'DEFAULT' and 'COMPACT' can share the same code
        if self.layout_type in {"DEFAULT", "COMPACT"}:

            layout.prop(
                property_group, "display_name", text="", emboss=False, icon="TEXT"
            )

            # debug
            # layout.label(text=str(property_group.tokens))

            if property_group.is_favorite:
                layout.label(icon="SOLO_ON")

            icon = "CHECKBOX_HLT" if property_group.is_enabled else "CHECKBOX_DEHLT"
            layout.prop(property_group, "is_enabled", text="", icon=icon, emboss=False)
