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
from ..agent_core.ui_bridge import ui_write, ui_call, ui_read
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
    if org == "minimax":
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
    if org == "minimax":
        return getattr(prefs, "minimax_api_key", "")
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
        # The coroutine runs on the background loop where bpy is off-limits.
        # Snapshot all bpy/prefs-derived data on the main thread first.
        try:
            snap = await ui_read(self._snapshot, context)
        except Exception as exc:
            ui_call(self.report, {"WARNING"}, f"Connection test setup failed: {exc}")
            self.quit()
            return

        props = snap["props"]
        ui_write(
            props,
            connection_test_running=True,
            connection_test_result="",
            connection_test_message="Testing...",
        )
        ui_call(self._redraw_area, snap["area"])

        try:
            await self._run_probe(props, snap)
        finally:
            ui_write(props, connection_test_running=False)
            ui_call(self._redraw_area, snap["area"])
            self.quit()

    def _snapshot(self, context) -> dict:
        """Main-thread read of everything the probe needs as plain data.

        Resolves bpy.context fresh (the context captured at invoke time may be
        stale by the time this runs on the main thread); keeps the captured
        area reference only for redraw targeting.
        """
        ctx = bpy.context
        props = ctx.scene.chat_companion_properties
        prefs = ctx.preferences.addons[base_package].preferences
        area = getattr(context, "area", None)
        snap: dict = {
            "props": props,
            "area": area,
            "deps_ok": dependencies.dependencies_installed,
            "error": None,
            "method": None,
            "url": None,
            "headers": None,
        }
        if not snap["deps_ok"]:
            return snap
        if not _api_key_for_prefs(prefs):
            snap["error"] = "No API key set"
            return snap
        provider = _provider_for_prefs(prefs)
        if provider is None:
            snap["error"] = f"Unsupported provider '{prefs.llm_organization}'"
            return snap
        snap["method"], snap["url"], snap["headers"] = provider.connectivity_request(prefs)
        return snap

    async def _run_probe(self, props, snap: dict) -> None:
        if not snap["deps_ok"]:
            self._fail(props, "Dependencies not installed")
            return
        if snap["error"]:
            self._fail(props, snap["error"])
            return

        import httpx

        method, url, headers = snap["method"], snap["url"], snap["headers"]
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
            ui_write(
                props,
                connection_test_result="ok",
                connection_test_message=f"OK · {latency_ms:.0f} ms",
            )
            ui_call(self.report, {"INFO"}, f"Connection OK ({latency_ms:.0f} ms)")
        elif status in (401, 403):
            self._fail(props, f"Auth failed (HTTP {status}) · check API key")
        elif status == 404:
            # Endpoint reached but no /models route: still proves connectivity.
            ui_write(
                props,
                connection_test_result="ok",
                connection_test_message=f"Reachable · {latency_ms:.0f} ms (no /models route)",
            )
            ui_call(self.report, {"INFO"}, f"Reachable ({latency_ms:.0f} ms)")
        else:
            self._fail(props, f"HTTP {status} · {latency_ms:.0f} ms")

    def _fail(self, props, message: str) -> None:
        ui_write(
            props,
            connection_test_result="fail",
            connection_test_message=message,
        )
        ui_call(self.report, {"WARNING"}, f"Connection test failed: {message}")

    @staticmethod
    def _redraw_area(area) -> None:
        try:
            if area is not None:
                area.tag_redraw()
        except Exception:
            pass
