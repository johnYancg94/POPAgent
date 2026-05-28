"""Small policy helpers for the POPAgent loop."""

from __future__ import annotations

import json
from typing import Any


_IGNORED_KEYS = {
    "timestamp",
    "time",
    "request_id",
    "uuid",
    "nonce",
}


def normalized_tool_signature(name: str, arguments: dict) -> tuple[str, str]:
    return name, json.dumps(
        _normalize_value(arguments),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def choose_max_iters(prompt: str, *, tool_count: int, configured_max: int) -> int:
    configured = max(1, int(configured_max or 1))
    text = (prompt or "").lower()
    complex_markers = (
        "build",
        "create",
        "生成",
        "创建",
        "complete",
        "完整",
        "verify",
        "检查",
        "then",
        "然后",
    )
    suggested = 3
    if tool_count >= 6 or any(marker in text for marker in complex_markers):
        suggested = 15
    elif tool_count >= 3:
        suggested = 8
    return min(configured, suggested)


def _normalize_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _normalize_value(value[key])
            for key in sorted(value)
            if str(key).lower() not in _IGNORED_KEYS
        }
    if isinstance(value, list):
        return [_normalize_value(item) for item in value]
    if isinstance(value, str):
        compact = " ".join(value.split())
        if len(compact) > 160:
            return compact[:160]
        return compact
    return value
