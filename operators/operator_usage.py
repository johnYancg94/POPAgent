import csv
import os

import bpy
from bpy.props import StringProperty
from bpy.types import Operator


def _resolve_log_dir(prefs) -> str:
    """Mirror operator_ask._default_log_dir: <addon root>/usage_logs."""
    configured = getattr(prefs, "trace_log_dir", "") or ""
    if configured:
        return configured
    addon_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(addon_root, "usage_logs")


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


class CHAT_COMPANION_OT_mine_logs(Operator):
    """Export a week's usage logs as a single shareable zip, then clear them.

    Cut, not copy: it bundles report.txt + the raw episodes into one uniquely
    named zip, then moves the consumed logs into a local _archive/ so the live
    area is emptied. Next export is therefore naturally incremental, filenames
    never collide, and old data is archived (not destroyed) for offline mining.

    Designed for non-technical members: one click -> a Save dialog with the
    filename prefilled -> done. Independent of scene state and developer mode.
    """

    bl_idname = "chat_companion.mine_logs"
    bl_label = "Export Usage Logs"
    bl_description = (
        "Bundle this period's usage logs into one zip to share, then archive "
        "and clear them so the next export only covers new activity"
    )
    bl_options = {"REGISTER", "INTERNAL"}

    filepath: StringProperty(subtype="FILE_PATH")
    filename: StringProperty()
    filter_glob: StringProperty(default="*.zip", options={"HIDDEN"})

    def _label(self, prefs) -> str:
        return getattr(prefs, "trace_log_user_id", "") or "unknown"

    def invoke(self, context, event):
        from ..agent_core import usage_mining

        prefs = context.preferences.addons[__package__.split(".")[0]].preferences
        log_dir = _resolve_log_dir(prefs)
        if not usage_mining.read_episodes(log_dir):
            self.report({"WARNING"}, "No usage logs to export yet.")
            return {"CANCELLED"}

        from datetime import datetime
        day = datetime.now().strftime("%Y-%m-%d")
        label = usage_mining._sanitize_label(self._label(prefs))
        self.filepath = os.path.join(
            os.path.expanduser("~"), f"popagent_{label}_{day}.zip"
        )
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        from ..agent_core import usage_mining, skill_registry

        prefs = context.preferences.addons[__package__.split(".")[0]].preferences
        log_dir = _resolve_log_dir(prefs)
        dest_dir = os.path.dirname(self.filepath) or os.path.expanduser("~")
        known = [s.get("name", "") for s in skill_registry.all_skills()]

        res = usage_mining.export_and_archive(
            log_dir, dest_dir, label=self._label(prefs), known_skills=known
        )
        if res.get("skipped"):
            self.report({"WARNING"}, "No usage logs to export yet.")
            return {"CANCELLED"}

        self.report(
            {"INFO"},
            "Exported {n} episodes to {z} ({a} log files archived)".format(
                n=res["episode_count"],
                z=os.path.basename(res["zip_path"]),
                a=res["archived_files"],
            ),
        )
        return {"FINISHED"}
