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
import blf
import copy
import asyncio
import textwrap
import platform
import itertools
from bpy.types import Context
from .. import __package__ as base_package
from .markdown_renderer import parse_markdown_blocks
from ..agent_core.ui_bridge import ui_write, ui_call


def _redraw_area(area) -> None:
    try:
        if area is not None:
            area.tag_redraw()
    except Exception:
        pass


def parse_llm_content(answer: str) -> list:
    """Formats LLM answer"""
    return parse_markdown_blocks(answer)


def wrap_array(context, array):
    wrapped_array = []
    for line in array:
        # wrap each line if exceeding panel width
        wrap_list = wrap_text_to_panel_width(context, line)
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
            new_lines = wrap_text_to_panel_width(context, line, padding)
            if len(new_lines) == 0:
                new_lines.append("")
            wrap_list.pop(index)
            for new_line in reversed(new_lines):
                wrap_list.insert(index, new_line)
    else:
        # wrap each line if exceeding panel width
        wrap_list = wrap_text_to_panel_width(context, wrapped_string, padding)

    return wrap_list


def _font_size_pixels():
    ui_scale = bpy.context.preferences.view.ui_scale
    if bpy.app.version < (4, 3, 0):
        font_size_points = bpy.context.preferences.ui_styles[0].widget_label.points
    else:
        font_size_points = bpy.context.preferences.ui_styles[0].widget.points
    return max(1, int((font_size_points * bpy.context.preferences.system.dpi) / 72 * ui_scale))


def _text_width_px(text: str) -> float:
    font_id = 0
    try:
        blf.size(font_id, _font_size_pixels())
        return blf.dimensions(font_id, text)[0]
    except Exception:
        return len(text) * _font_size_pixels() * 0.55


def _available_text_width(context, padding=0):
    ui_scale = bpy.context.preferences.view.ui_scale
    tab_width = 40 * ui_scale
    margin = 34 * ui_scale
    extra = padding * ui_scale
    return max(36, context.region.width - tab_width - margin - extra)


def wrap_text_to_panel_width(context, text, padding=0):
    """Wrap by measured pixel width so narrow panels do not ellipsize labels."""
    max_width = _available_text_width(context, padding)
    if not text:
        return [""]

    lines = []
    for source_line in str(text).splitlines() or [""]:
        if not source_line:
            lines.append("")
            continue

        current = ""
        for token in re.findall(r"\S+\s*", source_line):
            candidate = current + token
            if current and _text_width_px(candidate.rstrip()) > max_width:
                lines.extend(_wrap_long_token(current.rstrip(), max_width))
                current = token.lstrip()
            else:
                current = candidate

        if current:
            lines.extend(_wrap_long_token(current.rstrip(), max_width))

    return lines or [""]


def _wrap_long_token(text, max_width):
    if _text_width_px(text) <= max_width:
        return [text]

    wrapped = []
    current = ""
    for char in text:
        candidate = current + char
        if current and _text_width_px(candidate) > max_width:
            wrapped.append(current)
            current = char
        else:
            current = candidate
    if current:
        wrapped.append(current)
    return wrapped


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
    elif addon_preferences.llm_organization == "mimo":
        api_key = addon_preferences.mimo_api_key
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

    # Loop condition reads props directly (reads are tolerated off the main
    # thread); writes + redraw are marshalled. Runs on the background loop.
    area = getattr(context, "area", None)
    while props.is_connecting:
        for iteration in range(1, len(icons) + 1):
            ui_write(
                props,
                waiting_string=text + iteration * suffix,
                waiting_icon=icons[iteration - 1],
            )
            ui_call(_redraw_area, area)
            await asyncio.sleep(interval)
    return


async def print_answering_string(context: Context):
    props = context.scene.chat_companion_properties

    interval: float = 0.25
    text: str = "Answering"
    suffix: str = "."
    icons: list = ["ALIGN_TOP", "ALIGN_MIDDLE", "ALIGN_BOTTOM"]
    area = getattr(context, "area", None)
    while props.is_streaming or props.waiting_for_answer:
        for iteration in range(1, len(icons) + 1):
            ui_write(
                props,
                answering_string=text + iteration * suffix,
                answering_icon=icons[iteration - 1],
            )
            ui_call(_redraw_area, area)
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
    elif prefs.llm_organization == "mimo":
        ai_model: str = prefs.mimo_model
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
