"""Pure Python tests for usage error records."""

from pathlib import Path
import importlib.util
import sys


ROOT = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location(
    "usage_stats", ROOT / "utils" / "usage_stats.py"
)
usage_stats = importlib.util.module_from_spec(spec)
sys.modules["usage_stats"] = usage_stats
spec.loader.exec_module(usage_stats)


class _Collection(list):
    def add(self):
        item = type("UsageItem", (), {})()
        self.append(item)
        return item


class _Context:
    def __init__(self):
        self.scene = type("Scene", (), {"chat_companion_usage": _Collection()})()


class _Prefs:
    llm_organization = "openai"
    open_ai_model = "unknown-model"


def test_error_usage_record_is_written_without_token_usage():
    context = _Context()

    usage_stats.add_usage_record(
        context,
        _Prefs(),
        None,
        mode="agent",
        prompt="prompt",
        latency_ms=42,
        status_code=503,
        is_error=True,
        error_message="server unavailable",
    )

    assert len(context.scene.chat_companion_usage) == 1
    item = context.scene.chat_companion_usage[0]
    assert item.is_error is True
    assert item.total_tokens == 0
    assert item.status_code == 503
    assert item.error_message == "server unavailable"


def run():
    test_error_usage_record_is_written_without_token_usage()
    print("test_usage_error_records OK")
    return True


if __name__ == "__main__":
    run()
