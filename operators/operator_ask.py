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

# pyright: reportInvalidTypeForm=false


import bpy
import asyncio
import json
import time
import os
import traceback
from asyncio import Future
from bpy.props import StringProperty, BoolProperty
from bpy.types import Operator, Context, bpy_prop_collection
from ..utils import dependencies
from ..utils.async_loop import AsyncModalOperatorMixin
from ..utils import cc_globals
from ..utils.chat_setup import system_instructions
from ..utils.chat_setup import system_instructions_code_completion
from ..utils.utils import (
    parse_llm_content,
    print_waiting_string,
    print_answering_string,
    construct_parts,
    get_system_info,
)
from ..utils.usage_stats import add_usage_record, get_current_model
from urllib.parse import quote
from ..properties.properties import ChatCompanionProperties
from ..properties.addon_preferences import ChatCompanionPreferences
from ..properties.property_updates import PropertyUpdates
from .. import __package__ as base_package
from ..agent_core import skill_registry, executor
from ..agent_core.message_builder import MessageBuilder, ToolCall, history_context_items
from ..agent_core.context_builder import build_scene_summary
from ..agent_core.vision_inputs import collect_enabled_image_payloads
from ..agent_core.retry import (
    ModelServerTimeoutError,
    RetryPolicy,
    build_httpx_timeout,
    run_with_model_timeout,
    run_with_retries,
)
from ..agent_core.execution_trace import (
    create_trace,
    record_abort,
    record_iteration,
    record_tool_call,
)
from ..agent_core.agent_policy import choose_max_iters, normalized_tool_signature
from ..providers import OpenAICompatProvider, AnthropicProvider


def _addon_version_str() -> str:
    try:
        from .. import bl_info

        return ".".join(str(v) for v in bl_info.get("version", ()))
    except Exception:
        return ""


def _default_log_dir() -> str:
    """`<addon install dir>/usage_logs`. The addon root is two levels up from
    this file (operators/operator_ask.py)."""
    addon_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(addon_root, "usage_logs")


def _skill_meta_lookup(name: str) -> dict | None:
    """Map a skill name to owner/confirm-level/risk flags for the usage log.

    Returns None for unknown names (e.g. the LLM hallucinated a skill), so the
    log records the bare call without enrichment.
    """
    skill = skill_registry.get_skill_by_name(name)
    if not skill:
        return None
    meta = skill.get("metadata", {}) or {}
    return {
        "owner": skill.get("owner", ""),
        "confirm_level": skill_registry.get_permission_level(skill),
        "writes_files": bool(meta.get("writes_files")),
        "modifies_scene": bool(meta.get("modifies_scene")),
        "undoable": bool(meta.get("undoable")),
        "launches_external_process": bool(meta.get("launches_external_process")),
    }


