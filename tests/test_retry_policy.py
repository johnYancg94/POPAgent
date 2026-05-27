"""Pure Python tests for transient API retry policy."""

from pathlib import Path
import importlib.util
import sys


ROOT = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location(
    "retry", ROOT / "agent_core" / "retry.py"
)
retry = importlib.util.module_from_spec(spec)
sys.modules["retry"] = retry
spec.loader.exec_module(retry)


RetryPolicy = retry.RetryPolicy
run_with_retries = retry.run_with_retries
is_recoverable_error = retry.is_recoverable_error


class _HTTPStatusError(Exception):
    def __init__(self, status_code):
        self.response = type("Response", (), {"status_code": status_code})()


class _TimeoutError(Exception):
    pass


async def _no_sleep(_seconds):
    return None


def test_retries_recoverable_errors_until_success():
    attempts = {"count": 0}

    async def operation():
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise _HTTPStatusError(503)
        return "ok"

    async def scenario():
        return await run_with_retries(
            operation,
            policy=RetryPolicy(max_attempts=3, base_delay=0),
            sleep=_no_sleep,
            is_recoverable=is_recoverable_error,
        )

    import asyncio

    assert asyncio.run(scenario()) == "ok"
    assert attempts["count"] == 3


def test_does_not_retry_unrecoverable_http_status():
    attempts = {"count": 0}

    async def operation():
        attempts["count"] += 1
        raise _HTTPStatusError(401)

    async def scenario():
        try:
            await run_with_retries(
                operation,
                policy=RetryPolicy(max_attempts=3, base_delay=0),
                sleep=_no_sleep,
                is_recoverable=is_recoverable_error,
            )
        except _HTTPStatusError:
            return "raised"

    import asyncio

    assert asyncio.run(scenario()) == "raised"
    assert attempts["count"] == 1


def test_timeout_like_errors_are_recoverable_by_name():
    assert is_recoverable_error(_TimeoutError())


def run():
    test_retries_recoverable_errors_until_success()
    test_does_not_retry_unrecoverable_http_status()
    test_timeout_like_errors_are_recoverable_by_name()
    print("test_retry_policy OK")
    return True


if __name__ == "__main__":
    run()
