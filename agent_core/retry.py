"""Retry helpers for transient provider API failures."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Awaitable, Callable, TypeVar

if TYPE_CHECKING:
    import httpx

T = TypeVar("T")

# ---------------------------------------------------------------------------
# Timeout constants — modelled on Anthropic SDK (connect=5s, total=600s)
# ---------------------------------------------------------------------------
DEFAULT_CONNECT_TIMEOUT = 5.0       # detect real network failures fast
DEFAULT_REQUEST_TIMEOUT = 600.0     # 10 min — covers longest reasoning runs


def build_httpx_timeout(read_timeout: float | None = None) -> httpx.Timeout:
    """Return a structured httpx.Timeout with industry-standard defaults.

    * ``connect`` — 5 s (fast-fail on network problems).
    * ``read``    — *read_timeout* or ``DEFAULT_REQUEST_TIMEOUT`` (600 s).
    * ``write``   — 10 s.
    * ``pool``    — 5 s.

    Pass ``read_timeout=None`` to disable the read timeout entirely
    (the model may think for an unbounded duration).
    """
    import httpx

    return httpx.Timeout(
        connect=DEFAULT_CONNECT_TIMEOUT,
        read=read_timeout if read_timeout is not None else DEFAULT_REQUEST_TIMEOUT,
        write=10.0,
        pool=5.0,
    )


class ModelServerTimeoutError(TimeoutError):
    """Raised when the model server takes too long to produce a response."""


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay: float = 0.5
    max_delay: float = 4.0


def is_recoverable_error(exc: BaseException) -> bool:
    """Return True for network, timeout, rate-limit, and 5xx-like failures."""
    if isinstance(exc, asyncio.CancelledError):
        return False
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    if status_code is not None:
        return status_code in {408, 409, 425, 429, 500, 502, 503, 504}

    name = type(exc).__name__.lower()
    return (
        "timeout" in name
        or "connect" in name
        or "network" in name
        or "readerror" in name
        or "writeerror" in name
    )


async def run_with_retries(
    operation: Callable[[], Awaitable[T]],
    *,
    policy: RetryPolicy | None = None,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    is_recoverable: Callable[[BaseException], bool] = is_recoverable_error,
    on_retry: Callable[[int, int, BaseException, float], None] | None = None,
) -> T:
    """Run an async operation with bounded exponential backoff."""
    active_policy = policy or RetryPolicy()
    attempts = max(1, active_policy.max_attempts)

    for attempt in range(1, attempts + 1):
        try:
            return await operation()
        except BaseException as exc:
            if attempt >= attempts or not is_recoverable(exc):
                raise
            delay = min(
                active_policy.max_delay,
                active_policy.base_delay * (2 ** (attempt - 1)),
            )
            if on_retry is not None:
                on_retry(attempt, attempts, exc, delay)
            if delay > 0:
                await sleep(delay)

    raise RuntimeError("retry loop exited unexpectedly")


async def run_with_model_timeout(awaitable: Awaitable[T], *, timeout: float) -> T:
    """Apply a user-facing total wait timeout around a provider operation."""
    try:
        return await asyncio.wait_for(awaitable, timeout=max(0.001, float(timeout)))
    except asyncio.TimeoutError as exc:
        raise ModelServerTimeoutError(
            f"Model server timed out after {timeout:.1f}s"
        ) from exc
