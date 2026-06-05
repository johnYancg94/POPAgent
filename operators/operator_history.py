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
from bpy.types import Operator, Context
from bpy.props import BoolProperty
from ..properties.property_updates import PropertyUpdates
from ..utils import cc_globals
from ..properties.properties import ChatCompanionProperties
from ..properties.addon_preferences import ChatCompanionPreferences
from ..properties.item_history import HistoryPropertyGroup
from .. import __package__ as base_package


class CHAT_COMPANION_OT_add_history_item(Operator):
    bl_idname = "chat_companion.add_history_item"
    bl_label = "Add History"
    bl_description = "Add prompt and answer to history"
    bl_options = {"REGISTER", "INTERNAL"}

    # properties
    name: bpy.props.IntProperty(default=0)
    display_name: bpy.props.StringProperty()
    prompt: bpy.props.StringProperty()
    answer: bpy.props.StringProperty()
    parts: bpy.props.StringProperty()
    object_results: bpy.props.StringProperty(default="")
    is_favorite: bpy.props.BoolProperty(default=False)
    is_enabled: bpy.props.BoolProperty(default=True)
    llm_organization: bpy.props.StringProperty()
    tool_calls_json: bpy.props.StringProperty(default="")
    episode_id: bpy.props.StringProperty(default="")
    episode_log_path: bpy.props.StringProperty(default="")
    feedback_rating: bpy.props.StringProperty(default="")

    # error properties
    is_error: bpy.props.BoolProperty(default=False)
    error_button_icon: bpy.props.StringProperty()
    error_button_text: bpy.props.StringProperty()
    error_button_content: bpy.props.StringProperty()
    error_button_url: bpy.props.StringProperty()
    error_title: bpy.props.StringProperty()
    error_info: bpy.props.StringProperty()
    error_message: bpy.props.StringProperty()

    def execute(self, context: Context):
        props: ChatCompanionProperties = context.scene.chat_companion_properties
        prefs: ChatCompanionPreferences = context.preferences.addons[
            base_package
        ].preferences
        history: set(HistoryPropertyGroup) = context.scene.chat_companion_history

        # ! add to history
        history_item: HistoryPropertyGroup = history.add()
        # this name is the unique identifies
        history_item.name = str(self.name)

        history_item.display_name = self.display_name
        history_item.user_prompt = self.prompt
        history_item.answer = self.answer
        history_item.answer_parts = self.parts
        history_item.answer_object_results = self.object_results
        history_item.is_favorite = self.is_favorite
        history_item.icon = "VIEWZOOM"
        history_item.llm_organization = prefs.llm_organization
        history_item.tool_calls_json = self.tool_calls_json
        history_item.episode_id = self.episode_id
        history_item.episode_log_path = self.episode_log_path
        history_item.feedback_rating = self.feedback_rating

        history_item.is_error = self.is_error
        history_item.error_button_icon = self.error_button_icon
        history_item.error_button_text = self.error_button_text
        history_item.error_button_content = self.error_button_content
        history_item.error_button_url = self.error_button_url
        history_item.error_title = self.error_title
        history_item.error_info = self.error_info
        history_item.error_message = self.error_message

        # ! move to beginning of list since the attachment list is reversed
        history.move(len(history) - 1, 0)

        # reorder names (ids)
        for index, item in enumerate(history):
            item.name = str(index)

        # ! make new history selected
        props.selected_history_item = 0

        # update history tokens count
        PropertyUpdates.update_selected_history_tokens(self, context)

        return {"FINISHED"}


class CHAT_COMPANION_OT_favorite_history_item(Operator):
    bl_idname = "chat_companion.favorite_history_item"
    bl_label = "Favorite"
    bl_description = "Keep the currently selected prompt and answer"
    bl_options = {"REGISTER", "INTERNAL"}

    @classmethod
    def poll(self, context: Context):
        history: set(HistoryPropertyGroup) = context.scene.chat_companion_history
        return len(history) > 0

    def execute(self, context: Context):

        props: ChatCompanionProperties = context.scene.chat_companion_properties
        history: set(HistoryPropertyGroup) = context.scene.chat_companion_history

        # the index is the key (history_item.name)
        history_item: HistoryPropertyGroup = history.get(
            str(props.selected_history_item)
        )
        history_item.is_favorite = not history_item.is_favorite

        return {"FINISHED"}


