"""
Background asyncio event loop for the agent runtime.

Why this exists:
    The agent's asyncio loop used to be driven cooperatively by a Blender modal
    operator's TIMER events (utils/async_loop.py). When Blender's main thread
    stalled (heavy modifier recalc, big scenes, slow scripts), the TIMER stopped
    firing, nobody kicked the loop, and the whole agent froze — including
    in-flight LLM requests, which then spuriously timed out.

    This module runs the event loop on a dedicated daemon OS thread that is NOT
    starved by main-thread stalls. Coroutines are submitted from the main thread
    (e.g. an operator's invoke) via submit(); they run independently. Any bpy
    access from inside those coroutines MUST still be marshalled back to the main
    thread via agent_core.main_thread.run_on_main / agent_core.ui_bridge — bpy is
    not thread-safe.

Lifecycle:
    start()    — called from addon register(). Idempotent.
    submit()   — schedule a coroutine on the bg loop, returns concurrent Future.
    shutdown() — called from addon unregister(). Cancels in-flight tasks, stops
                 the loop, joins the thread. Idempotent.
"""

from __future__ import annotations
import asyncio
import threading
import concurrent.futures
from typing import Coroutine, Any

_loop: asyncio.AbstractEventLoop | None = None
_thread: threading.Thread | None = None
_MAX_WORKERS = 10


def _run_loop(loop: asyncio.AbstractEventLoop) -> None:
    asyncio.set_event_loop(loop)
    try:
        loop.run_forever()
    finally:
        # run_forever returned (stop() was called); close out the loop cleanly.
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
        except Exception:
            pass
        loop.close()


def start() -> None:
    """Create the bg loop + thread if not already running. Idempotent."""
    global _loop, _thread
    if _thread is not None and _thread.is_alive():
        return
    _loop = asyncio.new_event_loop()
    _loop.set_default_executor(
        concurrent.futures.ThreadPoolExecutor(max_workers=_MAX_WORKERS)
    )
    _thread = threading.Thread(
        target=_run_loop, args=(_loop,), name="POPAgentAsyncLoop", daemon=True
    )
    _thread.start()


def is_running() -> bool:
    return _loop is not None and not _loop.is_closed() and \
        _thread is not None and _thread.is_alive()


def get_loop() -> asyncio.AbstractEventLoop | None:
    return _loop


def submit(coro: Coroutine) -> concurrent.futures.Future:
    """Schedule a coroutine on the bg loop from any thread.

    Returns a concurrent.futures.Future. .cancel() on it is thread-safe and
    propagates cancellation into the running coroutine.
    """
    if not is_running():
        start()
    return asyncio.run_coroutine_threadsafe(coro, _loop)


def shutdown(timeout: float = 5.0) -> None:
    """Cancel in-flight tasks, stop the loop, join the thread. Idempotent."""
    global _loop, _thread
    loop, thread = _loop, _thread
    if loop is None:
        return

    def _cancel_all() -> None:
        for task in asyncio.all_tasks(loop):
            task.cancel()

    if not loop.is_closed():
        try:
            loop.call_soon_threadsafe(_cancel_all)
        except RuntimeError:
            pass
        # Give cancellations a beat to propagate, then stop the loop.
        loop.call_soon_threadsafe(loop.stop)
    if thread is not None and thread.is_alive():
        thread.join(timeout=timeout)
    _loop = None
    _thread = None
