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
