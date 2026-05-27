"""Retry helpers for transient provider API failures."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable, TypeVar


T = TypeVar("T")


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay: float = 0.5
    max_delay: float = 4.0


def is_recoverable_error(exc: BaseException) -> bool:
    """Return True for network, timeout, rate-limit, and 5xx-like failures."""
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
