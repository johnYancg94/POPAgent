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
import json
from bpy.types import Operator
from ..utils.utils import string_to_tokens_float


class CHAT_COMPANION_OT_add_external_text(Operator):
    bl_idname = "chat_companion.add_external_text"
    bl_label = "Attach"
    bl_description = "Add a text file from disk as attachment"
    bl_options = {"REGISTER", "INTERNAL"}

    # choosen path will be stored here
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    @classmethod
    def poll(self, context):
        return True

    def invoke(self, context, event):
        # call the file browser with the operator self (so this operator)
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        chat_properties = context.scene.chat_companion_properties
        attachments = context.scene.chat_companion_attachments

        # load the external text file
        try:
            text = bpy.data.texts.load(filepath=self.filepath, internal=True)
        except Exception as e:
            print("Filetype not supported!", e)
            self.report({"WARNING"}, "Filetype not supported!")
            return {"CANCELLED"}

        try:
            text_as_json = json.dumps(text.as_string())
        except Exception as e:
            bpy.data.texts.remove(text)
            print("Filetype not supported!", e)
            self.report({"WARNING"}, "Filetype not supported!")
            return {"CANCELLED"}

        # ! add to attachments
        attachment = attachments.add()
        # this name is the unique identifies
        attachment.name = str(len(attachments) - 1)

        attachment.text = text_as_json

        attachment.display_name = text.name
        attachment.is_favorite = False
        attachment.is_enabled = True
        attachment.tokens = round(string_to_tokens_float(text.as_string()))

        # ! update attachment token count
        chat_properties.selected_attachment_tokens += attachment.tokens

        # ! move to beginning of list since the attachment list is reversed
        attachments.move(len(attachments) - 1, 0)

        # ! make new attachment selected
        chat_properties.selected_attachment_item = 0

        # reorder names (ids)
        for index, attachment in enumerate(attachments):
            attachment.name = str(index)

        self.report({"INFO"}, "Attachment added")
        return {"FINISHED"}


class CHAT_COMPANION_OT_add_internal_text(Operator):
    bl_idname = "chat_companion.add_internal_text"
    bl_label = "Attach Internal Text..."
    bl_description = "Add a Blender text block as attachment"
    bl_options = {"REGISTER", "INTERNAL"}

    # properties
    file_name: bpy.props.StringProperty()

    @classmethod
    def poll(self, context):
        return True

    def execute(self, context):
        chat_properties = context.scene.chat_companion_properties
        attachments = context.scene.chat_companion_attachments

        # ! add to attachments
        attachment = attachments.add()
        # this name is the unique identifies
        attachment.name = str(len(attachments) - 1)

        text_file = bpy.data.texts[self.file_name]
        text_as_json = json.dumps(text_file.as_string())
        attachment.text = text_as_json

        attachment.display_name = text_file.name
        attachment.is_favorite = False
        attachment.is_enabled = True
        attachment.tokens = round(string_to_tokens_float(text_file.as_string()))

        # ! update attachment token count
        chat_properties.selected_attachment_tokens += attachment.tokens

        # ! move to beginning of list since the attachment list is reversed
        attachments.move(len(attachments) - 1, 0)

        # ! make new attachment selected
        chat_properties.selected_attachment_item = 0

        # reorder names (ids)
        for index, attachment in enumerate(attachments):
            attachment.name = str(index)

        self.report({"INFO"}, "Attachment added")
        return {"FINISHED"}


class CHAT_COMPANION_OT_remove_attachment(Operator):
    bl_idname = "chat_companion.remove_attachment"
    bl_label = "Remove"
    bl_description = "Remove an attachment (not possible if starred/favorited)"
    bl_options = {"REGISTER", "INTERNAL"}

    @classmethod
    def poll(self, context):
        chat_properties = context.scene.chat_companion_properties
        attachments = context.scene.chat_companion_attachments
        has_attachments = len(attachments) > 0
        attachment_item = attachments.get(str(chat_properties.selected_attachment_item))
        return has_attachments and not attachment_item.is_favorite

    def execute(self, context):

        chat_properties = context.scene.chat_companion_properties
        attachments = context.scene.chat_companion_attachments

        items_to_keep = []
        previous_item_index = chat_properties.selected_attachment_item

        # ! lower tokens count
        attachment_item = attachments.get(str(previous_item_index))
        if attachment_item.is_enabled:
            chat_properties.selected_attachment_tokens -= attachment_item.tokens

        for key, item in attachments.items():
            # keep all but the selected one
            if int(item.name) is not chat_properties.selected_attachment_item:
                items_to_keep.append(
                    {
                        "display_name": item.display_name,
                        "text": item.text,
                        "is_favorite": item.is_favorite,
                        "is_enabled": item.is_enabled,
                        "tokens": item.tokens,
                    }
                )

        # ! delete the whole history
        attachments.clear()

        # ! add favorites back in
        for item_to_keep in items_to_keep:
            attachment = attachments.add()
            # this name is the unique identifies
            attachment.name = str(len(attachments) - 1)
            attachment.display_name = item_to_keep["display_name"]
            attachment.text = item_to_keep["text"]
            attachment.is_favorite = item_to_keep["is_favorite"]
            attachment.is_enabled = item_to_keep["is_enabled"]
            attachment.tokens = item_to_keep["tokens"]

        # ! select item below
        chat_properties.selected_attachment_item = max(0, previous_item_index - 1)

        if len(attachments) == 0:
            chat_properties.selected_attachment_item = max(0, len(attachments) - 1)
            chat_properties.selected_attachment_tokens = 0

        # ! reorder names (ids)
        for index, attachment in enumerate(attachments):
            attachment.name = str(index)

        self.report({"INFO"}, "Attachment deleted")
        return {"FINISHED"}