class CHAT_COMPANION_OT_ask(Operator, AsyncModalOperatorMixin):
    bl_idname: str = "chat_companion.ask"
    bl_label: str = "Ask POPAgent"
    bl_description: str = (
        "Sends a prompt to a language AI and prints the answer in the addon panel of POPAgent"
    )
    bl_options: dict = {"REGISTER", "INTERNAL"}

    # properties
    user_prompt: StringProperty(options={"HIDDEN"})
    is_code_completion: BoolProperty(default=False, options={"HIDDEN"})
    is_context_menu: BoolProperty(default=False, options={"HIDDEN"})
    use_streaming: BoolProperty(default=False, options={"HIDDEN"})
    # temporary store state for code completion
    was_streaming: BoolProperty(default=False, options={"HIDDEN"})

    @classmethod
    def description(cls, context: Context, properties) -> str:
        addon_preferences: ChatCompanionPreferences = context.preferences.addons[
            base_package
        ].preferences
        chat_properties: ChatCompanionProperties = (
            context.scene.chat_companion_properties
        )

        api_key: str | None = None
        if addon_preferences.llm_organization == "openai":
            api_key = addon_preferences.open_ai_api_key
        elif addon_preferences.llm_organization == "mimo":
            api_key = addon_preferences.mimo_api_key
        elif addon_preferences.llm_organization == "deepseek":
            api_key = addon_preferences.deepseek_api_key
        elif addon_preferences.llm_organization == "anthropic":
            api_key = getattr(addon_preferences, "anthropic_api_key", "")

        no_api_key: bool = api_key is None or len(api_key) == 0 or api_key == ""
        desciption: str = (
            "Sends a prompt to a language AI and prints the answer in the addon panel of POPAgent"
        )
        if no_api_key:
            desciption = "Please enter your API key in the addons preferences first"
        if chat_properties.waiting_for_answer or chat_properties.is_streaming:
            desciption = "Please wait for the current answer before asking again"
        return desciption

    async def async_execute(self, context: Context):
        props: ChatCompanionProperties = context.scene.chat_companion_properties
        prefs: ChatCompanionPreferences = context.preferences.addons[
            base_package
        ].preferences

        # force update llm details
        # (they usually only get updated when changing llm orga or model)
        PropertyUpdates.update_llm_details(self, context)

        # check if api key and the userpromt
        # are not none and if it is not an empty string
        api_key_go: bool = props.api_key is not None and props.api_key
        user_prompt_go: bool = self.user_prompt is not None and self.user_prompt

        if not api_key_go and not user_prompt_go:
            self.report(
                {"WARNING"},
                "No API key and no prompt to answer. Enter your API key in the addons preferences and enter a prompt into the text field.",
            )
            self.quit()
            return
        elif not api_key_go and user_prompt_go:
            self.report(
                {"WARNING"},
                "No API key. Did you enter your API key in the addons preferences?",
            )
            self.quit()
            return
        elif not user_prompt_go and api_key_go:
            self.report({"WARNING"}, "No prompt entered.")
            self.quit()
            return

        # set prompt when the operator was called directly
        # and not via text field
        props.user_prompt = self.user_prompt

        # setting answering status to waiting
        props.waiting_for_answer = True
        props.is_connecting = True

        # * workaround
        # setting to empty strings so the old answer isn't displayed
        # for a brief moment before the ui updates to display new answer
        props.answer = ""
        props.answer_parts = ""
        props.expanded_answer_code_indices = ""
        props.waiting_string = ""
        props.waiting_icon = "BLANK1"
        props.error_button_icon = ""
        props.error_button_text = ""
        props.error_button_content = ""
        props.error_button_url = ""
        props.error_title = ""
        props.error_info = ""
        props.error_message = ""
        cc_globals.request_failed = False
        self._usage_recorded = False
        self._active_trace = None
        self._request_started_at = time.perf_counter()
        self._turn_cost = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "latency_ms": 0,
        }

        # if it is code completion, don't use streaming
        if self.is_code_completion:
            self.was_streaming = self.use_streaming
            self.use_streaming = False
            # this will trigger LLM updates, since some LLMs have different urls, payloads, ... for streaming/non-streaming
            prefs.use_streaming = False

        self.report({"INFO"}, "Your prompt was sent. Generating answer...")

        # async code to run for api call
        coroutines = [
            self.query_api(context),
            print_answering_string(context),
            print_waiting_string(context, icon_set="CONNECTING", text="Connecting"),
        ]
        # ! query
        try:
            async_return: Future = await asyncio.gather(*coroutines)
        except asyncio.CancelledError:
            props.waiting_for_answer = False
            props.is_connecting = False
            props.is_streaming = False
            props.waiting_string = "Cancelled"
            props.waiting_icon = "CANCEL"
            self.report({"INFO"}, "POPAgent request cancelled.")
            self.quit()
            return

        # update view_3d (where addon is located in (context))
        try:
            # it sometimes doesn't exist when view3D isn't current area
            context.area.tag_redraw()
        except Exception as e:
            pass

        self.report({"INFO"}, "POPAgent answered.")
        self.quit()

    async def query_api(self, context: Context):
        props: ChatCompanionProperties = context.scene.chat_companion_properties
        prefs: ChatCompanionPreferences = context.preferences.addons[
            base_package
        ].preferences
        history: bpy_prop_collection = context.scene.chat_companion_history

        if not dependencies.dependencies_installed:
            self.show_general_error(
                context=context,
                title="Missing dependencies",
                solution="Please install dependencies in the addons preferences.",
            )
            return None
        else:
            import httpx

        payload: dict = json.loads(props.api_payload)

        # put together all messages
        all_messages: list = []
        system_prompt: str = construct_parts(" ".join(system_instructions))
        if self.is_code_completion:
            system_prompt = construct_parts(
                " ".join(system_instructions_code_completion)
            )

        all_messages.append(
            {
                "role": props.req_schema_role_system,
                props.req_schema_parts: system_prompt,
            }
        )

        # ! add enabled history to messages
        max_history_context = getattr(prefs, "max_history_context", 5)
        history_context = history_context_items(history, max_history_context)
        for previous_history in reversed(history_context):
            all_messages.append(
                {
                    "role": props.req_schema_role_user,
                    props.req_schema_parts: construct_parts(
                        previous_history.user_prompt
                    ),
                }
            )
            all_messages.append(
                {
                    "role": props.req_schema_role_assistant,
                    props.req_schema_parts: construct_parts(
                        previous_history.answer
                    ),
                }
            )

        # add current prompt and attachments
        attachments = context.scene.chat_companion_attachments
        attachments_string = ""
        for attachment in attachments:
            if attachment.is_enabled:
                attachments_string += "\n" + json.loads(attachment.text) + "\n"
        prompt_and_attachments = self.user_prompt + attachments_string
        all_messages.append(
            {
                "role": props.req_schema_role_user,
                props.req_schema_parts: construct_parts(prompt_and_attachments),
            }
        )

        # ! add messages to payload
        payload.update({props.req_schema_contents: all_messages})

        try:
            async with httpx.AsyncClient() as client:
                # Agent mode must take precedence over the legacy chat streaming
                # branch. _agent_query() handles streaming-with-tools itself.
                available_skills = skill_registry.all_skills()
                use_agent = bool(available_skills) and getattr(
                    prefs, "agent_mode_enabled", True
                )

                if use_agent:
                    await self._agent_query(context, client)
                    return None

                # ! streaming
                if self.use_streaming:
                    props.is_streaming = True
                    if prefs.llm_organization in {"openai", "mimo", "deepseek"}:
                        payload["stream_options"] = {"include_usage": True}
                    print(
                        f"Sending streaming request:\n{props.api_url = }\n{props.api_headers}"
                    )
                    started_at = time.perf_counter()
                    status_code, raw_usage = await self._stream_with_retries(
                        context,
                        client,
                        url=props.api_url,
                        headers=json.loads(props.api_headers),
                        body=payload,
                        timeout=prefs.timeout,
                    )

                    cc_globals.request_failed = False
                    self._record_usage(
                        context,
                        prefs,
                        raw_usage,
                        mode="streaming",
                        prompt=self.user_prompt,
                        latency_ms=(time.perf_counter() - started_at) * 1000,
                        status_code=status_code,
                    )

                    if props.answer == "":
                        self.show_general_error(
                            context=context,
                            title="No Answer",
                            solution="There was no answer sent. Please try again or use another model.",
                        )
                    else:
                        # ! add to history
                        bpy.ops.chat_companion.add_history_item(
                            display_name=self.user_prompt,
                            prompt=self.user_prompt,
                            answer=props.answer,
                            parts=props.answer_parts,
                            is_favorite=False,
                        )

                    # setting answering status
                    props.waiting_for_answer = False
                    props.is_streaming = False

                    return None

                # ! for non streaming use async requests session
                else:
                    await self._plain_query(context, client, payload, props, prefs)

        except httpx.ConnectError as e:
            self.show_connection_error(context=context, error=e)
        except httpx.TimeoutException as e:
            # Maybe set up for a retry, or continue in a retry loop
            self.show_general_error(
                context=context,
                error=e,
                title="Timeout",
                solution="Possible solution:\nTrying to get an answer took too long, maybe the server is under heavy load, your internet connection is not stable at the moment or you've set the timeout very short?",
            )
        except ModelServerTimeoutError as e:
            self.show_general_error(
                context=context,
                error=e,
                title="Model Server Busy",
                solution=(
                    "The model server did not produce a response before the "
                    "configured timeout. The server may be busy or experiencing "
                    "high latency. Please try again later or switch models."
                ),
            )
        except httpx.TooManyRedirects as e:
            # Tell the user their URL was bad and try a different one
            self.show_general_error(
                context=context,
                error=e,
                title="Redirect Error",
                solution="The URL to the server is wrong. Please report this error.",
            )
        except httpx.RequestError as e:
            self.show_general_error(
                context=context,
                error=e,
                title="Request Error",
                solution="There was an unexpected error while trying to get an answer, please report this error.",
            )
        except httpx.HTTPError as e:
            # https://platform.openai.com/docs/guides/error-codes/api-errors
            http_response = getattr(e, "response", None)
            status_code = getattr(http_response, "status_code", 0)
            if status_code == 401:
                self.show_general_error(
                    context,
                    error=e,
                    title="HTTP 401 Error",
                    solution="Possible solution:\nEnsure the API key used is correct or generate a new one.\nNever share your API keys with anyone!",
                )
            elif status_code == 429:
                self.show_general_error(
                    context,
                    error=e,
                    title="HTTP 429 Error",
                    solution="Possible causes:\nLikely the servers are experiencing high traffic. Please retry your prompt after a brief wait or try another AI model.\n\nIt is also possible that you are sending prompts too quickly.\n\nOr you have hit your maximum monthly spend (hard limit) if you are using OpenAI, which you can view in the account billing section https://platform.openai.com/account/billing/limits.\n",
                )
            elif status_code == 500:
                self.show_general_error(
                    context,
                    error=e,
                    title="HTTP 500 Error",
                    solution="The server had an error while processing your request.\nPossible solution:\nRetry your request after a brief wait. For OpenAI you can check the status page: https://status.openai.com/",
                )
            elif status_code == 502:
                self.show_general_error(
                    context,
                    error=e,
                    title="HTTP 502 Error",
                    solution="The server had an error while processing your request.\nPossible solution:\nRetry your request after a brief wait. For OpenAI you can check the status page: https://status.openai.com/",
                )
            elif status_code == 400:
                text_400: str = (
                    "Possible solution:\nThere can be multiple reasons. It is possible that the servers are experiencing high traffic. Please retry your prompt after a brief wait. Feel free to report the error."
                )
                try:
                    error_details: dict = http_response.json()
                    text_400 = error_details.get("error").get("message")
                    print(f"Error details: {error_details}")
                except Exception:
                    pass
                self.show_general_error(
                    context=context, error=e, title="HTTP 400 Error", solution=text_400
                )
            elif status_code == 404:
                self.show_general_error(
                    context=context,
                    error=e,
                    title="AI Model Error",
                    solution="Possible solution:\nYou may not have been approved to use this model. Please check your user profile there or use another model.",
                )
            else:
                self.show_general_error(
                    context=context,
                    error=e,
                    solution="Please report this error and retry your prompt. Sorry for the inconvenience.",
                )
        except httpx.StreamError as e:
            self.show_general_error(
                context=context,
                error=e,
                title="Stream Error",
                solution="There was an error streaming the answer. Please report this error. If the error persists, disable streaming in the addon's preferences.",
            )
        except Exception as e:
            self.show_general_error(
                context=context,
                error=e,
                solution="There was an error in the addon, please report this error.",
            )
        finally:
            # setting answering status
            props.waiting_for_answer = False
            props.is_connecting = False
            props.is_streaming = False
            # reset to stream if it was a code completion and stream was selected before
            if self.was_streaming:
                prefs.use_streaming = True

    async def handle_stream_chunk(self, context: Context, response):
        props: ChatCompanionProperties = context.scene.chat_companion_properties
        prefs: ChatCompanionPreferences = context.preferences.addons[
            base_package
        ].preferences

        new_content = ""
        raw_usage = {}

        async for chunk in response.aiter_lines():
            # connected
            props.is_connecting = False

            if not chunk:
                continue

            if chunk == "event: message_start":
                continue

            # split word data from payload
            chunk_parts: list = chunk.split(":", 1)
            data_chunk: str = chunk_parts[1].strip()

            # break point
            if data_chunk == "[DONE]":
                break

            # convert chunk to dict
            try:
                data: dict = json.loads(data_chunk)
            except json.JSONDecodeError as e:
                continue

            if isinstance(data.get("usage"), dict):
                raw_usage = data["usage"]

            root: dict | list | None = data.get(props.res_schema_root)
            if not root:
                continue
            if isinstance(root, list):
                root = root[0]

            # OpenAI break point for whole stream
            if root.get(props.res_schema_finish_reason, "") == "stop":
                break

            # max length
            if root.get(props.res_schema_finish_reason, "") == "length":
                new_content += "\n\nThe model has reached its maximum context length (its maximum tokens/characters)! Please switch to an AI model with a higher context length (in the addons preferences) or reduce your prompt attachments."
                props.answer = new_content
                new_parts = parse_llm_content(new_content)
                props.answer_parts = json.dumps(new_parts)
                try:
                    # TODO has to work when switching context
                    # it sometimes doesn't exist
                    # when view3D isn't current area
                    context.area.tag_redraw()
                except Exception as e:
                    pass
                break

            # content
            if delta := root.get("delta"):
                # openai and llama content
                content_delta = delta.get(props.req_schema_parts)
                if isinstance(content_delta, str) and content_delta:
                    new_content += content_delta
                    props.answer = new_content
                    new_parts = parse_llm_content(new_content)
                    props.answer_parts = json.dumps(new_parts)
                try:
                    context.area.tag_redraw()
                except Exception as e:
                    pass
        return raw_usage

    async def _plain_query(self, context, client, payload, props, prefs):
        """Original non-streaming single-turn chat path."""
        print(f"Sending post request (plain):\n{props.api_url = }")
        started_at = time.perf_counter()
        response = await self._post_with_retries(
            context,
            client,
            url=props.api_url,
            headers=json.loads(props.api_headers),
            body=payload,
            timeout=prefs.timeout,
        )
        response.raise_for_status()
        cc_globals.request_failed = False
        status_code = response.status_code

        try:
            response = response.json()
        except json.JSONDecodeError:
            self.report({"WARNING"}, "Could not read response from server.")
            self.quit()
            return

        if response is None:
            self.report({"WARNING"}, "The response returned nothing.")
            self.quit()
            return

        self._record_usage(
            context,
            prefs,
            response.get("usage") or {},
            mode="plain",
            prompt=self.user_prompt,
            latency_ms=(time.perf_counter() - started_at) * 1000,
            status_code=status_code,
        )

        root = response.get(props.res_schema_root)
        if not root:
            self.report({"WARNING"}, "Could not get root from response.")
            self.quit()
            return
        if isinstance(root, list):
            root = root[0]

        content = root.get(props.res_schema_content)
        if isinstance(content, list):
            content = content[0]
        if not content:
            self.report({"WARNING"}, "Could not get content from response.")
            self.quit()
            return

        parts = content.get(props.req_schema_parts)
        if not parts:
            self.report({"WARNING"}, "Could not get parts from response.")
            self.quit()
            return

        props.answer = parts
        answer_parts = parse_llm_content(parts)
        props.answer_parts = json.dumps(answer_parts)

        bpy.ops.chat_companion.add_history_item(
            display_name=self.user_prompt,
            prompt=self.user_prompt,
            answer=parts,
            parts=json.dumps(answer_parts),
            is_favorite=False,
        )

        props.waiting_for_answer = False
        props.is_connecting = False

        report_icon = "INFO"
        report_message = "Answer generated."
        if self.is_code_completion:
            props.update_code_completion = True
            self.is_code_completion = False
            if props.code_completion_text_not_found:
                props.code_completion_text_not_found = False
                report_icon = "WARNING"
                report_message = "Could not paste code for completion."

        self.report({report_icon}, report_message)

    async def _agent_query(self, context, client):
        """Tool-calling agent loop (max_iters iterations)."""
        props: ChatCompanionProperties = context.scene.chat_companion_properties
        prefs: ChatCompanionPreferences = context.preferences.addons[
            base_package
        ].preferences
        history: bpy_prop_collection = context.scene.chat_companion_history

        org = prefs.llm_organization
        if org == "openai":
            provider = OpenAICompatProvider("openai")
        elif org == "mimo":
            provider = OpenAICompatProvider("mimo")
        elif org == "deepseek":
            provider = OpenAICompatProvider("deepseek")
        elif org == "anthropic":
            provider = AnthropicProvider()
        else:
            self.show_general_error(context, solution=f"Provider '{org}' not supported in agent mode.")
            return

        system_text = construct_parts(" ".join(system_instructions))
        system_text += (
            "\n\nLive Blender state rule: scene contents, selection, active object, "
            "mode, and enabled addons may change between chat turns. For requests "
            "about the current scene or current Blender state, call the relevant "
            "query tool again and do not rely on prior chat answers."
            "\n\nBlender Python API rule: before writing or executing Blender "
            "Python when API names, operator parameters, context requirements, "
            "or version behavior are uncertain, call `blender.api_search` and "
            "base the code on the returned official documentation results."
            "\n\nBlender node expert rule: for material-node tasks, inspect or "
            "validate first with `blender.material.inspect_nodes` or "
            "`blender.material.validate_nodes`; when the user explicitly wants "
            "PBR texture hookup, prefer `blender.material.connect_pbr_textures` "
            "over arbitrary Python. For Geometry Nodes tasks, inspect or validate "
            "first with `blender.geometry_nodes.inspect` or "
            "`blender.geometry_nodes.validate`; for a basic Geometry Nodes modifier "
            "or pass-through node group, prefer "
            "`blender.geometry_nodes.ensure_basic_group`. When exact Blender 5.1 "
            "ShaderNode or GeometryNode type identifiers are uncertain, call "
            "`blender.nodes.search_types` before choosing node IDs. For controlled "
            "node graph edits, prefer `blender.material.add_node`, "
            "`blender.material.connect_nodes`, `blender.material.set_node_input`, "
            "`blender.geometry_nodes.add_node`, `blender.geometry_nodes.connect_nodes`, "
            "and `blender.geometry_nodes.set_node_input`. Use `dev.run_python` only "
            "when the dedicated node skills cannot express the requested operation."
            "\n\nAgent planning/reflection rule: for multi-step tasks, keep a "
            "short internal plan before acting. After each tool result, check "
            "whether the result satisfies the user's goal before calling another "
            "tool."
        )
        try:
            scene_summary = await build_scene_summary()
            if scene_summary:
                system_text = system_text + "\n\n" + scene_summary
        except Exception as exc:
            print(f"[agent] scene summary failed: {exc}")
        skills = skill_registry.all_skills()
        tools = provider.skills_to_tools(skills)

        max_iters = choose_max_iters(
            self.user_prompt,
            tool_count=len(tools),
            configured_max=getattr(prefs, "agent_max_iters", 10),
        )
        max_history_context = getattr(prefs, "max_history_context", 5)
        # Anti-loop: track last 3 (skill, args_hash) pairs.
        recent_calls: list[tuple[str, str]] = []
        trace = create_trace()
        self._active_trace = trace

        # Streaming with tools: enabled when both prefs.use_streaming AND the
        # provider declares support. Falls back to non-streaming otherwise.
        use_stream = bool(getattr(prefs, "use_streaming", False)) and \
            provider.supports_streaming_with_tools()
        multimodal_enabled = bool(getattr(props, "multimodal_enabled", False))
        include_image_results = (
            multimodal_enabled and provider.supports_image_input(prefs)
        )
        user_images = []
        if include_image_results:
            user_images = collect_enabled_image_payloads(
                context.scene.chat_companion_image_attachments
            )
        if include_image_results:
            system_text += (
                "\n\nVision rule: when the user asks about what is visible in "
                "the current viewport, call `blender.viewport_screenshot`; its "
                "result will be attached as an image in the next model turn."
            )
        else:
            system_text += (
                "\n\nVision rule: the current model configuration does not "
                "support image input. Do not call `blender.viewport_screenshot` "
                "to visually inspect the scene; explain that visual reading "
                "requires enabling multimodal input and using a compatible model."
            )

        mb = MessageBuilder.from_history(history, max_items=max_history_context)
        # Collect enabled text attachments and append to user prompt
        text_attachments = context.scene.chat_companion_attachments
        attachments_string = ""
        for attachment in text_attachments:
            if attachment.is_enabled:
                try:
                    attachments_string += "\n" + json.loads(attachment.text) + "\n"
                except (json.JSONDecodeError, TypeError):
                    attachments_string += "\n" + attachment.text + "\n"
        prompt_with_attachments = self.user_prompt + attachments_string
        mb.append_user(prompt_with_attachments, images=user_images)

        props.is_connecting = False

        for iteration in range(max_iters):
            # Build provider-specific wire payload.
            if org == "anthropic":
                system_for_wire, messages = mb.to_anthropic(
                    system_text,
                    tool_name_mapper=provider._to_wire_tool_name,
                    include_image_results=include_image_results,
                )
                url, headers, body = provider.build_request(
                    prefs, messages, tools, system=system_for_wire, stream=use_stream
                )
            else:
                messages = mb.to_openai(
                    system_prompt=system_text,
                    tool_name_mapper=provider._to_wire_tool_name,
                    include_image_results=include_image_results,
                    include_reasoning_content=(
                        org == "deepseek"
                        or org == "mimo"
                    ),
                )
                url, headers, body = provider.build_request(
                    prefs, messages, tools, stream=use_stream
                )

            print(f"[agent] iter={iteration} url={url} stream={use_stream}")

            started_at = time.perf_counter()
            status_code = 200
            if use_stream:
                llm_resp = await self._agent_stream_iter(
                    context, client, provider, url, headers, body, prefs, props
                )
                if llm_resp is None:
                    record_abort(trace, "stream_error")
                    return
            else:
                response = await self._post_with_retries(
                    context,
                    client,
                    url=url,
                    headers=headers,
                    body=body,
                    timeout=prefs.timeout,
                )
                response.raise_for_status()
                cc_globals.request_failed = False
                status_code = response.status_code

                try:
                    resp_json = response.json()
                except json.JSONDecodeError:
                    record_abort(trace, "invalid_json")
                    self.show_general_error(context, solution="Could not parse LLM response as JSON.")
                    return

                llm_resp = provider.parse_response(resp_json)

            latency_ms = (time.perf_counter() - started_at) * 1000
            self._record_usage(
                context,
                prefs,
                llm_resp.usage,
                mode="agent",
                prompt=self.user_prompt,
                latency_ms=latency_ms,
                status_code=status_code,
            )
            iteration_entry = record_iteration(
                trace,
                index=iteration,
                stream=use_stream,
                latency_ms=latency_ms,
                status_code=status_code,
                finish_reason=llm_resp.finish_reason,
                text=llm_resp.text,
                reasoning_content=getattr(llm_resp, "reasoning_content", ""),
            )

            if llm_resp.tool_calls:
                # 1. Record assistant message with tool calls.
                tc_list = [
                    ToolCall(id=tc.id, name=tc.name, arguments=tc.arguments)
                    for tc in llm_resp.tool_calls
                ]
                mb.append_assistant_with_tool_calls(
                    llm_resp.text,
                    tc_list,
                    reasoning_content=getattr(llm_resp, "reasoning_content", ""),
                )

                # 2. Execute each tool and record results.
                for tc in llm_resp.tool_calls:
                    # Anti-deadloop check.
                    sig = normalized_tool_signature(tc.name, tc.arguments)
                    recent_calls.append(sig)
                    repeated = sum(1 for s in recent_calls[-6:] if s == sig)
                    if repeated >= 3:
                        final_text = (
                            f"检测到工具 `{tc.name}` 被反复以相同参数调用（≥3次），已中止循环。"
                            "请换一种方式或直接告诉我需要什么帮助。"
                        )
                        mb.append_assistant(final_text)
                        record_abort(trace, "anti_loop")
                        self._finish_agent(context, props, prefs, mb, final_text, trace)
                        return

                    tool_started_at = time.perf_counter()
                    result = await executor.run(tc, context)
                    mb.append_tool_result(tc.id, tc.name, result)
                    record_tool_call(
                        trace,
                        iteration_entry,
                        name=tc.name,
                        arguments=tc.arguments,
                        result=result,
                        duration_ms=(time.perf_counter() - tool_started_at) * 1000,
                    )

                # Continue loop for next LLM turn.
                continue

            else:
                # Final natural-language reply — done.
                final_text = llm_resp.text or "(no response)"
                mb.append_assistant(final_text)
                self._finish_agent(context, props, prefs, mb, final_text, trace)
                return

        # Exceeded max_iters.
        final_text = f"已达最大迭代次数（{max_iters}），任务可能未完成。"
        record_abort(trace, "max_iters")
        self._finish_agent(context, props, prefs, mb, final_text, trace)

    async def _agent_stream_iter(self, context, client, provider, url, headers,
                                 body, prefs, props):
        """One streaming iteration: feed SSE lines to provider's parser, push
        text deltas live to props.answer, return the assembled LLMResponse.

        Returns None on error (caller should bail out)."""
        props.is_streaming = True
        self._set_model_thinking(context, props)

        async def operation():
            parser = provider.create_stream_parser()
            running_text = ""
            props.answer = ""
            props.answer_parts = json.dumps([])
            async with client.stream(
                "POST", url=url, headers=headers, json=body,
                timeout=build_httpx_timeout(prefs.timeout),
            ) as response:
                response.raise_for_status()
                cc_globals.request_failed = False
                async for raw_line in response.aiter_lines():
                    if raw_line is None:
                        continue
                    line = raw_line.rstrip("\r")
                    events = parser.feed_line(line)
                    for ev in events:
                        if ev.kind == "text":
                            running_text += ev.payload
                            props.answer = running_text
                            try:
                                parts = parse_llm_content(running_text)
                                props.answer_parts = json.dumps(parts)
                            except Exception:
                                pass
                            try:
                                if context.area is not None:
                                    context.area.tag_redraw()
                            except Exception:
                                pass
                        # tool_call / done events handled at finalize().
            return parser.finalize()

        def on_retry(attempt, attempts, exc, delay):
            props.waiting_string = (
                f"Retrying stream {attempt + 1}/{attempts} "
                f"after {type(exc).__name__}"
            )
            props.waiting_icon = "FILE_REFRESH"
            try:
                if context.area is not None:
                    context.area.tag_redraw()
            except Exception:
                pass

        try:
            return await run_with_retries(
                operation,
                policy=RetryPolicy(max_attempts=3),
                on_retry=on_retry,
            )
        except ModelServerTimeoutError:
            raise
        except Exception as exc:
            print(f"[agent] streaming error: {exc}")
            self.show_general_error(context, solution=f"Streaming failed: {exc}")
            return None
        finally:
            props.is_streaming = False

    async def _post_with_retries(self, context, client, *, url, headers, body, timeout):
        props: ChatCompanionProperties = context.scene.chat_companion_properties
        self._set_model_thinking(context, props)

        async def operation():
            response = await client.post(
                url=url,
                headers=headers,
                json=body,
                timeout=build_httpx_timeout(timeout),
            )
            response.raise_for_status()
            return response

        def on_retry(attempt, attempts, exc, delay):
            props.waiting_string = (
                f"Retrying request {attempt + 1}/{attempts} "
                f"after {type(exc).__name__}"
            )
            props.waiting_icon = "FILE_REFRESH"
            try:
                if context.area is not None:
                    context.area.tag_redraw()
            except Exception:
                pass

        return await run_with_retries(
            operation,
            policy=RetryPolicy(max_attempts=3),
            on_retry=on_retry,
        )

    async def _stream_with_retries(self, context, client, *, url, headers, body, timeout):
        props: ChatCompanionProperties = context.scene.chat_companion_properties
        self._set_model_thinking(context, props)

        async def operation():
            props.answer = ""
            props.answer_parts = json.dumps([])
            async with client.stream(
                "POST",
                url=url,
                headers=headers,
                json=body,
                timeout=build_httpx_timeout(timeout),
            ) as response:
                response.raise_for_status()
                raw_usage = await self.handle_stream_chunk(context, response)
                return response.status_code, raw_usage

        def on_retry(attempt, attempts, exc, delay):
            props.waiting_string = (
                f"Retrying stream {attempt + 1}/{attempts} "
                f"after {type(exc).__name__}"
            )
            props.waiting_icon = "FILE_REFRESH"
            try:
                if context.area is not None:
                    context.area.tag_redraw()
            except Exception:
                pass

        return await run_with_retries(
            operation,
            policy=RetryPolicy(max_attempts=3),
            on_retry=on_retry,
        )

    def _set_model_thinking(self, context, props) -> None:
        props.waiting_string = "Model is thinking..."
        props.waiting_icon = "SORTTIME"
        try:
            if context.area is not None:
                context.area.tag_redraw()
        except Exception:
            pass

    def _record_usage(self, context, prefs, raw_usage, **kwargs) -> None:
        add_usage_record(context, prefs, raw_usage, **kwargs)
        if kwargs.get("is_error") or bool(raw_usage):
            self._usage_recorded = True
        turn = getattr(self, "_turn_cost", None)
        if turn is not None and isinstance(raw_usage, dict):
            turn["input_tokens"] += int(
                raw_usage.get("input_tokens") or raw_usage.get("prompt_tokens") or 0
            )
            turn["output_tokens"] += int(
                raw_usage.get("output_tokens") or raw_usage.get("completion_tokens") or 0
            )
            turn["total_tokens"] += int(raw_usage.get("total_tokens") or 0)
            turn["latency_ms"] += max(0, int(kwargs.get("latency_ms", 0) or 0))

    def _record_error_usage_once(
        self,
        context,
        prefs,
        error,
        *,
        status_code: int = 0,
    ) -> None:
        if getattr(self, "_usage_recorded", False):
            return
        response = getattr(error, "response", None)
        status = status_code or getattr(response, "status_code", 0)
        started_at = getattr(self, "_request_started_at", time.perf_counter())
        self._record_usage(
            context,
            prefs,
            None,
            mode=self._current_request_mode(context, prefs),
            prompt=self.user_prompt,
            latency_ms=(time.perf_counter() - started_at) * 1000,
            status_code=status,
            is_error=True,
            error_message=str(error),
        )

    def _current_request_mode(self, context, prefs) -> str:
        try:
            has_skills = bool(skill_registry.all_skills())
        except Exception:
            has_skills = False
        if has_skills and getattr(prefs, "agent_mode_enabled", True):
            return "agent"
        if self.use_streaming:
            return "streaming"
        return "plain"

    def _finish_agent(self, context, props, prefs, mb, final_text: str,
                      trace: dict | None = None):
        """Write final answer to props and history."""
        answer_parts = parse_llm_content(final_text)
        props.answer = final_text
        props.answer_parts = json.dumps(answer_parts)

        tool_calls_json = json.dumps(
            trace or getattr(self, "_active_trace", None) or [],
            ensure_ascii=False,
        )
        bpy.ops.chat_companion.add_history_item(
            display_name=self.user_prompt,
            prompt=self.user_prompt,
            answer=final_text,
            parts=json.dumps(answer_parts),
            is_favorite=False,
            tool_calls_json=tool_calls_json,
        )

        props.waiting_for_answer = False
        props.is_connecting = False
        self.report({"INFO"}, "Agent finished.")
        self._write_usage_log(context, prefs, trace)

    def _write_usage_log(self, context, prefs, trace) -> None:
        """Append one JSONL line for this turn. Never breaks the turn on error."""
        if not getattr(prefs, "trace_log_enabled", False):
            return
        trace = trace or getattr(self, "_active_trace", None)
        if not isinstance(trace, dict):
            return
        try:
            from ..agent_core import usage_log

            user_id = getattr(prefs, "trace_log_user_id", "") or ""
            if not user_id:
                user_id = usage_log.new_user_id()
                try:
                    prefs.trace_log_user_id = user_id
                except Exception:
                    pass

            include_full = bool(getattr(prefs, "trace_log_full", False))
            episode = usage_log.build_episode(
                trace=trace,
                user_id=user_id,
                env={
                    "blender": ".".join(str(v) for v in bpy.app.version),
                    "popagent": _addon_version_str(),
                },
                llm={
                    "org": getattr(prefs, "llm_organization", ""),
                    "model": get_current_model(prefs),
                    "mode": self._current_request_mode(context, prefs),
                },
                prompt=self.user_prompt,
                cost=dict(getattr(self, "_turn_cost", {}) or {}),
                include_args=include_full,
                include_results=include_full,
                include_prompt_full=include_full,
                meta_lookup=_skill_meta_lookup,
            )
            log_dir = getattr(prefs, "trace_log_dir", "") or _default_log_dir()
            usage_log.append_episode(log_dir, episode)
        except Exception as exc:
            print(f"[agent] usage log write failed: {exc}")

    def show_connection_error(self, context, error):

        chat_properties: ChatCompanionProperties = (
            context.scene.chat_companion_properties
        )
        prefs: ChatCompanionPreferences = context.preferences.addons[
            base_package
        ].preferences
        self._record_error_usage_once(context, prefs, error)
        if getattr(self, "_active_trace", None):
            record_abort(self._active_trace, "connection_error")

        # tell addon that request failed
        cc_globals.request_failed = True

        # error title and info
        chat_properties.error_title = "You are not connected to the internet."
        chat_properties.error_info = "Please check your internet connection.\n\nSee error message below, it could also be that the maximum number of retries was exceeded. In this case or any other unexpected error please report the error."

        # error message
        chat_properties.error_message = str(error) + "\n\n" + get_system_info()

        # error button
        chat_properties.error_button_icon = "ERROR"
        chat_properties.error_button_text = "Search This Error"
        # no content here because we are using a url
        chat_properties.error_button_url = (
            "https://platform.openai.com/docs/guides/error-codes"
        )
        chat_properties.error_button_content = chat_properties.error_button_url

        answer = ""
        chat_properties.answer = answer
        chat_properties.answer_parts = json.dumps(
            [{"type": "text", "content": [answer]}]
        )

        # ! add error to history
        bpy.ops.chat_companion.add_history_item(
            display_name="Connection Error",
            answer=chat_properties.answer,
            parts=chat_properties.answer_parts,
            is_error=True,
            tool_calls_json=json.dumps(
                getattr(self, "_active_trace", None) or [],
                ensure_ascii=False,
            ),
            error_button_icon=chat_properties.error_button_icon,
            error_button_text=chat_properties.error_button_text,
            error_button_content=chat_properties.error_button_content,
            error_button_url=chat_properties.error_button_url,
            error_title=chat_properties.error_title,
            error_info=chat_properties.error_info,
            error_message=chat_properties.error_message,
        )

        try:
            # it sometimes doesn't exist when view3D isn't current area
            context.area.tag_redraw()
        except Exception as e:
            pass
        self.report({"WARNING"}, "No Internet Connection")
        self.quit()

    def show_open_ai_error(self, context, error, response, solution):

        chat_properties: ChatCompanionProperties = (
            context.scene.chat_companion_properties
        )

        response_json = response.json()
        message = response_json["error"]["message"]
        err_type = response_json["error"]["type"]
        err_code = response_json["error"]["code"]

        # tell addon that request failed
        cc_globals.request_failed = True

        # error title and info
        chat_properties.error_title = "POPAgent could not get an answer..."
        chat_properties.error_info = solution

        # error message
        chat_properties.error_message = (
            message
            + "\n\n"
            + str(response.reason)
            + "\n"
            + str(error)
            + "\n\nError type: "
            + str(err_type)
            + "\nError code: "
            + str(err_code)
            + "\n\n"
            + get_system_info()
        )

        # error button
        chat_properties.error_button_icon = "URL"
        chat_properties.error_button_text = "More Information"
        # no content here because we are using a url
        chat_properties.error_button_content = ""
        chat_properties.error_button_url = (
            "https://platform.openai.com/docs/guides/error-codes"
        )

        answer = ""
        chat_properties.answer = answer
        chat_properties.answer_parts = json.dumps(
            [{"type": "text", "content": [answer]}]
        )

        # ! add error to history
        bpy.ops.chat_companion.add_history_item(
            display_name="OpenAI Error",
            answer=chat_properties.answer,
            parts=chat_properties.answer_parts,
            is_error=True,
            error_button_icon=chat_properties.error_button_icon,
            error_button_text=chat_properties.error_button_text,
            error_button_content=chat_properties.error_button_content,
            error_button_url=chat_properties.error_button_url,
            error_title=chat_properties.error_title,
            error_info=chat_properties.error_info,
            error_message=chat_properties.error_message,
        )

        try:
            # it sometimes doesn't exist when view3D isn't current area
            context.area.tag_redraw()
        except Exception as e:
            pass
        self.report({"WARNING"}, str(error))
        self.quit()

    def show_request_error(self, context, error, response, solution):

        chat_properties: ChatCompanionProperties = (
            context.scene.chat_companion_properties
        )

        response_json = response.json()
        message = response_json["error"]["message"]
        err_type = response_json["error"]["type"]
        err_code = response_json["error"]["code"]

        # tell addon that request failed
        cc_globals.request_failed = True

        # error title and info
        chat_properties.error_title = "POPAgent encountered an error..."
        chat_properties.error_info = solution

        # error message
        chat_properties.error_message = (
            message
            + "\n\n"
            + str(response.reason)
            + "\n"
            + str(error)
            + "\n\nError type: "
            + str(err_type)
            + "\nError code: "
            + str(err_code)
            + "\n\n"
            + get_system_info()
        )

        # error button
        chat_properties.error_button_icon = "ERROR"
        chat_properties.error_button_text = "Search This Error"
        # no content here because we are using a url
        chat_properties.error_button_url = (
            "https://platform.openai.com/docs/guides/error-codes"
        )
        chat_properties.error_button_content = chat_properties.error_button_url

        answer = ""
        chat_properties.answer = answer
        chat_properties.answer_parts = json.dumps(
            [{"type": "text", "content": [answer]}]
        )

        # ! add error to history
        bpy.ops.chat_companion.add_history_item(
            display_name="Request Error",
            answer=chat_properties.answer,
            parts=chat_properties.answer_parts,
            is_error=True,
            error_button_icon=chat_properties.error_button_icon,
            error_button_text=chat_properties.error_button_text,
            error_button_content=chat_properties.error_button_content,
            error_button_url=chat_properties.error_button_url,
            error_title=chat_properties.error_title,
            error_info=chat_properties.error_info,
            error_message=chat_properties.error_message,
        )

        try:
            # it sometimes doesn't exist when view3D isn't current area
            context.area.tag_redraw()
        except Exception as e:
            pass
        self.report({"WARNING"}, str(error))
        self.quit()

    def show_general_error(self, context, solution, error=None, title="Error"):

        chat_properties: ChatCompanionProperties = (
            context.scene.chat_companion_properties
        )
        prefs: ChatCompanionPreferences = context.preferences.addons[
            base_package
        ].preferences
        self._record_error_usage_once(context, prefs, error or title)
        if getattr(self, "_active_trace", None):
            record_abort(self._active_trace, title or "error")

        # tell addon that request failed
        cc_globals.request_failed = True

        # error title and info
        chat_properties.error_title = "POPAgent encountered an error..."
        chat_properties.error_info = solution

        # error message
        if error:
            error_message = "".join(
                traceback.format_exception(None, error, error.__traceback__)
            )
            chat_properties.error_message = (
                str(error_message) + "\n\n" + get_system_info()
            )
        else:
            chat_properties.error_message = "Error" + "\n\n" + get_system_info()
            error = "Error"

        # error button
        chat_properties.error_button_icon = "ERROR"
        chat_properties.error_button_text = "Search This Error"
        # no content here because we are using a url
        chat_properties.error_button_url = (
            "https://platform.openai.com/docs/guides/error-codes"
        )
        chat_properties.error_button_content = chat_properties.error_button_url

        answer = ""
        chat_properties.answer = answer
        chat_properties.answer_parts = json.dumps(
            [{"type": "text", "content": [answer]}]
        )
        chat_properties.waiting_for_answer = False

        # ! add error to history
        bpy.ops.chat_companion.add_history_item(
            display_name=title,
            answer=chat_properties.answer,
            parts=chat_properties.answer_parts,
            is_error=True,
            tool_calls_json=json.dumps(
                getattr(self, "_active_trace", None) or [],
                ensure_ascii=False,
            ),
            error_button_icon=chat_properties.error_button_icon,
            error_button_text=chat_properties.error_button_text,
            error_button_content=chat_properties.error_button_content,
            error_button_url=chat_properties.error_button_url,
            error_title=chat_properties.error_title,
            error_info=chat_properties.error_info,
            error_message=chat_properties.error_message,
        )

        try:
            # it sometimes doesn't exist when view3D isn't current area
            context.area.tag_redraw()
        except Exception as e:
            pass
        self.report({"WARNING"}, str(error))
        self.quit()
