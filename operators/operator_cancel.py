import bpy

from ..utils import cc_globals


class CHAT_COMPANION_OT_cancel_request(bpy.types.Operator):
    bl_idname = "chat_companion.cancel_request"
    bl_label = "Cancel POPAgent Request"
    bl_description = "Cancel the currently running POPAgent request"
    bl_options = {"REGISTER", "INTERNAL"}

    def execute(self, context):
        props = context.scene.chat_companion_properties
        task = cc_globals.active_async_tasks.get("chat_companion.ask")
        if task is None or task.done():
            props.waiting_for_answer = False
            props.is_connecting = False
            props.is_streaming = False
            props.waiting_string = "Cancelled"
            props.waiting_icon = "CANCEL"
            return {"FINISHED"}

        task.cancel()
        props.waiting_string = "Cancelling"
        props.waiting_icon = "CANCEL"
        return {"FINISHED"}
