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
from bpy.types import Context
from .. import __package__ as base_package


def set_full_llms(context: Context) -> list[dict, dict]:
    """Updates header and payload depending on selected ai organization and model."""

    from ..properties.properties import ChatCompanionProperties
    from ..properties.addon_preferences import ChatCompanionPreferences

    props: ChatCompanionProperties = context.scene.chat_companion_properties
    prefs: ChatCompanionPreferences = context.preferences.addons[
        base_package
    ].preferences

    headers: dict = {}
    payload: dict = {}

    # ! deepseek
    if prefs.llm_organization == "deepseek":
        # key
        props.api_key = prefs.deepseek_api_key
        # url
        props.api_url = prefs.deepseek_base_url.rstrip("/") + "/chat/completions"
        # header
        headers.update({"Authorization": f"Bearer {props.api_key}"})
        headers.update({"Content-Type": "application/json"})
        if prefs.use_streaming:
            headers.update({"Accept": "text/event-stream"})
        # payload
        payload.update({"temperature": 1.0})
        payload.update({"top_p": 1.0})
        payload.update({"stream": prefs.use_streaming})
        payload.update({"model": prefs.deepseek_model})
        payload.update({"thinking": {"type": "enabled"}})
        payload.update({"reasoning_effort": "high"})
        # schema
        props.req_schema_contents = "messages"
        props.req_schema_role_system = "system"
        props.req_schema_role_user = "user"
        props.req_schema_role_assistant = "assistant"
        props.req_schema_parts = "content"
        props.res_schema_root = "choices"
        props.res_schema_content = "message"
        props.res_schema_finish_reason = "finish_reason"
    return [headers, payload]
