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
from ..properties.properties import ChatCompanionProperties
from ..properties.item_history import HistoryPropertyGroup


class CHAT_COMPANION_OT_rate_answer(Operator):
    """Thumbs up/down the selected answer; rewrites its usage-log episode.

    Toggle semantics: clicking the already-active rating clears it (back to
    unrated). The rating is a subjective quality signal stored as an extra
    dimension in the on-disk JSONL episode for offline mining.
    """

    bl_idname = "chat_companion.rate_answer"
    bl_label = "Rate Answer"
    bl_description = "Mark this answer helpful or not; saved to the usage log"
    bl_options = {"REGISTER", "INTERNAL"}

    rating: bpy.props.StringProperty(default="up")

    @classmethod
    def poll(cls, context: Context):
        return len(context.scene.chat_companion_history) > 0

    def execute(self, context: Context):
        from ..agent_core import usage_log

        props: ChatCompanionProperties = context.scene.chat_companion_properties
        history = context.scene.chat_companion_history
        item: HistoryPropertyGroup = history.get(str(props.selected_history_item))

        if item is None or not item.episode_id or not item.episode_log_path:
            self.report({"WARNING"}, "No usage-log episode to rate for this answer.")
            return {"CANCELLED"}

        new_rating = "" if item.feedback_rating == self.rating else self.rating
        try:
            ok = usage_log.rewrite_feedback(
                item.episode_log_path, item.episode_id, new_rating
            )
        except Exception as exc:
            self.report({"WARNING"}, f"Could not save feedback: {exc}")
            return {"CANCELLED"}

        if not ok:
            self.report({"WARNING"}, "Could not find the log entry to update.")
            return {"CANCELLED"}

        item.feedback_rating = new_rating
        try:
            context.area.tag_redraw()
        except Exception:
            pass
        return {"FINISHED"}
