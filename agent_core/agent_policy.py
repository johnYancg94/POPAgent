"""Small policy helpers for the POPAgent loop."""

from __future__ import annotations

import hashlib
import json
from typing import Any


_IGNORED_KEYS = {
    "timestamp",
    "time",
    "request_id",
    "uuid",
    "nonce",
    "loop_warning",
}


def normalized_tool_signature(name: str, arguments: dict) -> tuple[str, str]:
    canonical = json.dumps(
        _normalize_value(arguments),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return name, hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def normalized_result_signature(result: Any) -> tuple[str, str, str]:
    if not isinstance(result, dict):
        canonical = json.dumps(
            _normalize_value(result),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return (
            "ok",
            "",
            hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        )

    ok = bool(result.get("ok", True))
    error_kind = str(result.get("error_kind") or "")
    if not ok:
        error_text = str(result.get("error") or "")
        tail = next(
            (line.strip() for line in reversed(error_text.splitlines()) if line.strip()),
            "",
        )
        return "error", error_kind, tail[:500]

    canonical = json.dumps(
        _normalize_value(result),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return "ok", "", hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# Graduated anti-loop thresholds (count of identical signatures in the recent
# window, inclusive of the current call):
#   < WARN   -> proceed (normal retry)
#   == WARN  -> inject a correction nudge, but still execute this call
#   >= BLOCK -> reject only this tool call and let the model change strategy
_REPEAT_WARN = 2
_REPEAT_BLOCK = 3


def repeat_intervention(
    recent_calls: list,
    sig: tuple,
    *,
    window: int = 6,
    block_success: bool = False,
) -> str:
    """Decide how to react to a repeated tool signature.

    `recent_calls` contains completed calls as `(tool_signature,
    result_signature)` pairs. Returns "proceed", "warn", or "block".
    """
    outcomes = [
        outcome
        for previous_sig, outcome in recent_calls[-window:]
        if previous_sig == sig
    ]
    if not outcomes:
        return "proceed"
    latest = outcomes[-1]
    repeated = 0
    for outcome in reversed(outcomes):
        if outcome != latest:
            break
        repeated += 1
    latest_succeeded = bool(latest and latest[0] == "ok")
    if repeated >= _REPEAT_BLOCK - 1 and (
        block_success or not latest_succeeded
    ):
        return "block"
    if repeated >= _REPEAT_WARN - 1:
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


_ABSOLUTE_MAX_ITERS = 200
_SIMPLE_TASK_CAP = 5


def choose_max_iters(prompt: str, *, tool_count: int, configured_max: int) -> int:
    """Resolve effective max-iterations for a turn.

    - Complex tasks (many tools or strong markers) trust the user's
      ``configured_max`` so long pipelines can use the full headroom.
    - Simple tasks are capped at ``_SIMPLE_TASK_CAP`` to save cost, while
      still respecting a smaller user setting.
    - ``_ABSOLUTE_MAX_ITERS`` is a hard ceiling that bounds prefs tampering.
    """
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
        "pipeline",
        "批次",
    )
    is_complex = tool_count >= 5 or any(marker in text for marker in complex_markers)
    if is_complex:
        return min(_ABSOLUTE_MAX_ITERS, configured)
    return min(_ABSOLUTE_MAX_ITERS, configured, _SIMPLE_TASK_CAP)


def _normalize_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _normalize_value(value[key])
            for key in sorted(value)
            if str(key).lower() not in _IGNORED_KEYS
        }
    if isinstance(value, list):
        return [_normalize_value(item) for item in value]
    return value
