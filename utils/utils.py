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

import re
import bpy
import copy
import asyncio
import textwrap
import platform
import itertools
from bpy.types import Context
from .. import __package__ as base_package


def parse_llm_content(answer: str) -> list:
    """Formats LLM answer"""

    # ! 1. split lines at line boundaries (for example linesep: \n)
    answer_list: list[str] = answer.splitlines()

    # ! 2. separate into text/code/list parts
    # for special treatment of individual parts
    answer_parts: list = []
    index: int = 0
    current_type: str = "none"
    # if the next part is a different one than the current
    # for example switching from text to code
    switch: bool = False
    first_list_item: bool = True
    jumping_list_gap: bool = False
    code_started: bool = False
    # can be text, python, ... whatever LLM puts after initial "```"
    code_language: str = ""

    # TODO lists are still not parsed correctly
    # TODO sometimes the first line of text after code is still wrongly considered code
    for line in answer_list:
        # * switching between parts
        # code ends, afterwards could be anything
        if "```" in line and code_started:
            current_type = "none"
            code_started = False
            code_language = ""
            continue
        # code begins
        elif "```" in line:
            current_type = "code"
            code_language = line.split("`")[-1].title()
            index += 1
            switch = True
            code_started = True
        # list line
        elif re.search(r"^\d+\.\s", line):
            current_type = "list"
            if first_list_item or not jumping_list_gap:
                first_list_item = False
                index += 1
                new_part = {"type": current_type, "content": []}
                answer_parts.append(new_part)
        # remove blank lines after a list entry
        elif current_type == "list" and len(line) == 0:
            jumping_list_gap = True
            continue
        # first line after last list line
        elif current_type == "list" and not re.search(r"^\d+\.\s", line):
            current_type = "text"
            index += 1
            switch = True
            first_list_item = True
        # after code, the type is none, and is followed by blank text lines
        elif current_type == "none" and len(line) == 0:
            current_type = "text"
            index += 1
            switch = True
        else:
            pass

        # * adding of lines to parts
        # create first part
        if len(answer_parts) == 0:
            # if first line is already code
            if current_type == "code":
                index -= 1
                switch = False
                new_part = {
                    "type": "code",
                    "content": [],
                    "code_language": code_language,
                    "error": "",
                    "error_line_number": None,
                }
            # first line is text part
            else:
                current_type = "text"
                new_part = {
                    "type": current_type,
                    "content": [
                        line,
                    ],
                }
            answer_parts.append(new_part)
        # create part of certain type
        elif switch:
            new_part = {
                "type": current_type,
                "content": [],
                "code_language": code_language,
                "error": "",
                "error_line_number": None,
            }
            answer_parts.append(new_part)
            switch = False
        # append line to current part type
        else:
            answer_parts[index]["content"].append(line)

        # reset if we are currently just jumping over a blank line
        # between list items
        jumping_list_gap = False

    # add indices
    for index, part in enumerate(answer_parts):
        part["index"] = index

    # # get full parts when they are finished (the next part started)
    # if len(answer_parts) > 1:
    #     print("---------------", answer_parts[-2])

    return answer_parts


def wrap_array(context, array):
    wrapped_array = []
    for line in array:
        # wrap each line if exceeding panel width
        wrap_list = textwrap.wrap(line, calc_max_characters(context))
        # add empty string to empty list
        # otherwise it gets lost in chaining later
        # (this will be an empty line)
        if len(wrap_list) == 0:
            wrap_list = [""]
        wrapped_array.append(wrap_list)
    wrapped_array = list(itertools.chain.from_iterable(wrapped_array))

    return wrapped_array


def wrap_string_to_panel(context, string, padding=0, linebreak=False):

    wrapped_string = copy.copy(string)
    # if string containes linebreaks (\n, ...)
    if linebreak:
        # break lines
        wrap_list = wrapped_string.splitlines()
        for index, line in enumerate(wrap_list):
            # wrap each line if exceeding panel width
            new_lines = textwrap.wrap(line, calc_max_characters(context, padding))
            if len(new_lines) == 0:
                new_lines.append("")
            wrap_list.pop(index)
            for new_line in reversed(new_lines):
                wrap_list.insert(index, new_line)
    else:
        # wrap each line if exceeding panel width
        wrap_list = textwrap.wrap(wrapped_string, calc_max_characters(context, padding))

    return wrap_list


