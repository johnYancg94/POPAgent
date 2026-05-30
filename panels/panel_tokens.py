# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.

from bpy.types import Panel, UILayout

from .panel import POLYGONINGENIEUR_panel
from ..operators.operator_usage import (
    CHAT_COMPANION_OT_clear_usage,
    CHAT_COMPANION_OT_export_usage_csv,
    CHAT_COMPANION_OT_mine_logs,
)
from ..utils.usage_stats import format_cost_rmb, format_tokens, summarize_usage
from .. import __package__ as base_package
from ..translations import POPAGENT_CTX


class CHAT_COMPANION_PT_tokens(POLYGONINGENIEUR_panel, Panel):
    bl_idname = "CHAT_COMPANION_PT_tokens"
    bl_label = "Usage"
    bl_translation_context = POPAGENT_CTX
    bl_order = 3
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header(self, context):
        self.layout.label(text="", icon="SORTTIME")

    def draw(self, context):
        usage_records = context.scene.chat_companion_usage
        summary = summarize_usage(usage_records)

        layout = self.layout
        layout.use_property_split = False
        layout.use_property_decorate = False

        # Export is independent of scene state: usage logs accumulate on disk
        # across all projects, so this button must show even in a brand-new
        # file with zero scene usage, and regardless of developer mode.
        self._draw_export(layout)

        if summary["requests"] == 0:
            empty = layout.column(align=True)
            empty.label(text="No usage recorded for this scene yet.", icon="INFO")
            empty.label(text="Ask POPAgent and this panel will fill in.")
            return

        if not self._developer_mode(context):
            self._draw_compact_summary(layout, summary)
            return

        self._draw_summary(layout, summary)
        layout.separator()
        self._draw_breakdown(layout, summary)
        layout.separator()
        self._draw_recent(layout, usage_records)
        layout.separator()
        self._draw_actions(layout)

    def _developer_mode(self, context) -> bool:
        try:
            prefs = context.preferences.addons[base_package].preferences
            return bool(getattr(prefs, "developer_mode", False))
        except Exception:
            return False

    def _draw_compact_summary(self, layout: UILayout, summary: dict):
        box = layout.box()
        box.label(text="Scene Usage", icon="GRAPH")
        grid = box.grid_flow(row_major=True, columns=2, even_columns=True, even_rows=True)
        self._metric(grid, "Total tokens", format_tokens(summary["total_tokens"]), "SMALL_CAPS")
        self._metric(grid, "RMB cost", format_cost_rmb(summary["estimated_cost_rmb"]), "TAG")

    def _draw_summary(self, layout: UILayout, summary: dict):
        requests = summary["requests"]
        errors = summary["errors"]
        success_rate = 0
        if requests:
            success_rate = round(((requests - errors) / requests) * 100)

        box = layout.box()
        box.label(text="Scene Usage", icon="GRAPH")

        grid = box.grid_flow(row_major=True, columns=2, even_columns=True, even_rows=True)
        self._metric(grid, "Requests", str(requests), "FILE_TEXT")
        self._metric(grid, "Total tokens", format_tokens(summary["total_tokens"]), "SMALL_CAPS")
        self._metric(grid, "RMB cost", format_cost_rmb(summary["estimated_cost_rmb"]), "TAG")
        self._metric(grid, "Success", f"{success_rate}%", "CHECKMARK", label_ctxt=POPAGENT_CTX)
        if summary["avg_latency_ms"]:
            latency = box.row(align=True)
            latency.label(text=f"Average latency: {summary['avg_latency_ms']} ms", icon="TIME")

    def _draw_breakdown(self, layout: UILayout, summary: dict):
        box = layout.box()
        box.label(text="Token Breakdown", icon="LINENUMBERS_ON")

        col = box.column(align=True)
        self._line(col, "Input", summary["input_tokens"], "TRIA_RIGHT")
        self._line(col, "Output", summary["output_tokens"], "TRIA_RIGHT")
        if summary["cache_creation_tokens"]:
            self._line(col, "Cache creation", summary["cache_creation_tokens"], "TRIA_RIGHT")
        if summary["cache_read_tokens"]:
            self._line(col, "Cache read", summary["cache_read_tokens"], "TRIA_RIGHT")
        if summary["reasoning_tokens"]:
            self._line(col, "Reasoning", summary["reasoning_tokens"], "TRIA_RIGHT")

    def _draw_recent(self, layout: UILayout, usage_records):
        box = layout.box()
        box.label(text="Recent Requests", icon="PRESET")

        shown = 0
        for item in reversed(usage_records):
            row = box.row(align=True)
            row.alert = item.is_error
            icon = "ERROR" if item.is_error else "CHECKMARK"
            model = item.model or item.llm_organization or "model"
            row.label(text=item.created_at[-8:], icon=icon)
            row.label(text=model)
            row.label(text=format_tokens(item.total_tokens))
            row.label(text=format_cost_rmb(item.estimated_cost_rmb, item.cost_is_estimated))
            shown += 1
            if shown >= 8:
                break

    def _draw_export(self, layout: UILayout):
        box = layout.box()
        col = box.column(align=True)
        col.scale_y = 1.3
        col.operator(
            CHAT_COMPANION_OT_mine_logs.bl_idname,
            text="Export Usage Logs",
            text_ctxt="*",
            icon="EXPORT",
        )
        hint = box.row()
        hint.enabled = False
        hint.label(text="Weekly: click, save the .zip, send it in.", icon="INFO")

    def _draw_actions(self, layout: UILayout):
        row = layout.row(align=True)
        row.operator(
            CHAT_COMPANION_OT_export_usage_csv.bl_idname,
            text="Export CSV",
            icon="EXPORT",
        )
        clear = row.operator(
            CHAT_COMPANION_OT_clear_usage.bl_idname,
            text="Clear",
            text_ctxt=POPAGENT_CTX,
            icon="TRASH",
        )

    def _metric(self, layout: UILayout, label: str, value: str, icon: str, label_ctxt: str = ""):
        col = layout.column(align=True)
        col.label(text=label, text_ctxt=label_ctxt, icon=icon)
        value_row = col.row(align=True)
        value_row.scale_y = 1.2
        value_row.label(text=value)

    def _line(self, layout: UILayout, label: str, value: int, icon: str):
        row = layout.row(align=True)
        row.label(text=label, icon=icon)
        row.label(text=format_tokens(value))
