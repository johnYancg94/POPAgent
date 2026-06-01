# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

"""
Async operator support.

History:
    This used to drive the asyncio loop cooperatively from a Blender modal
    operator's TIMER events (the "kick" design copied from blender-asyncio).
    That coupled the agent's progress to the main thread: when Blender stalled
    (heavy modifier recalc, big scenes, slow scripts), the TIMER stopped firing,
    nobody kicked the loop, and the whole agent — including in-flight LLM
    requests — froze and spuriously timed out.

    The loop now lives on a dedicated background thread (agent_core.async_runtime)
    and progresses independently of main-thread stalls. AsyncModalOperatorMixin
    submits its coroutine there. The operator STILL runs modal, but only as a
    lifetime anchor: it keeps `self` alive (so self.report / self.quit stay valid)
    and polls whether the background future has finished so it can clean up its
    TIMER on the main thread. The TIMER no longer drives the loop — if the main
    thread stalls, the coroutine keeps running and cleanup just happens a little
    late.

    All bpy access from inside the coroutine MUST still be marshalled to the main
    thread via agent_core.main_thread.run_on_main / agent_core.ui_bridge. bpy is
    not thread-safe.
"""

import asyncio
import logging
import typing

import bpy

from . import cc_globals
from ..agent_core import async_runtime

log: logging.Logger = logging.getLogger(__name__)


def _operator_task_key(operator) -> str | None:
    """Return the stable Blender operator idname for task registry lookups."""
    return getattr(type(operator), "bl_idname", None)


def setup_asyncio_executor() -> None:
    """Start the background event loop. Called from addon register()."""
    async_runtime.start()


class AsyncModalOperatorMixin:
    """Run async_execute() on the background loop; modal only as lifetime anchor.

    Subclasses implement `async def async_execute(self, context)`. The coroutine
    runs on agent_core.async_runtime's background thread, decoupled from main-thread
    stalls. The operator stays modal so `self` (and self.report/self.quit) survive
    until the coroutine finishes; its TIMER only polls future.done() to clean up.
    """

    log = logging.getLogger("%s.AsyncModalOperatorMixin" % __name__)
    _future = None
    timer = None

    def invoke(self, context, event):
        self._future = async_runtime.submit(self.async_execute(context))
        task_key = _operator_task_key(self)
        if task_key:
            cc_globals.active_async_tasks[task_key] = self._future

        wm = context.window_manager
        wm.modal_handler_add(self)
        # Slow poll: this TIMER only drives cleanup, not the loop. ~15 fps is
        # plenty for noticing the future finished, and is cheap when idle.
        self.timer = wm.event_timer_add(1 / 15, window=context.window)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        return self.invoke(context, None)

    async def async_execute(self, context):
        """Entry point of the asynchronous operator. Implement in a subclass."""
        return

    def quit(self):
        """Request cleanup. The coroutine drives its own bpy writes via ui_bridge;
        this just cancels the background future if it is still running."""
        fut = self._future
        if fut is not None and not fut.done():
            fut.cancel()

    def modal(self, context, event):
        if event.type != "TIMER":
            return {"PASS_THROUGH"}

        fut = self._future
        if fut is None or fut.done():
            if fut is not None:
                try:
                    # Surface any non-cancellation exception from the coroutine.
                    exc = fut.exception()
                    if exc is not None:
                        self.log.error("Async task failed: %s", exc)
                except Exception:
                    pass  # cancelled / still settling — nothing to report
            self._finish(context)
            return {"FINISHED"}

        return {"PASS_THROUGH"}

    def _finish(self, context):
        task_key = _operator_task_key(self)
        if task_key and cc_globals.active_async_tasks.get(task_key) is self._future:
            cc_globals.active_async_tasks.pop(task_key, None)
        if self.timer is not None:
            try:
                context.window_manager.event_timer_remove(self.timer)
            except Exception:
                pass
            self.timer = None
        self._future = None
