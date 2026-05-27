"""Image attachments sent with the next POPAgent prompt."""

import bpy


class ImageAttachmentPropertyGroup(bpy.types.PropertyGroup):
    display_name: bpy.props.StringProperty()
    source: bpy.props.StringProperty()
    media_type: bpy.props.StringProperty()
    image_base64: bpy.props.StringProperty()
    is_enabled: bpy.props.BoolProperty(
        name="Enabled",
        description="Send this image with the next prompt",
        default=True,
    )


class CHAT_COMPANION_UL_item_image_attachment(bpy.types.UIList):

    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname
    ):
        if self.layout_type in {"DEFAULT", "COMPACT"}:
            layout.prop(item, "display_name", text="", emboss=False, icon="IMAGE_DATA")
            icon_name = "CHECKBOX_HLT" if item.is_enabled else "CHECKBOX_DEHLT"
            layout.prop(item, "is_enabled", text="", icon=icon_name, emboss=False)
