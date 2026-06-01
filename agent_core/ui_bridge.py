"""
UI bridge: marshal bpy reads/writes from the bg agent loop onto the main thread.

Why this exists:
    The agent runtime now runs on a background OS thread (agent_core.async_runtime).
    bpy is NOT thread-safe — every read/write of scene properties, UI tagging, and
    operator calls must happen on Blender's main thread. agent_core.main_thread
    already provides run_on_main(fn, ...) -> concurrent.futures.Future, drained by a
    bpy.app.timers callback (independent of the old modal-kick mechanism).

    This module wraps run_on_main with three ergonomic helpers tuned for the agent's
    UI write patterns:

      ui_write(props, **fields)  fire-and-forget: set several props attrs at once.
                                 Returns immediately; ordering is guaranteed by the
                                 single-consumer FIFO drain queue. Use for live
                                 streaming deltas where awaiting every write would
                                 add a main-thread round-trip per token.

      ui_call(fn, *a, **kw)      fire-and-forget: run an arbitrary main-thread fn
                                 (area.tag_redraw, bpy.ops.* history append, ...).

      ui_read(fn, *a, **kw)      await a value computed on the main thread. Use for
                                 the few in-loop reads that must see live bpy state.

    Fire-and-forget calls intentionally drop the Future: the drain queue runs them
    in submission order on the main thread, so a sequence of ui_write/ui_call lands
    in order. If one raises, its Future captures the exception (see
    main_thread._drain_queue) and the next item still runs — a failed tag_redraw
    never blocks a subsequent answer write.
"""

from __future__ import annotations
import asyncio
import concurrent.futures
from typing import Any, Callable

from .main_thread import run_on_main


def _apply_fields(props, fields: dict) -> None:
    for key, value in fields.items():
        setattr(props, key, value)


def ui_write(props, **fields) -> None:
    """Fire-and-forget: set several attrs on a bpy props struct on the main thread.

    `props` is captured by reference; it is only touched inside the main-thread
    callback, never on the bg thread. Ordering vs other ui_* calls is preserved
    by the FIFO drain queue.
    """
    run_on_main(_apply_fields, props, fields)


def ui_call(fn: Callable, *args, **kwargs) -> None:
    """Fire-and-forget: run fn(*args, **kwargs) on the main thread, ignore result."""
    run_on_main(fn, *args, **kwargs)


async def ui_read(fn: Callable, *args, **kwargs) -> Any:
    """Await fn(*args, **kwargs) evaluated on the main thread; return its value.

    Raises whatever fn raises (the main-thread Future captures it). Must be
    awaited from a coroutine running on the bg loop.
    """
    future: concurrent.futures.Future = run_on_main(fn, *args, **kwargs)
    return await asyncio.wrap_future(future)