class CHAT_COMPANION_OT_move_attachment(Operator):
    bl_idname = "chat_companion.move_attachment"
    bl_label = "Move Attachment"
    bl_description = ""
    bl_options = {"REGISTER", "INTERNAL"}

    # properties
    move_up: bpy.props.BoolProperty(options={"HIDDEN"})

    @classmethod
    def description(cls, context, properties):
        return (
            "Move the selected attachment up. The attachments will be sent along with the prompt in the displayed order"
            if properties.move_up
            else "Move the selected attachment down. The attachments will be sent along with the prompt in the displayed order"
        )

    @classmethod
    def poll(self, context):
        attachments = context.scene.chat_companion_attachments
        has_attachments = len(attachments) > 1
        return has_attachments

    def execute(self, context):
        chat_properties = context.scene.chat_companion_properties
        attachments = context.scene.chat_companion_attachments

        current_index = chat_properties.selected_attachment_item
        move_to = 0
        if self.move_up and current_index > 0:
            move_to = -1
        elif not self.move_up and current_index < len(attachments) - 1:
            move_to = 1

        # move attachment
        attachments.move(current_index, current_index + move_to)

        # reorder names (ids)
        for index, attachment in enumerate(attachments):
            attachment.name = str(index)

        # update selected
        chat_properties.selected_attachment_item = current_index + move_to

        return {"FINISHED"}


class CHAT_COMPANION_OT_favorite_attachment(Operator):
    bl_idname = "chat_companion.favorite_attachment"
    bl_label = "Favorite Attachment"
    bl_description = "Favorite/Unfavorite an attachment (Favorites won't be deleted when clearing the attachments)"
    bl_options = {"REGISTER", "INTERNAL"}

    @classmethod
    def poll(self, context):
        attachments = context.scene.chat_companion_attachments
        has_attachments = len(attachments) > 0
        return has_attachments

    def execute(self, context):
        chat_properties = context.scene.chat_companion_properties
        attachments = context.scene.chat_companion_attachments
        attachment_item = attachments.get(str(chat_properties.selected_attachment_item))
        attachment_item.is_favorite = not attachment_item.is_favorite

        return {"FINISHED"}


class CHAT_COMPANION_OT_clear_attachments(Operator):
    bl_idname = "chat_companion.clear_attachments"
    bl_label = "Clear Attachments"
    bl_description = "Clear out all attachments except the favorites"
    bl_options = {"REGISTER", "INTERNAL"}

    @classmethod
    def poll(self, context):
        attachments = context.scene.chat_companion_attachments
        return len(attachments) > 0

    def execute(self, context):
        chat_properties = context.scene.chat_companion_properties
        attachments = context.scene.chat_companion_attachments

        favorites = []

        for key, attachment in attachments.items():
            # keep favorites
            if attachment.is_favorite:
                favorites.append(
                    {
                        "display_name": attachment.display_name,
                        "text": attachment.text,
                        "icon": attachment.icon,
                        "is_favorite": attachment.is_favorite,
                        "is_enabled": attachment.is_enabled,
                        "tokens": attachment.tokens,
                    }
                )

        # delete the whole history
        attachments.clear()

        # reset token count
        chat_properties.selected_attachment_tokens = 0

        # add favorites back in
        for index, fav in enumerate(favorites):
            # ! add to attachments
            attachment = attachments.add()
            # this name is the unique identifies
            attachment.name = str(index)

            attachment.display_name = fav["display_name"]
            attachment.text = fav["text"]
            attachment.icon = fav["icon"]
            attachment.is_favorite = fav["is_favorite"]
            attachment.is_enabled = fav["is_enabled"]
            attachment.tokens = fav["tokens"]

            # ! add token count
            if fav["is_enabled"]:
                chat_properties.selected_attachment_tokens += attachment.tokens

        chat_properties.selected_attachment_item = 0

        self.report({"INFO"}, "History cleared")
        return {"FINISHED"}
