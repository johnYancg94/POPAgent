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


# Graduated anti-loop thresholds (count of identical signatures in the recent
# window, inclusive of the current call):
#   < WARN   -> proceed (normal retry)
#   == WARN  -> inject a correction nudge, but still execute this call
#   >= ABORT -> stop the loop (last-resort safety net)
_REPEAT_WARN = 2
_REPEAT_ABORT = 3


def repeat_intervention(recent_calls: list, sig: tuple, *, window: int = 6) -> str:
    """Decide how to react to a repeated tool signature.

    `recent_calls` must already include the current `sig`. Returns one of
    "proceed", "warn", or "abort".
    """
    repeated = sum(1 for s in recent_calls[-window:] if s == sig)
    if repeated >= _REPEAT_ABORT:
        return "abort"
    if repeated == _REPEAT_WARN:
        return "warn"
    return "proceed"


def repeat_warning_text(name: str) -> str:
    """Correction nudge injected as a tool result when a call repeats once."""
    return (
        f"[POPAgent 提醒] 工具 `{name}` 刚以相同参数得到了相同结果。"
        "不要再用同样的参数重复调用。请改变策略："
        "①如果是 Blender API 名称/参数不确定，先调用 blender.api_search 核对再改写；"
        "②换一种实现思路或换一个更合适的 skill；"
        "③如果确实无法推进，请直接向用户说明卡点并提出具体问题，不要继续空转。"
    )


def is_parallel_safe(permission_level: str, metadata: dict | None) -> bool:
    """Whether a tool call may run concurrently with others in the same turn.

    Conservative: only pure read-only / pure-compute skills qualify. A skill is
    parallel-safe iff its confirm level is "never" (so it triggers no
    confirmation dialog — avoiding the single-flight _pending_future in
    confirm_dialog) and its metadata declares no side effects.
    """
    if permission_level != "never":
        return False
    meta = metadata or {}
    if meta.get("modifies_scene"):
        return False
    if meta.get("writes_files"):
        return False
    if meta.get("launches_external_process"):
        return False
    return True


def plan_tool_groups(parallel_flags: list) -> list:
    """Partition tool-call indices into ordered execution groups.

    Consecutive parallel-safe calls collapse into one group (run concurrently);
    any non-parallel-safe call is its own singleton group (run serially). Groups
    always run in original order, and within a group results are still appended
    in original index order, so the tool_use<->tool_result wire correspondence
    that OpenAI/Anthropic require is preserved regardless of completion order.
    """
    groups: list = []
    i = 0
    n = len(parallel_flags)
    while i < n:
        if parallel_flags[i]:
            run = [i]
            i += 1
            while i < n and parallel_flags[i]:
                run.append(i)
                i += 1
            groups.append(run)
        else:
            groups.append([i])
            i += 1
    return groups


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