class CHAT_COMPANION_OT_delete_history_item(Operator):
    bl_idname = "chat_companion.delete_history_item"
    bl_label = "Delete"
    bl_description = "Delete this prompt and answer (not possible if starred/favorited)"
    bl_options = {"REGISTER", "INTERNAL"}

    @classmethod
    def poll(self, context: Context):
        props: ChatCompanionProperties = context.scene.chat_companion_properties
        history: set(HistoryPropertyGroup) = context.scene.chat_companion_history

        has_history: bool = len(history) > 0
        history_item: HistoryPropertyGroup = history.get(
            str(props.selected_history_item)
        )
        return has_history and not history_item.is_favorite

    def execute(self, context: Context):
        # TODO bug when clearing -> llm_orga resets to OpenAI for all!

        props: ChatCompanionProperties = context.scene.chat_companion_properties
        history: set(HistoryPropertyGroup) = context.scene.chat_companion_history

        items_to_keep: list = []
        previous_item_index: int = props.selected_history_item

        for history_item in history:
            if not isinstance(history_item, HistoryPropertyGroup):
                continue
            # keep all but the selected one
            if int(history_item.name) is not props.selected_history_item:
                items_to_keep.append(
                    {
                        "display_name": history_item.display_name,
                        "user_prompt": history_item.user_prompt,
                        "answer": history_item.answer,
                        "answer_parts": history_item.answer_parts,
                        "answer_object_results": history_item.answer_object_results,
                        "is_favorite": history_item.is_favorite,
                        "llm_organization": history_item.llm_organization,
                        "tool_calls_json": history_item.tool_calls_json,
                        "episode_id": history_item.episode_id,
                        "episode_log_path": history_item.episode_log_path,
                        "feedback_rating": history_item.feedback_rating,
                        "is_error": history_item.is_error,
                        "error_button_icon": history_item.error_button_icon,
                        "error_button_text": history_item.error_button_text,
                        "error_button_content": history_item.error_button_content,
                        "error_button_url": history_item.error_button_url,
                        "error_title": history_item.error_title,
                        "error_info": history_item.error_info,
                        "error_message": history_item.error_message,
                    }
                )

        # delete the whole history
        history.clear()

        # add favorites back in
        for item_to_keep in reversed(items_to_keep):
            if not isinstance(item_to_keep, dict):
                continue
            print(item_to_keep, item_to_keep.get("llm_organization"))
            bpy.ops.chat_companion.add_history_item(
                display_name=item_to_keep["display_name"],
                prompt=item_to_keep["user_prompt"],
                answer=item_to_keep["answer"],
                parts=item_to_keep["answer_parts"],
                object_results=item_to_keep["answer_object_results"],
                is_favorite=item_to_keep["is_favorite"],
                is_error=item_to_keep["is_error"],
                llm_organization=item_to_keep["llm_organization"],
                tool_calls_json=item_to_keep["tool_calls_json"],
                episode_id=item_to_keep["episode_id"],
                episode_log_path=item_to_keep["episode_log_path"],
                feedback_rating=item_to_keep["feedback_rating"],
                error_button_icon=item_to_keep["error_button_icon"],
                error_button_text=item_to_keep["error_button_text"],
                error_button_content=item_to_keep["error_button_content"],
                error_button_url=item_to_keep["error_button_url"],
                error_title=item_to_keep["error_title"],
                error_info=item_to_keep["error_info"],
                error_message=item_to_keep["error_message"],
            )

        # select item below
        props.selected_history_item = max(0, previous_item_index - 1)

        # empty prompt and answer if no history remains
        if len(history) == 0:
            props.selected_history_item = max(0, len(history) - 1)

            cc_globals.request_failed = False
            props.answer = ""
            props.answer_parts = ""
            props.answer_object_results = ""
            props.error_button_icon = ""
            props.error_button_text = ""
            props.error_button_content = ""
            props.error_button_url = ""
            props.error_title = ""
            props.error_info = ""
            props.error_message = ""

        # reorder names (ids)
        for index, history_item in enumerate(history):
            history_item.name = str(index)

        # update history tokens count
        PropertyUpdates.update_selected_history_tokens(self, context)

        self.report({"INFO"}, "This prompt and answer where deleted")
        return {"FINISHED"}


