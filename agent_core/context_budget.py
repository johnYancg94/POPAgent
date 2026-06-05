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
