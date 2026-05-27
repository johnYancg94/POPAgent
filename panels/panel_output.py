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
from ..operators.operator_ask import CHAT_COMPANION_OT_ask
from ..utils.utils import wrap_string_to_panel
from ..utils.utils import wrap_array
from ..utils.utils import can_send_prompt
from .panel import POLYGONINGENIEUR_panel
from ..properties.properties import ChatCompanionProperties
from ..properties.addon_preferences import ChatCompanionPreferences
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
        if props.is_connecting:
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

        for index, part in enumerate(answer_parts):
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

            # ! list items
            if part["type"] == "list":
                for list_item in part["content"]:

                    step_number = int(list_item.split(".")[0])

                    # container for the whole list step
                    list_container = layout.column(align=True)
                    # split layout into two columns
                    list_split = list_container.split(
                        factor=30 / context.region.width, align=True
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
                    list_text = list_split.column(align=True)
                    wrapped_list = wrap_string_to_panel(
                        context=context, string=list_item, padding=30
                    )
                    for index, list_line in enumerate(wrapped_list):
                        if index == 0:
                            list_text.label(text=list_line)
                        elif step_number <= 9:
                            list_text.label(text="    " + list_line)
                        elif step_number >= 10:
                            list_text.label(text="      " + list_line)

                # TODO ask for script for all steps
                # layout.label(text="Get script for all steps")

            # ! code
            if part["type"] == "code" and len(part["content"]) > 0:
                code_container = layout.column(align=True)

                header = code_container.column_flow(columns=3, align=True)
                header.scale_y = 1.1
                code_language = (
                    part["code_language"] if part["code_language"] else "Text"
                )
                header.label(text=code_language)

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
                for line_index, code_line in enumerate(part["content"]):
                    # container
                    code_line_container = box.row(align=True)
                    code_line_container.scale_y = 0.6
                    # line number
                    code_line_number = code_line_container.column(align=True)
                    line_number = line_index + 1
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
                            code_line_text.label(text="    " + wrapped_line)
                        else:
                            code_line_text.label(text=wrapped_line)

                    code_line_text.alignment = "EXPAND"
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

        # ! agent tool call timeline
        history = context.scene.chat_companion_history
        chat_properties = context.scene.chat_companion_properties
        if len(history) > 0:
            selected_item = history.get(str(chat_properties.selected_history_item))
            if selected_item and selected_item.tool_calls_json:
                try:
                    tool_calls = json.loads(selected_item.tool_calls_json)
                except (json.JSONDecodeError, AttributeError):
                    tool_calls = []
                if tool_calls:
                    layout.separator(factor=0.5)
                    timeline_box = layout.box()
                    header_row = timeline_box.row(align=True)
                    header_row.label(text=f"工具调用 ({len(tool_calls)})", icon="TOOL_SETTINGS")
                    for i, tc in enumerate(tool_calls):
                        tc_row = timeline_box.row(align=True)
                        ok = tc.get("result", {}).get("ok", True)
                        icon = "CHECKMARK" if ok else "ERROR"
                        tc_row.label(text=f"{i+1}. {tc.get('name', '?')}", icon=icon)

        # ! copy complete answer
        has_content: bool = False
        if len(answer_parts) > 0:
            answer_part: list = answer_parts[0].get("content", [])
            if len(answer_part[0]) > 0:
                has_content = True
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

    def draw_error_message(self, context: Context, layout: UILayout):
        chat_properties: ChatCompanionProperties = context.scene.chat_companion_properties

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

        # error message
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
