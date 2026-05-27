import csv
import os

import bpy
from bpy.props import StringProperty
from bpy.types import Operator


class CHAT_COMPANION_OT_clear_usage(Operator):
    bl_idname = "chat_companion.clear_usage"
    bl_label = "Clear Usage"
    bl_description = "Clear usage records saved in the current Blender scene"
    bl_options = {"REGISTER", "INTERNAL"}

    @classmethod
    def poll(cls, context):
        return len(context.scene.chat_companion_usage) > 0

    def execute(self, context):
        context.scene.chat_companion_usage.clear()
        self.report({"INFO"}, "Scene usage records cleared.")
        return {"FINISHED"}


class CHAT_COMPANION_OT_export_usage_csv(Operator):
    bl_idname = "chat_companion.export_usage_csv"
    bl_label = "Export Usage CSV"
    bl_description = "Export current scene usage records to a CSV file"
    bl_options = {"REGISTER", "INTERNAL"}

    filepath: StringProperty(
        name="File Path",
        subtype="FILE_PATH",
        default="popagent_usage.csv",
    )

    @classmethod
    def poll(cls, context):
        return len(context.scene.chat_companion_usage) > 0

    def invoke(self, context, event):
        if not self.filepath or self.filepath == "popagent_usage.csv":
            blend_path = bpy.data.filepath
            base_dir = os.path.dirname(blend_path) if blend_path else os.path.expanduser("~")
            self.filepath = os.path.join(base_dir, "popagent_usage.csv")
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        records = context.scene.chat_companion_usage
        fieldnames = [
            "created_at",
            "llm_organization",
            "model",
            "mode",
            "input_tokens",
            "output_tokens",
            "cache_creation_tokens",
            "cache_read_tokens",
            "reasoning_tokens",
            "total_tokens",
            "estimated_cost_rmb",
            "latency_ms",
            "status_code",
            "is_error",
            "prompt_preview",
            "error_message",
        ]
        with open(self.filepath, "w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            for item in records:
                writer.writerow({name: getattr(item, name) for name in fieldnames})
        self.report({"INFO"}, f"Usage exported to {self.filepath}")
        return {"FINISHED"}