class CHAT_COMPANION_OT_clear_history(Operator):
    bl_idname = "chat_companion.clear_history"
    bl_label = "Clear History"
    bl_description = "Clear all of history except the favorites"
    bl_options = {"REGISTER", "INTERNAL"}

    @classmethod
    def poll(self, context):
        history = context.scene.chat_companion_history
        return len(history) > 0

    def execute(self, context):
        chat_properties: ChatCompanionProperties = context.scene.chat_companion_properties
        history = context.scene.chat_companion_history

        favorites = []

        for key, item in history.items():
            # keep favorites
            if item.is_favorite:
                favorites.append(
                    {
                        "display_name": item.display_name,
                        "user_prompt": item.user_prompt,
                        "answer": item.answer,
                        "answer_parts": item.answer_parts,
                        "answer_object_results": item.answer_object_results,
                        "is_favorite": item.is_favorite,
                        "llm_organization": item.llm_organization,
                        "tool_calls_json": item.tool_calls_json,
                        "episode_id": item.episode_id,
                        "episode_log_path": item.episode_log_path,
                        "feedback_rating": item.feedback_rating,
                        "is_error": item.is_error,
                        "error_button_icon": item.error_button_icon,
                        "error_button_text": item.error_button_text,
                        "error_button_content": item.error_button_content,
                        "error_button_url": item.error_button_url,
                        "error_title": item.error_title,
                        "error_info": item.error_info,
                        "error_message": item.error_message,
                    }
                )

        # delete the whole history
        history.clear()

        # add favorites back in
        for index, fav in enumerate(reversed(favorites)):
            # ! add to history
            bpy.ops.chat_companion.add_history_item(
                name=index,
                display_name=fav["display_name"],
                prompt=fav["user_prompt"],
                answer=fav["answer"],
                parts=fav["answer_parts"],
                object_results=fav["answer_object_results"],
                is_favorite=fav["is_favorite"],
                llm_organization=fav["llm_organization"],
                tool_calls_json=fav["tool_calls_json"],
                episode_id=fav["episode_id"],
                episode_log_path=fav["episode_log_path"],
                feedback_rating=fav["feedback_rating"],
                is_error=fav["is_error"],
                error_button_icon=fav["error_button_icon"],
                error_button_text=fav["error_button_text"],
                error_button_content=fav["error_button_content"],
                error_button_url=fav["error_button_url"],
                error_title=fav["error_title"],
                error_info=fav["error_info"],
                error_message=fav["error_message"],
            )

        chat_properties.selected_history_item = 0

        # empty prompt and answer if no history remains
        if len(history) == 0:
            cc_globals.request_failed = False
            chat_properties.answer = ""
            chat_properties.answer_parts = ""
            chat_properties.answer_object_results = ""
            chat_properties.error_button_icon = ""
            chat_properties.error_button_text = ""
            chat_properties.error_button_content = ""
            chat_properties.error_button_url = ""
            chat_properties.error_title = ""
            chat_properties.error_info = ""
            chat_properties.error_message = ""

        # update history tokens count
        PropertyUpdates.update_selected_history_tokens(self, context)

        self.report({"INFO"}, "History cleared")
        return {"FINISHED"}


class CHAT_COMPANION_OT_move_history(Operator):
    bl_idname = "chat_companion.move_history"
    bl_label = "Move History"
    bl_description = ""
    bl_options = {"REGISTER", "INTERNAL"}

    # properties
    move_up: BoolProperty()

    @classmethod
    def description(cls, context, properties):
        return (
            "Move the selected history up. The order of the history matters when sending it along with your next prompt"
            if properties.move_up
            else "Move the selected history down. The order of the history matters when sending it along with your next prompt"
        )

    @classmethod
    def poll(self, context):
        history = context.scene.chat_companion_history
        return len(history) > 1

    def execute(self, context):
        chat_properties = context.scene.chat_companion_properties
        history = context.scene.chat_companion_history

        current_index = chat_properties.selected_history_item
        move_by = 0
        if self.move_up and current_index > 0:
            move_by = -1
        elif not self.move_up and current_index < len(history) - 1:
            move_by = 1

        # move attachment
        history.move(current_index, current_index + move_by)

        # reorder names (ids)
        for index, history_item in enumerate(history):
            history_item.name = str(index)

        # update selected
        chat_properties.selected_history_item = current_index + move_by

        return {"FINISHED"}
