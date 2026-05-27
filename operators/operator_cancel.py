import bpy

from ..utils import cc_globals


class CHAT_COMPANION_OT_cancel_request(bpy.types.Operator):
    bl_idname = "chat_companion.cancel_request"
    bl_label = "Cancel POPAgent Request"
    bl_description = "Cancel the currently running POPAgent request"
    bl_options = {"REGISTER", "INTERNAL"}

    def execute(self, context):
        task = cc_globals.active_async_tasks.get("chat_companion.ask")
        if task is None or task.done():
            return {"CANCELLED"}

        task.cancel()
        props = context.scene.chat_companion_properties
        props.waiting_string = "Cancelling"
        props.waiting_icon = "CANCEL"
        return {"FINISHED"}
