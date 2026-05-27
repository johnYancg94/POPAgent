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
Manages the asyncio loop.
(Copied from https://github.com/lampysprites/blender-asyncio,
who copied it from Blender Cloud plugin with minor changes)
And I made some changes.
"""


import asyncio
import traceback
import concurrent.futures
import logging
import gc
import typing
import bpy
from . import cc_globals
from concurrent.futures import ThreadPoolExecutor
from asyncio import AbstractEventLoop, Task
from logging import StreamHandler, Formatter, Logger
from typing import Any
from bpy.types import WindowManager, Context


# set up logging
formatter = Formatter(
    fmt="%(asctime)s UT-AL %(levelname)-8s %(message)s", datefmt="%H:%M:%S"
)
log_handler: StreamHandler = StreamHandler()
log_handler.setFormatter(formatter)
log: Logger = logging.getLogger(__name__)
log.addHandler(log_handler)

# Keeps track of whether a loop-kicking operator is already running.
_loop_kicking_operator_running: bool = False


def setup_asyncio_executor() -> None:
    """Sets up AsyncIO to run properly on each platform."""

    if kick_async_loop():
        erase_async_loop()
        global _loop_kicking_operator_running
        _loop_kicking_operator_running = False

    # On windows, ProactorEventLoop is now also the default event loop
    # Source: https://docs.python.org/3.11/library/asyncio-platforms.html#asyncio-windows-subprocess
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError as error:
        # If no loop is found, set a new one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    executor: ThreadPoolExecutor = concurrent.futures.ThreadPoolExecutor(max_workers=10)
    loop.set_default_executor(executor)


def kick_async_loop(*args) -> bool:
    """
    Performs a single iteration of the asyncio event loop.

    :return: whether the asyncio loop should stop after this kick.
    """

    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError as error:
        # If no loop is found, set a new one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    # Even when we want to stop, we always need to do one more
    # 'kick' to handle task-done callbacks.
    stop_after_this_kick: bool = False

    if loop.is_closed():
        log.warning("loop closed, stopping immediately.")
        return True

    all_tasks: set[Task[Any]] = asyncio.all_tasks(loop)
    if not len(all_tasks):
        log.debug("no more scheduled tasks, stopping after this kick.")
        stop_after_this_kick = True

    elif all(task.done() for task in all_tasks):
        log.debug(
            "all %i tasks are done, fetching results and stopping after this kick.",
            len(all_tasks),
        )
        stop_after_this_kick = True

        # Clean up circular references between tasks.
        gc.collect()

        for task_idx, task in enumerate(all_tasks):
            if not task.done():
                continue

            try:
                res: Any = task.result()
                log.debug("   task #%i: result=%r", task_idx, res)
            except asyncio.CancelledError:
                # No problem, we want to stop anyway.
                log.debug("   task #%i: cancelled", task_idx)
            except Exception:
                print("{}: resulted in exception".format(task))
                traceback.print_exc()

    loop.stop()
    loop.run_forever()

    return stop_after_this_kick


def ensure_async_loop() -> None:
    log.debug("Starting asyncio loop")
    # is {'RUNNING_MODAL'} or {'PASS_THROUGH'} or ...
    result: set = bpy.ops.chat_companion.loop()
    log.debug("Result of starting modal operator is %r", result)


def erase_async_loop() -> None:
    global _loop_kicking_operator_running

    log.debug("Erasing async loop")

    loop: AbstractEventLoop = asyncio.get_event_loop()
    loop.stop()


class AsyncLoopModalOperator(bpy.types.Operator):
    bl_idname = "chat_companion.loop"
    bl_label = "Runs the asyncio main loop"

    timer = None
    log: Logger = logging.getLogger(__name__ + ".AsyncLoopModalOperator")

    def __del__(self):
        global _loop_kicking_operator_running
        self.log.debug("Deleting Async Operator")
        # This can be required when the operator is running while Blender
        # (re)loads a file. The operator then doesn't get the chance to
        # finish the async tasks, hence stop_after_this_kick is never True.
        _loop_kicking_operator_running = False

    def execute(self, context: Context):
        return self.invoke(context, None)

    def invoke(self, context: Context, event):
        global _loop_kicking_operator_running

        if _loop_kicking_operator_running:
            self.log.debug("Another loop-kicking operator is already running.")
            return {"PASS_THROUGH"}

        context.window_manager.modal_handler_add(self)
        _loop_kicking_operator_running = True

        wm: WindowManager = context.window_manager
        self.timer = wm.event_timer_add(0.00001, window=context.window)

        return {"RUNNING_MODAL"}

    def modal(self, context: Context, event):
        global _loop_kicking_operator_running

        # If _loop_kicking_operator_running is set to False, someone called
        # erase_async_loop(). This is a signal that we really should stop
        # running.
        if not _loop_kicking_operator_running:
            return {"FINISHED"}

        if event.type != "TIMER":
            return {"PASS_THROUGH"}

        self.log.debug("KICKING LOOP")
        # stop after this kick?
        if kick_async_loop():
            context.window_manager.event_timer_remove(self.timer)
            _loop_kicking_operator_running = False

            self.log.debug("Stopped asyncio loop kicking")
            return {"FINISHED"}

        return {"RUNNING_MODAL"}


class AsyncModalOperatorMixin:
    async_task = None  # asyncio task for fetching thumbnails
    # asyncio future for signalling that we want to cancel everything.
    signalling_future = None
    log = logging.getLogger("%s.AsyncModalOperatorMixin" % __name__)

    _state = "INITIALIZING"
    stop_upon_exception = True

    def invoke(self, context: Context, event):
        context.window_manager.modal_handler_add(self)
        self.timer = context.window_manager.event_timer_add(
            1 / 15, window=context.window
        )

        self.log.info("Starting")
        self._new_async_task(self.async_execute(context))

        return {"RUNNING_MODAL"}

    async def async_execute(self, context: Context):
        """Entry point of the asynchronous operator.

        Implement in a subclass.
        """
        return

    def quit(self):
        """Signals the state machine to stop this operator from running."""
        self._state = "QUIT"

    def execute(self, context: Context):
        return self.invoke(context, None)

    def modal(self, context: Context, event):
        task = self.async_task

        if task and task.done() and task.cancelled():
            self.quit()
            self._finish(context)
            return {"FINISHED"}

        if task and task.done() and not task.cancelled():
            ex = task.exception()
            if ex is not None:
                self._state = "EXCEPTION"
                self.log.error("Exception while running task: %s", ex)
                if self.stop_upon_exception:
                    self.quit()
                    self._finish(context)
                    return {"FINISHED"}

                return {"RUNNING_MODAL"}

        if self._state == "QUIT":
            self._finish(context)
            return {"FINISHED"}

        return {"PASS_THROUGH"}

    def _finish(self, context: Context):
        task_key = getattr(self, "bl_idname", None)
        if task_key and cc_globals.active_async_tasks.get(task_key) is self.async_task:
            cc_globals.active_async_tasks.pop(task_key, None)
        self._stop_async_task()
        context.window_manager.event_timer_remove(self.timer)

    def _new_async_task(
        self, async_task: typing.Coroutine, future: asyncio.Future = None
    ):
        """Stops the currently running async task, and starts another one."""

        self.log.debug(
            "Setting up a new task %r, so any existing task must be stopped", async_task
        )
        self._stop_async_task()

        # Download the previews asynchronously.
        self.signalling_future = future or asyncio.Future()
        self.async_task = asyncio.ensure_future(async_task)
        task_key = getattr(self, "bl_idname", None)
        if task_key:
            cc_globals.active_async_tasks[task_key] = self.async_task
        self.log.debug("Created new task %r", self.async_task)

        # Start the async manager so everything happens.
        ensure_async_loop()

    def _stop_async_task(self):
        self.log.debug("Stopping async task")
        if self.async_task is None:
            self.log.debug("No async task, trivially stopped")
            return

        # Signal that we want to stop.
        self.async_task.cancel()
        if not self.signalling_future.done():
            self.log.info("Signalling that we want to cancel anything that's running.")
            self.signalling_future.cancel()

        # Wait until the asynchronous task is done.
        if not self.async_task.done():
            self.log.info("blocking until async task is done.")
            loop = asyncio.get_event_loop()
            try:
                loop.run_until_complete(self.async_task)
            except asyncio.CancelledError:
                self.log.info("Asynchronous task was cancelled")
                return

        # noinspection PyBroadException
        try:
            # This re-raises any exception of the task.
            self.async_task.result()
        except asyncio.CancelledError:
            self.log.info("Asynchronous task was cancelled")
        except Exception:
            self.log.exception("Exception from asynchronous task")
