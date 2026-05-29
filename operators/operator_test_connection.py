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

"""Lightweight connectivity test for the selected LLM provider.

Sends a token-free `GET /models` probe to validate network reachability,
base URL and API key auth without spending any inference tokens, then
reports the round-trip latency in the N-panel.
"""

import time

import bpy
from bpy.types import Operator, Context

from ..utils import dependencies
from ..utils.async_loop import AsyncModalOperatorMixin
from ..properties.properties import ChatCompanionProperties
from ..properties.addon_preferences import ChatCompanionPreferences
from .. import __package__ as base_package
from ..providers import OpenAICompatProvider, AnthropicProvider


# Connectivity probe is intentionally fast: a stalled network should fail the
# test quickly rather than hang behind the long generation timeout.
_TEST_CONNECT_TIMEOUT = 5.0
_TEST_READ_TIMEOUT = 15.0


def _provider_for_prefs(prefs):
    org = getattr(prefs, "llm_organization", "")
    if org == "openai":
        return OpenAICompatProvider("openai")
    if org == "mimo":
        return OpenAICompatProvider("mimo")
    if org == "deepseek":
        return OpenAICompatProvider("deepseek")
    if org == "anthropic":
        return AnthropicProvider()
    return None


def _api_key_for_prefs(prefs) -> str:
    org = getattr(prefs, "llm_organization", "")
    if org == "openai":
        return getattr(prefs, "open_ai_api_key", "")
    if org == "mimo":
        return getattr(prefs, "mimo_api_key", "")
    if org == "deepseek":
        return getattr(prefs, "deepseek_api_key", "")
    if org == "anthropic":
        return getattr(prefs, "anthropic_api_key", "")
    return ""


class CHAT_COMPANION_OT_test_connection(Operator, AsyncModalOperatorMixin):
    bl_idname: str = "chat_companion.test_connection"
    bl_label: str = "Test Connection"
    bl_description: str = (
        "Send a tiny token-free request to the selected provider to check "
        "reachability, API key and round-trip latency"
    )
    bl_options: dict = {"REGISTER", "INTERNAL"}

    async def async_execute(self, context: Context):
        props: ChatCompanionProperties = context.scene.chat_companion_properties
        prefs: ChatCompanionPreferences = context.preferences.addons[
            base_package
        ].preferences

        props.connection_test_running = True
        props.connection_test_result = ""
        props.connection_test_message = "Testing..."
        self._redraw(context)

        try:
            await self._run_probe(context, props, prefs)
        finally:
            props.connection_test_running = False
            self._redraw(context)
            self.quit()

    async def _run_probe(self, context, props, prefs) -> None:
        if not dependencies.dependencies_installed:
            self._fail(props, "Dependencies not installed")
            return

        if not _api_key_for_prefs(prefs):
            self._fail(props, "No API key set")
            return

        provider = _provider_for_prefs(prefs)
        if provider is None:
            self._fail(props, f"Unsupported provider '{prefs.llm_organization}'")
            return

        import httpx

        method, url, headers = provider.connectivity_request(prefs)
        timeout = httpx.Timeout(
            _TEST_READ_TIMEOUT, connect=_TEST_CONNECT_TIMEOUT
        )

        started_at = time.perf_counter()
        try:
            async with httpx.AsyncClient() as client:
                response = await client.request(
                    method, url, headers=headers, timeout=timeout
                )
        except httpx.ConnectError:
            self._fail(props, "Cannot reach server (check Base URL / internet)")
            return
        except httpx.ConnectTimeout:
            self._fail(props, f"Connect timed out (>{int(_TEST_CONNECT_TIMEOUT)}s)")
            return
        except httpx.TimeoutException:
            self._fail(props, "Request timed out")
            return
        except Exception as exc:
            self._fail(props, f"{type(exc).__name__}: {exc}")
            return

        latency_ms = (time.perf_counter() - started_at) * 1000
        status = response.status_code

        if status == 200:
            props.connection_test_result = "ok"
            props.connection_test_message = f"OK · {latency_ms:.0f} ms"
            self.report({"INFO"}, f"Connection OK ({latency_ms:.0f} ms)")
        elif status in (401, 403):
            self._fail(props, f"Auth failed (HTTP {status}) · check API key")
        elif status == 404:
            # Endpoint reached but no /models route: still proves connectivity.
            props.connection_test_result = "ok"
            props.connection_test_message = (
                f"Reachable · {latency_ms:.0f} ms (no /models route)"
            )
            self.report({"INFO"}, f"Reachable ({latency_ms:.0f} ms)")
        else:
            self._fail(props, f"HTTP {status} · {latency_ms:.0f} ms")

    def _fail(self, props, message: str) -> None:
        props.connection_test_result = "fail"
        props.connection_test_message = message
        self.report({"WARNING"}, f"Connection test failed: {message}")

    def _redraw(self, context) -> None:
        try:
            if context.area is not None:
                context.area.tag_redraw()
        except Exception:
            pass
