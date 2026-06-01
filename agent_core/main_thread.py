"""
Main-thread dispatcher for bpy operations.

All bpy reads/writes must happen on Blender's main thread.
Worker coroutines submit callables here and await the returned Future.

Usage:
    future = run_on_main(my_fn, arg1, kwarg=val)
    result = await asyncio.wrap_future(future)  # from worker thread/coroutine
"""

from __future__ import annotations
import bpy
import queue
import concurrent.futures
from typing import Callable, Any

_task_queue: queue.Queue = queue.Queue()
_TIMER_INTERVAL = 0.016  # ~60 fps drain rate


def run_on_main(fn: Callable, *args, **kwargs) -> concurrent.futures.Future:
    """Submit fn(*args, **kwargs) to run on the main thread; return a Future."""
    future: concurrent.futures.Future = concurrent.futures.Future()
    _task_queue.put_nowait((future, fn, args, kwargs))
    return future


def _drain_queue() -> float | None:
    """bpy.app.timers callback: drain pending tasks from the queue."""
    while not _task_queue.empty():
        try:
            future, fn, args, kwargs = _task_queue.get_nowait()
        except queue.Empty:
            break
        if future.cancelled():
            continue
        try:
            result = fn(*args, **kwargs)
            future.set_result(result)
        except Exception as exc:
            future.set_exception(exc)
    return _TIMER_INTERVAL


def _start_timer() -> None:
    if not bpy.app.timers.is_registered(_drain_queue):
        bpy.app.timers.register(_drain_queue, persistent=True)


def _stop_timer() -> None:
    if bpy.app.timers.is_registered(_drain_queue):
        bpy.app.timers.unregister(_drain_queue)


def shutdown_main_thread() -> None:
    """Call from addon unregister() to stop the timer and drain remaining tasks."""
    _stop_timer()
    # Cancel any queued futures so callers don't hang.
    while not _task_queue.empty():
        try:
            future, _, _, _ = _task_queue.get_nowait()
            future.cancel()
        except queue.Empty:
            break


def start_main_thread() -> None:
    """Call from addon register() to (re)start the drain timer.

    Import-time _start_timer() only fires on the FIRST import. After a
    disable→enable cycle the module stays cached, so the import-time start does
    not re-run — but unregister() called shutdown_main_thread() and killed the
    timer. Without an explicit restart the drain queue would be dead and every
    ui_read/ui_write from the agent loop would hang forever. register() must
    call this to re-arm the timer symmetrically with shutdown_main_thread().
    """
    _start_timer()


# Start the timer as soon as this module is imported (addon registration).
_start_timer()
