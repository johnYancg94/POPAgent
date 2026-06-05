"""Token 预算估算 + 老轮 tool_result 压缩 + 历史裁剪。

纯逻辑，不 import bpy。供 MessageBuilder 在输出 wire 格式前裁剪历史。
压缩只作用于历史轮次，最近 keep_last_n 条（本轮证据）永不压。"""
from __future__ import annotations
import json
from typing import Any


def estimate_tokens(text: str) -> int:
    """char/4 粗估，向上取整。不依赖外部 tokenizer。"""
    if not text:
        return 0
    return (len(text) + 3) // 4


def history_budget(
    context_window: int,
    *,
    reserve_for_output: int = 8000,
    reserve_for_system_and_tools: int = 20000,
) -> int:
    """从模型上下文窗口减去 output + system/tools 预留，得历史可用预算。
    最低钳到 4000，防极小窗口算出负值。"""
    return max(4000, context_window - reserve_for_output - reserve_for_system_and_tools)


_KEEP_KEYS = ("ok", "error_kind", "error", "action", "count")


def compact_tool_result(content: Any, max_chars: int) -> Any:
    """大 tool_result 降级。保留状态/关键字段，长 payload 换摘要指针。

    - dict：image_base64 → '<image elided>'；其余字段若整体 JSON 超 max_chars，
      把非关键字段里最长的字符串值截断并标 elided。
    - str：超 max_chars 截断 + 标记。
    - 其它：原样返回。"""
    if isinstance(content, str):
        if len(content) <= max_chars:
            return content
        return content[:max_chars] + f"...(elided {len(content) - max_chars} chars)"

    if not isinstance(content, dict):
        return content

    out = dict(content)
    if isinstance(out.get("image_base64"), str) and out["image_base64"]:
        out["image_base64"] = "<image elided>"

    if len(json.dumps(out, ensure_ascii=False)) <= max_chars:
        return out

    for key, val in list(out.items()):
        if key in _KEEP_KEYS:
            continue
        if isinstance(val, str) and len(val) > 80:
            out[key] = val[:80] + f"...(elided {len(val) - 80} chars)"
        elif isinstance(val, (list, dict)):
            blob = json.dumps(val, ensure_ascii=False)
            if len(blob) > 80:
                out[key] = blob[:80] + f"...(elided {len(blob) - 80} chars)"
    return out


def _msg_tokens(msg: Any) -> int:
    text = getattr(msg, "text", "") or ""
    total = estimate_tokens(text)
    trc = getattr(msg, "tool_result_content", None)
    if trc is not None:
        blob = trc if isinstance(trc, str) else json.dumps(trc, ensure_ascii=False)
        total += estimate_tokens(blob)
    return total


def fit_messages(msgs: list, budget_tokens: int, *, keep_last_n: int = 1) -> list:
    """从最新往回累加 token，超预算丢更早整条；纳入但超大的老 tool_result
    （非最近 keep_last_n 条）调 compact_tool_result 降级。

    最近 keep_last_n 条永远保留且永不压缩（本轮证据）。"""
    n = len(msgs)
    if n == 0:
        return []
    keep_from = max(0, n - keep_last_n)
    kept_reversed: list = []
    used = 0
    for i in range(n - 1, -1, -1):
        msg = msgs[i]
        protected = i >= keep_from
        if protected:
            kept_reversed.append(msg)
            used += _msg_tokens(msg)
            continue
        candidate = msg
        trc = getattr(msg, "tool_result_content", None)
        if trc is not None:
            import copy
            candidate = copy.copy(msg)
            candidate.tool_result_content = compact_tool_result(trc, max_chars=400)
        cost = _msg_tokens(candidate)
        if used + cost > budget_tokens:
            break
        kept_reversed.append(candidate)
        used += cost
    kept_reversed.reverse()
    return kept_reversed