def calc_max_characters(context, padding=0):
    # TODO is also dependent on Blender version! (WHY?)
    # thin/thick setting!
    addon_preferences = context.preferences.addons[base_package].preferences

    ui_scale = bpy.context.preferences.view.ui_scale

    # widget label only < Blender 4.3
    if bpy.app.version < (4, 3, 0):
        font_size_points = bpy.context.preferences.ui_styles[0].widget_label.points
    else:
        font_size_points = bpy.context.preferences.ui_styles[0].widget.points
    # font_size_scaled = font_size_points * ui_scale
    # font_size_pixel = 1.3333 * font_size_scaled
    font_size_pixel = (font_size_points * bpy.context.preferences.system.dpi) / 72

    # get region width minus tabs on right, minus margin
    tab_width = 40 * ui_scale
    margin = 60 * ui_scale
    extra = padding * ui_scale
    region_width = context.region.width - tab_width - margin - extra

    # TODO automatically change offset depending on dpi
    dpi_adjust = 2.2  # dpi = 72
    offset = dpi_adjust + addon_preferences.text_width_adjust
    # calc max characters per line
    max_characters = int(region_width // font_size_pixel)
    max_chars_offset = max(1, round(max_characters * offset))

    return max_chars_offset


def wrap_non_code_parts(answer_parts, width_in_px=50):

    wrapped_answer_parts = copy.deepcopy(answer_parts)

    for part in wrapped_answer_parts:
        wrapped_part = []
        for line in part["content"]:
            if part["type"] != "code":
                # wrap each line if exceeding panel width
                wrap_list = textwrap.wrap(line, width_in_px)
            else:
                wrap_list = [line]
            # add empty string to empty list
            # otherwise it gets lost in chaining later
            # (this will be an empty line)
            if len(wrap_list) == 0:
                wrap_list = [""]
            wrapped_part.append(wrap_list)
        part["content"] = list(itertools.chain.from_iterable(wrapped_part))

    return wrapped_answer_parts


def parts_to_pretty_string(parts):
    pretty_string = ""
    previous_type = "text"
    begin_comment = False
    end_comment = False
    for part in parts:
        # put multiline comment at the beginning of text part
        if part["type"] == "text" and not begin_comment:
            begin_comment = True
        for line in part["content"]:
            # add multiline comment
            if begin_comment:
                pretty_string += '"""\n'
                begin_comment = False
                end_comment = True
            # put an extra line break after code
            if part["type"] == "text" and previous_type == "code":
                pretty_string += "\n"
            # concatenate the line with a line break
            pretty_string += line + "\n"

            previous_type = part["type"]

        # add multiline comment at end of text block
        if end_comment:
            pretty_string += '"""\n'
            end_comment = False

    return pretty_string


def get_view3D_area(context):
    chat_properties = context.scene.chat_companion_properties

    # in 3d view context
    # ! make sure view3d editor is a visible area
    # * and we need the view3d area to overwrite the context
    # editor not visible, split area
    if not any(area.type == "VIEW_3D" for area in bpy.context.screen.areas):
        start_areas = bpy.context.screen.areas[:]

        chat_properties.view_was_splitted = True

        # If it's not visible, split the current area
        bpy.ops.screen.area_split(direction="VERTICAL", factor=0.0)

        # change space to text editor
        for area in context.screen.areas:
            if area not in start_areas:
                area.type = "VIEW_3D"

        # Get the new active area
        view3D_area = next(
            area for area in bpy.context.screen.areas if area.type == "VIEW_3D"
        )
    # view3d visible, get area
    else:
        # If view3d is already visible, just get its area
        view3D_area = next(
            area for area in bpy.context.screen.areas if area.type == "VIEW_3D"
        )

    return view3D_area


def get_text_editor_area(context):
    # ! copy code segment to current cursor location in text data block
    # editor not visible, split area
    if not any(area.type == "TEXT_EDITOR" for area in bpy.context.screen.areas):
        start_areas = bpy.context.screen.areas[:]

        # If it's not visible, split the current area
        bpy.ops.screen.area_split(direction="VERTICAL", factor=0.7)

        # change space to text editor
        for area in context.screen.areas:
            if area not in start_areas:
                area.type = "TEXT_EDITOR"

        # Get the new active area (which should now be the text editor)
        text_area = next(
            area for area in bpy.context.screen.areas if area.type == "TEXT_EDITOR"
        )
    # editor visible, get area
    else:
        # If the text editor is already visible, just get its area
        text_area = next(
            area for area in bpy.context.screen.areas if area.type == "TEXT_EDITOR"
        )

    return text_area


def can_send_prompt(context):
    addon_preferences = context.preferences.addons[base_package].preferences

    api_key: str | None = None
    if addon_preferences.llm_organization == "openai":
        api_key = addon_preferences.open_ai_api_key
    elif addon_preferences.llm_organization == "deepseek":
        api_key = addon_preferences.deepseek_api_key

    no_api_key = api_key is None or len(api_key) == 0 or api_key == ""
    chat_properties = context.scene.chat_companion_properties
    return (
        not no_api_key
        and not chat_properties.waiting_for_answer
        and not chat_properties.is_streaming
    )


def string_to_tokens_float(string):
    return len(string) / 4


async def print_waiting_string(
    context: Context,
    icon_set: str = "TEXT",
    interval: float = 0.4,
    text: str = "Generating",
):
    props = context.scene.chat_companion_properties

    suffix: str = "."
    icons: list = [
        "EVENT_A",
        "EVENT_B",
        "EVENT_C",
        "EVENT_D",
        "EVENT_E",
        "EVENT_F",
        "EVENT_G",
        "EVENT_H",
        "EVENT_I",
        "EVENT_J",
        "EVENT_K",
        "EVENT_L",
        "EVENT_M",
        "EVENT_N",
        "EVENT_O",
        "EVENT_P",
        "EVENT_Q",
        "EVENT_R",
        "EVENT_S",
        "EVENT_T",
        "EVENT_U",
        "EVENT_V",
        "EVENT_W",
        "EVENT_X",
        "EVENT_Y",
        "EVENT_Z",
    ]
    if icon_set == "CONNECTING":
        icons = ["PROP_OFF", "PROP_CON", "PROP_ON"]

    while props.is_connecting:
        for iteration in range(1, len(icons) + 1):
            props.waiting_string = text + iteration * suffix
            props.waiting_icon = icons[iteration - 1]
            try:
                # it sometimes doesn't exist when view3D isn't current area
                context.area.tag_redraw()
            except Exception as e:
                pass
            await asyncio.sleep(interval)
    return


async def print_answering_string(context: Context):
    props = context.scene.chat_companion_properties

    interval: float = 0.25
    text: str = "Answering"
    suffix: str = "."
    icons: list = ["ALIGN_TOP", "ALIGN_MIDDLE", "ALIGN_BOTTOM"]
    while props.is_streaming or props.waiting_for_answer:
        for iteration in range(1, len(icons) + 1):
            props.answering_string = text + iteration * suffix
            props.answering_icon = icons[iteration - 1]
            try:
                # it sometimes doesn't exist when view3D isn't current area
                context.area.tag_redraw()
            except Exception as e:
                pass
            await asyncio.sleep(interval)
    return


def construct_parts(text: str) -> str | list:
    """Construct the payload parts value that contains the prompt or data.
    Can be different for different LLMs."""

    return text


def get_system_info() -> str:
    """Get useful information of system, blender and addon."""

    from . import cc_globals
    from ..properties.addon_preferences import ChatCompanionPreferences
    try:
        from .. import bl_info
        version: str = bl_info.get("version", "1.5.14")
    except ImportError as e:
        version: str = "1.5.14"

    prefs: ChatCompanionPreferences = bpy.context.preferences.addons[
        base_package
    ].preferences

    addon_variant: str = "Full" if cc_globals.cc_full else "Free"
    if prefs.llm_organization == "openai":
        ai_model: str = prefs.open_ai_model
    elif prefs.llm_organization == "deepseek":
        ai_model: str = prefs.deepseek_model
    else:
        ai_model: str = ""

    return (
        f"System: {platform.platform()}\n"
        + f"Blender: {bpy.app.version_string}\n"
        + f"POPAgent {addon_variant} {version}\n"
        + f"{prefs.llm_organization} - {ai_model}"
    )
