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


import json
from bpy.types import Panel, UILayout, Context
from ..utils import cc_globals
from ..operators.operator_copy import CHAT_COMPANION_OT_copy
from ..operators.operator_full_version import CHAT_COMPANION_OT_full_version
from ..operators.operator_website import CHAT_COMPANION_OT_website
from ..operators.operator_copy_error import CHAT_COMPANION_OT_copy_error
from ..operators.operator_answer_view import CHAT_COMPANION_OT_open_answer_text
from ..operators.operator_answer_view import CHAT_COMPANION_OT_toggle_answer_code
from ..operators.operator_ask import CHAT_COMPANION_OT_ask
from ..utils.utils import wrap_string_to_panel
from ..utils.utils import wrap_array
from ..utils.utils import can_send_prompt
from .panel import POLYGONINGENIEUR_panel
from ..properties.properties import ChatCompanionProperties
from ..properties.addon_preferences import ChatCompanionPreferences
from ..agent_core.execution_trace import parse_trace
from .. import __package__ as base_package


class CHAT_COMPANION_PT_output(POLYGONINGENIEUR_panel, Panel):
    bl_idname = "CHAT_COMPANION_PT_output"
    bl_label = "        Answer"
    bl_order = 1
    bl_options = {"HEADER_LAYOUT_EXPAND"}

    def draw_header(self, context: Context):
        props: ChatCompanionProperties = context.scene.chat_companion_properties
        layout: UILayout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        split: UILayout = layout.split(align=True, factor=3.5 / 10)
        split.scale_y = 1.1
        left: UILayout = split.row()
        left.alignment = "LEFT"
        right: UILayout = split.row()
        right.alignment = "RIGHT"

        # animate when waiting for answer to complete
        if props.is_streaming or props.waiting_for_answer:
            self.bl_label = ""
            left.label(text=props.answering_string, icon=props.answering_icon)
        else:
            self.bl_label = "        Answer"
            left.label(text="", icon="WORDWRAP_ON")

        right.separator(factor=1)

    def draw(self, context: Context):
        props = context.scene.chat_companion_properties

        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        # waiting for answer
        if props.is_connecting or (props.waiting_for_answer and props.waiting_string):
            layout.label(text=props.waiting_string, icon=props.waiting_icon)
        if cc_globals.request_failed:
            self.draw_error_message(context, layout)
        else:
            if len(props.answer_parts) > 0:
                self.draw_answer(context, layout)
            else:
                layout.label(text="")
        context.area.tag_redraw()

    def draw_answer(self, context: Context, layout: UILayout):
        chat_properties = context.scene.chat_companion_properties
        addon_preferences = context.preferences.addons[
            base_package
        ].preferences

        if cc_globals.cc_full:
            from ..full.operator_copy_code_cursor import (
                CHAT_COMPANION_OT_copy_code_cursor,
            )
            from ..full.operator_copy_code_clipboard import (
                CHAT_COMPANION_OT_copy_code_clipboard,
            )
            from ..full.operator_copy_code_text import CHAT_COMPANION_OT_copy_code_text
            from ..full.operator_run_code import CHAT_COMPANION_OT_run_code

        # ! get separated answer parts
        answer_parts = json.loads(chat_properties.answer_parts)
        display_mode = addon_preferences.answer_display_mode
        compact_width = display_mode == "COMPACT" or context.region.width < 280
        narrow_width = compact_width or context.region.width < 360

        self.draw_answer_actions(context, layout, chat_properties, addon_preferences)

        if display_mode == "RAW":
            self.draw_raw_answer(context, layout, chat_properties.answer)
            if addon_preferences.developer_mode:
                self.draw_selected_execution_trace(context, layout, chat_properties)
            return

        expanded_code_indices = self.parse_expanded_indices(
            chat_properties.expanded_answer_code_indices
        )
        code_preview_lines = addon_preferences.answer_code_preview_lines
        if compact_width:
            code_preview_lines = min(code_preview_lines, 6)

        for index, part in enumerate(answer_parts):
            # ! Markdown headings
            if part["type"] == "heading":
                heading = part["content"][0] if part["content"] else ""
                heading_container = layout.column(align=True)
                heading_container.scale_y = 0.9 if compact_width else 1.05
                for line in wrap_string_to_panel(context, heading):
                    heading_container.label(text=line, icon="DISCLOSURE_TRI_RIGHT")
                layout.separator(factor=0.15)

            # ! regular text to show
            if part["type"] == "text":
                wrapped_text = wrap_array(context, part["content"])
                for line in wrapped_text:
                    line_col = layout.column()
                    line_col.label(text=line)
                    if len(line) == 0:
                        line_col.scale_y = 0.3
                    else:
                        # TODO make dependent on point size
                        line_col.scale_y = 0.6

            # ! bullet list items
            if part["type"] == "bullet_list":
                for list_item in part["content"]:
                    self.draw_list_line(
                        context=context,
                        layout=layout,
                        marker="-",
                        icon="NONE",
                        text=list_item,
                        padding=22,
                    )

            # ! quote text
            if part["type"] == "quote":
                quote_box = layout.box()
                quote_box.enabled = False
                quote_box.scale_y = 0.65
                for quote_line in part["content"]:
                    for line in wrap_string_to_panel(
                        context=context, string=quote_line, padding=14
                    ):
                        quote_box.label(text=line, icon="INFO")

            # ! Markdown tables, reduced to readable rows for narrow panels
            if part["type"] == "table":
                table_box = layout.box()
                table_box.scale_y = 0.7
                rows = part["content"]
                headers = rows[0] if rows else []
                body_rows = rows[1:] if len(rows) > 1 else rows
                for row_cells in body_rows:
                    row_text_parts = []
                    for cell_index, cell in enumerate(row_cells):
                        if cell_index < len(headers) and headers != row_cells:
                            row_text_parts.append(f"{headers[cell_index]}: {cell}")
                        else:
                            row_text_parts.append(cell)
                    for line in wrap_string_to_panel(
                        context=context,
                        string="; ".join(row_text_parts),
                        padding=16,
                    ):
                        table_box.label(text=line)

            # ! list items
            if part["type"] == "list":
                for list_item in part["content"]:
                    list_bits = list_item.split(".", 1)
                    marker = list_bits[0] + "." if len(list_bits) > 1 else ""
                    item_text = list_bits[1].strip() if len(list_bits) > 1 else list_item

                    # container for the whole list step
                    list_container = layout.column(align=True)
                    # split layout into two columns
                    list_split = list_container.split(
                        factor=min(0.22, 34 / context.region.width), align=True
                    )

                    # ask for step button
                    list_button_column = list_split.row(align=True)
                    list_button_column.enabled = (
                        can_send_prompt(context) and cc_globals.cc_full
                    )
                    if cc_globals.cc_full:
                        list_button = list_button_column.operator(
                            operator=CHAT_COMPANION_OT_ask.bl_idname,
                            text="",
                            icon="RIGHTARROW_THIN",
                        )
                        prompt = "How do I do step " + list_item + "?"
                        list_button.user_prompt = prompt
                        list_button.use_streaming = addon_preferences.use_streaming
                    else:
                        list_button = list_button_column.operator(
                            operator=CHAT_COMPANION_OT_full_version.bl_idname,
                            text="",
                            icon="RIGHTARROW_THIN",
                        )
                        list_button.feature = "list_button"

                    # list text
                    list_body = list_split.split(
                        factor=min(0.18, 28 / context.region.width), align=True
                    )
                    list_marker = list_body.column(align=True)
                    list_marker.label(text=marker)
                    list_text = list_body.column(align=True)
                    list_text.scale_y = 0.65
                    wrapped_list = wrap_string_to_panel(
                        context=context, string=item_text, padding=42
                    )
                    for list_line in wrapped_list:
                        list_text.label(text=list_line)

                # TODO ask for script for all steps
                # layout.label(text="Get script for all steps")

            # ! code
            if part["type"] == "code" and len(part["content"]) > 0:
                code_container = layout.column(align=True)

                header = code_container.column_flow(
                    columns=2 if compact_width else 3, align=True
                )
                header.scale_y = 1.1
                code_language = (
                    part["code_language"] if part["code_language"] else "Text"
                )
                code_label = f"{code_language} ({len(part['content'])} lines)"
                header.label(text=code_label, icon="TEXT")

                # ! run code
                run_code_button = header.row(align=True)
                run_code_button.alignment = "CENTER"
                run_code_button.scale_x = 1.3
                run_code_button.enabled = cc_globals.cc_full and can_send_prompt(
                    context
                )
                if cc_globals.cc_full:
                    if answer_parts[index]["error"] == "":
                        run_code = run_code_button.operator(
                            operator=CHAT_COMPANION_OT_run_code.bl_idname,
                            text="",
                            icon="PLAY",
                        )
                        run_code.content = json.dumps(answer_parts[index]["content"])
                        run_code.index = index
                    else:
                        fix_code = run_code_button.operator(
                            operator=CHAT_COMPANION_OT_ask.bl_idname,
                            text="Ask to Fix Error",
                            icon="ERROR",
                        )
                        prompt = (
                            "Fix: "
                            + answer_parts[index]["error"]
                            + " and give me the whole fixed script again"
                        )
                        fix_code.user_prompt = prompt
                        fix_code.use_streaming = addon_preferences.use_streaming
                else:
                    run_code = run_code_button.operator(
                        operator=CHAT_COMPANION_OT_full_version.bl_idname,
                        text="",
                        icon="PLAY",
                    )
                    run_code.feature = "run_code"

                copy_buttons = header.row(align=True)
                copy_buttons.alignment = "RIGHT"

                is_expanded = index in expanded_code_indices
                needs_collapse = len(part["content"]) > code_preview_lines
                if needs_collapse:
                    toggle_code_button = copy_buttons.column(align=True)
                    toggle_code = toggle_code_button.operator(
                        operator=CHAT_COMPANION_OT_toggle_answer_code.bl_idname,
                        text="",
                        icon="TRIA_DOWN" if is_expanded else "TRIA_RIGHT",
                    )
                    toggle_code.index = index

                # ! copy to cursor in current script file
                copy_to_cursor_button = copy_buttons.column(align=True)
                copy_to_cursor_button.enabled = cc_globals.cc_full and can_send_prompt(
                    context
                )
                if cc_globals.cc_full:
                    copy_cursor = copy_to_cursor_button.operator(
                        operator=CHAT_COMPANION_OT_copy_code_cursor.bl_idname,
                        text="",
                        icon="ITALIC",
                    )
                    copy_cursor.content = json.dumps(answer_parts[index]["content"])
                else:
                    copy_cursor = copy_to_cursor_button.operator(
                        operator=CHAT_COMPANION_OT_full_version.bl_idname,
                        text="",
                        icon="ITALIC",
                    )
                    copy_cursor.feature = "copy_code"

                # ! copy to new a new script file
                copy_to_script_button = copy_buttons.column(align=True)
                copy_to_script_button.enabled = cc_globals.cc_full and can_send_prompt(
                    context
                )
                if cc_globals.cc_full:
                    copy_script = copy_to_script_button.operator(
                        operator=CHAT_COMPANION_OT_copy_code_text.bl_idname,
                        text="",
                        icon="TEXT",
                    )
                    copy_script.content = json.dumps(answer_parts[index]["content"])
                else:
                    copy_script = copy_to_script_button.operator(
                        operator=CHAT_COMPANION_OT_full_version.bl_idname,
                        text="",
                        icon="TEXT",
                    )
                    copy_script.feature = "copy_code"

                # ! copy code part
                copy_code_button = copy_buttons.column(align=True)
                copy_code_button.scale_y = 1
                copy_code_button.scale_x = 1
                copy_code_button.alignment = "RIGHT"
                copy_code_button.enabled = cc_globals.cc_full and can_send_prompt(
                    context
                )
                if cc_globals.cc_full:
                    copy_code = copy_code_button.operator(
                        operator=CHAT_COMPANION_OT_copy_code_clipboard.bl_idname,
                        text="",
                        icon="DUPLICATE",
                    )
                    copy_code.content = json.dumps(answer_parts[index]["content"])
                else:
                    copy_code = copy_code_button.operator(
                        operator=CHAT_COMPANION_OT_full_version.bl_idname,
                        text="",
                        icon="DUPLICATE",
                    )
                    copy_code.feature = "copy_code"

                # ! show code
                box = code_container.box()
                box.separator(factor=0.2)
                visible_code = part["content"]
                if needs_collapse and not is_expanded:
                    visible_code = visible_code[:code_preview_lines]
                for line_index, code_line in enumerate(visible_code):
                    # container
                    code_line_container = box.row(align=True)
                    code_line_container.scale_y = 0.6
                    # line number
                    line_number = line_index + 1
                    if not narrow_width:
                        code_line_number = code_line_container.column(align=True)
                        code_line_number.label(text=str(line_number))
                        code_line_number.alignment = "LEFT"
                        code_line_number.scale_x = 0.075
                        code_line_number.enabled = False
                    # code text
                    code_line_text = code_line_container.column(align=True)
                    if part["error_line_number"] == line_number:
                        code_line_text.alert = True
                    else:
                        code_line_text.alert = False
                    wrapped_code = wrap_string_to_panel(
                        context=context, string=code_line, padding=20
                    )
                    for wr_index, wrapped_line in enumerate(wrapped_code):
                        if wr_index > 0:
                            code_line_text.label(text=wrapped_line)
                        else:
                            code_line_text.label(text=wrapped_line)

                    code_line_text.alignment = "EXPAND"
                if needs_collapse and len(part["content"]) > len(visible_code):
                    hidden_count = len(part["content"]) - len(visible_code)
                    box.label(
                        text=f"{hidden_count} more lines hidden",
                        icon="HIDE_ON",
                    )
                box.separator(factor=0.2)

                # ! show code error message box if error is present
                if part["error"] != "":
                    error_box = code_container.box()
                    error_message_container = error_box.column(align=True)
                    error_header = error_message_container.column_flow(
                        columns=2, align=True
                    )
                    error_header.scale_y = 1.1
                    error_header.label(text="Error Message")
                    error_header_buttons = error_header.row(align=True)
                    error_header_buttons.alignment = "RIGHT"
                    copy_error_button = error_header_buttons.column(align=True)
                    copy_error_button.scale_y = 1
                    copy_error_button.scale_x = 1
                    copy_error_button.alignment = "RIGHT"
                    copy_code = copy_error_button.operator(
                        operator=CHAT_COMPANION_OT_copy_error.bl_idname,
                        text="",
                        icon="DUPLICATE",
                    )
                    copy_code.content = part["error"]

                    error_message_text = error_message_container.box()
                    error_message_text.enabled = False
                    error_message_text.scale_y = 0.5
                    error_message_text.separator(factor=0.1)
                    wrapped_error_message = wrap_string_to_panel(
                        context=context,
                        string=part["error"],
                        padding=10,
                        linebreak=True,
                    )
                    for line in wrapped_error_message:
                        error_message_text.label(text=line)
                    error_message_text.separator(factor=0.1)

                layout.separator(factor=0.2)

        if addon_preferences.developer_mode:
            self.draw_selected_execution_trace(context, layout, chat_properties)

        # ! copy complete answer
        has_content: bool = bool(chat_properties.answer)
        if has_content:
            copy_answer_button = layout.row(align=True)
            copy_answer_button.enabled = can_send_prompt(context)
            copy_all_props = copy_answer_button.operator(
                operator=CHAT_COMPANION_OT_copy.bl_idname,
                text="Copy Answer",
                icon="DUPLICATE",
            )
            copy_all_props.content_type = "FULL"
            copy_all_props.content = chat_properties.answer

    def draw_answer_actions(
        self,
        context: Context,
        layout: UILayout,
        chat_properties: ChatCompanionProperties,
        addon_preferences: ChatCompanionPreferences,
    ):
        if not chat_properties.answer:
            return

        actions = layout.row(align=True)
        actions.enabled = can_send_prompt(context)
        open_answer = actions.operator(
            operator=CHAT_COMPANION_OT_open_answer_text.bl_idname,
            text="Open Full",
            icon="TEXT",
        )
        open_answer.content = chat_properties.answer
        copy_answer = actions.operator(
            operator=CHAT_COMPANION_OT_copy.bl_idname,
            text="",
            icon="DUPLICATE",
        )
        copy_answer.content_type = "FULL"
        copy_answer.content = chat_properties.answer
        mode_row = layout.row(align=True)
        mode_row.scale_y = 0.85
        mode_row.prop(addon_preferences, "answer_display_mode", text="")
        layout.separator(factor=0.2)

    def draw_execution_trace(self, layout: UILayout, trace: dict, raw_json: str):
        layout.separator(factor=0.5)
        trace_box = layout.box()
        summary = trace.get("summary", {})
        tool_count = summary.get("tool_count", 0)
        error_count = summary.get("error_count", 0)

        header_row = trace_box.row(align=True)
        header_row.label(
            text=f"Execution Trace ({tool_count} tools, {error_count} errors)",
            icon="TOOL_SETTINGS",
        )
        copy_trace = header_row.operator(
            operator=CHAT_COMPANION_OT_copy.bl_idname,
            text="",
            icon="DUPLICATE",
        )
        copy_trace.content_type = "RAW"
        copy_trace.content = raw_json

        if trace.get("version") == 1:
            for i, tc in enumerate(trace.get("legacy_tool_calls", [])):
                tc_row = trace_box.row(align=True)
                result = tc.get("result", {}) if isinstance(tc, dict) else {}
                ok = result.get("ok", True) if isinstance(result, dict) else True
                icon = "CHECKMARK" if ok else "ERROR"
                tc_row.label(text=f"{i + 1}. {tc.get('name', '?')}", icon=icon)
            return

        if summary.get("aborted"):
            abort_row = trace_box.row(align=True)
            abort_row.alert = True
            abort_row.label(
                text=f"Aborted: {summary.get('abort_reason', '')}",
                icon="ERROR",
            )

        for iteration in trace.get("iterations", []):
            iter_row = trace_box.row(align=True)
            iter_row.label(
                text=(
                    f"Iter {iteration.get('index', 0)} "
                    f"{iteration.get('latency_ms', 0)}ms "
                    f"status {iteration.get('status_code', 0)} "
                    f"{iteration.get('finish_reason', '')}"
                ),
                icon="TIME",
            )
            for tc in iteration.get("tool_calls", []):
                tc_row = trace_box.row(align=True)
                tc_row.alert = not tc.get("ok", True)
                icon = "CHECKMARK" if tc.get("ok", True) else "ERROR"
                error_kind = tc.get("error_kind", "")
                suffix = f" [{error_kind}]" if error_kind else ""
                tc_row.label(
                    text=f"{tc.get('name', '?')} {tc.get('duration_ms', 0)}ms{suffix}",
                    icon=icon,
                )

    def draw_selected_execution_trace(
        self,
        context: Context,
        layout: UILayout,
        chat_properties: ChatCompanionProperties,
    ):
        history = context.scene.chat_companion_history
        if len(history) <= 0:
            return
        selected_item = history.get(str(chat_properties.selected_history_item))
        if not selected_item or not selected_item.tool_calls_json:
            return
        trace = parse_trace(selected_item.tool_calls_json)
        if trace["summary"].get("tool_count", 0) > 0 or trace["summary"].get("aborted"):
            self.draw_execution_trace(layout, trace, selected_item.tool_calls_json)

    def draw_raw_answer(self, context: Context, layout: UILayout, answer: str):
        raw_box = layout.box()
        raw_box.scale_y = 0.58
        for line in wrap_string_to_panel(context=context, string=answer, linebreak=True):
            raw_box.label(text=line)

    def parse_expanded_indices(self, value: str) -> set:
        indices = set()
        for item in value.split(","):
            item = item.strip()
            if not item:
                continue
            try:
                indices.add(int(item))
            except ValueError:
                pass
        return indices

    def draw_list_line(
        self,
        context: Context,
        layout: UILayout,
        marker: str,
        icon: str,
        text: str,
        padding: int,
    ):
        row = layout.split(factor=min(0.18, 24 / context.region.width), align=True)
        marker_col = row.column(align=True)
        if marker:
            marker_col.label(text=marker)
        else:
            marker_col.label(text="", icon=icon)
        text_col = row.column(align=True)
        text_col.scale_y = 0.65
        for line in wrap_string_to_panel(context=context, string=text, padding=padding):
            text_col.label(text=line)

    def draw_error_message(self, context: Context, layout: UILayout):
        chat_properties: ChatCompanionProperties = context.scene.chat_companion_properties
        try:
            addon_preferences = context.preferences.addons[
                base_package
            ].preferences
        except Exception:
            addon_preferences = None

        # error title
        error_title_container = layout.column(align=True)
        error_title_container.scale_y = 0.7
        error_title_container.alert = True
        error_title = wrap_string_to_panel(
            context=context, string=chat_properties.error_title
        )
        for line in error_title:
            error_title_container.label(text=line)

        # error info
        error_info_text = layout.column(align=True)
        error_info_text.scale_y = 0.7
        wrapped_error_info = wrap_string_to_panel(
            context=context, string=chat_properties.error_info, linebreak=True
        )
        for line in wrapped_error_info:
            error_info_text.label(text=line)

        if not bool(getattr(addon_preferences, "developer_mode", False)):
            return

        self.draw_error_details(context, layout, chat_properties)

    def draw_error_details(
        self,
        context: Context,
        layout: UILayout,
        chat_properties: ChatCompanionProperties,
    ):
        error_message_container = layout.column(align=True)
        header = error_message_container.column_flow(columns=2, align=True)
        header.scale_y = 1.1
        header.label(text="Error Message")
        header_buttons = header.row(align=True)
        header_buttons.alignment = "RIGHT"
        copy_error_button = header_buttons.column(align=True)
        copy_error_button.scale_y = 1
        copy_error_button.scale_x = 1
        copy_error_button.alignment = "RIGHT"
        copy_code: CHAT_COMPANION_OT_copy_error = copy_error_button.operator(
            operator=CHAT_COMPANION_OT_copy_error.bl_idname, text="", icon="DUPLICATE"
        )
        copy_code.content = chat_properties.error_message

        error_message_text = error_message_container.box()
        # error_message_text.enabled = False
        error_message_text.scale_y = 0.5
        error_message_text.separator(factor=0.1)
        wrapped_error_message = wrap_string_to_panel(
            context=context,
            string=chat_properties.error_message,
            linebreak=True,
            padding=10,
        )
        for line in wrapped_error_message:
            error_message_text.label(text=line)
        error_message_text.separator(factor=0.1)

        # error button
        if chat_properties.error_button_icon == "URL":
            # button to website with more information
            more_info: CHAT_COMPANION_OT_website = layout.operator(
                operator=CHAT_COMPANION_OT_website.bl_idname,
                text="More Information",
                icon="URL",
            )
            more_info.url = chat_properties.error_button_url
        elif chat_properties.error_button_icon == "ERROR":
            report_button = layout.operator(
                "wm.url_open",
                text=chat_properties.error_button_text,
                icon=chat_properties.error_button_icon,
            )
            report_button.url = chat_properties.error_button_content
        else:
            pass
