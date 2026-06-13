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


def _drop_incomplete_tool_groups(msgs: list) -> list:
    """Keep assistant tool calls and their results only as complete groups."""
    out: list = []
    index = 0
    while index < len(msgs):
        msg = msgs[index]
        tool_calls = getattr(msg, "tool_calls", None) or []
        if getattr(msg, "role", None) == "assistant" and tool_calls:
            results = []
            cursor = index + 1
            while (
                cursor < len(msgs)
                and getattr(msgs[cursor], "role", None) == "tool_result"
            ):
                results.append(msgs[cursor])
                cursor += 1

            call_ids = {getattr(call, "id", "") for call in tool_calls}
            result_ids = {
                getattr(result, "tool_result_id", "") for result in results
            }
            if call_ids and call_ids == result_ids:
                out.append(msg)
                out.extend(results)
            index = cursor
            continue

        if getattr(msg, "role", None) != "tool_result":
            out.append(msg)
        index += 1
    return out


def fit_messages(msgs: list, budget_tokens: int, *, keep_last_n: int = 1) -> list:
    """从最新往回累加 token，超预算丢更早整条；纳入但超大的老 tool_result
    （非最近 keep_last_n 条）调 compact_tool_result 降级。

    最近 keep_last_n 条永远保留且永不压缩（本轮证据）。
    另:msgs[0] 若 role=="user"（initial prompt）也受保护，永不丢弃——
    保证 wire 后首条合法（first message must be user），从源头避免
    孤 tool_result / 孤 assistant 触发的 400。

    裁剪后若发生过截断，会从窗口头部剥掉孤立的非 user 消息（cut 可能落在
    assistant(tool_calls) 与其 tool_result 之间，留下无配对的 tool_result，
    OpenAI/Claude 都会 400）。剥离止于受保护 head 或尾部，绝不清空。

    实现策略：head 与 tail 都是绝对不变量，先从 msgs 中扣除；中间段再走
    反序累加 + compact + break。这避免把 head 算进 budget 超限比较里被误剥。"""
    n = len(msgs)
    if n == 0:
        return []
    keep_from = max(0, n - keep_last_n)
    head_protected = (
        keep_from > 0  # tail 与 head 不重叠
        and getattr(msgs[0], "role", None) == "user"
    )

    # 1) 头部:若受保护且与 tail 不重叠,无条件保留(不计入 budget)。
    head_msg = msgs[0] if head_protected else None
    middle = msgs[1:keep_from] if head_protected else msgs[0:keep_from]
    tail_msgs = msgs[keep_from:n]

    # 2) 中间段反序累加,超 budget 丢更早整条,老 tool_result 走 compact。
    kept_middle_reversed: list = []
    used = 0
    truncated = False
    for i in range(len(middle) - 1, -1, -1):
        msg = middle[i]
        candidate = msg
        trc = getattr(msg, "tool_result_content", None)
        if trc is not None:
            import copy
            candidate = copy.copy(msg)
            candidate.tool_result_content = compact_tool_result(trc, max_chars=400)
        cost = _msg_tokens(candidate)
        if used + cost > budget_tokens:
            truncated = True
            break
        kept_middle_reversed.append(candidate)
        used += cost
    kept_middle_reversed.reverse()
    middle_kept = kept_middle_reversed

    # 3) 拼装:head + middle_kept + tail(head 与 tail 互斥,要么有 head 要么 tail 占满)
    if head_msg is not None:
        out = [head_msg] + middle_kept + list(tail_msgs)
    else:
        out = middle_kept + list(tail_msgs)

    if truncated:
        # head 受保护时其 role 必为 "user",此循环天然以 head 为止点;
        # 万一 head 未受保护,旧逻辑兜底:剥到 user 停手,剥不到则保住尾部
        # keep_last_n 条(绝不清空)。
        while len(out) > keep_last_n and out[0].role != "user":
            out.pop(0)
        out = _drop_incomplete_tool_groups(out)
    return out


def _is_orphan_tool_result_user(msg: dict) -> bool:
    """Anthropic wire:首条 user 若是 tool_result-only(无文本/无图片),
    则该 user 缺配对的 assistant(tool_use),属于孤儿。"""
    if msg.get("role") != "user":
        return False
    content = msg.get("content")
    if not isinstance(content, list):
        return False
    if not content:
        return False
    return all(
        isinstance(block, dict) and block.get("type") == "tool_result"
        for block in content
    )


def _is_plain_user(msg: dict) -> bool:
    """Anthropic wire:合法 user 头需含文本/图片/或 tool_result 配对的内容。"""
    if msg.get("role") != "user":
        return False
    content = msg.get("content")
    if isinstance(content, str):
        return True
    if isinstance(content, list) and content:
        # 至少有一块不是纯 tool_result(避免孤儿);混了文本/图片/或含 tool_result
        # 但有其它内容(配对中的合规 user)都判为合法。
        has_non_tool_result = any(
            not (isinstance(b, dict) and b.get("type") == "tool_result")
            for b in content
        )
        if has_non_tool_result:
            return True
        # 全是 tool_result 的 list 仍视为 orphan(无配对 tool_use)
        return False
    return False


def sanitize_wire_head_anthropic(messages: list) -> list:
    """Anthropic wire 出口规整:剥掉开头不合法的消息,直到首条是合法 plain user。
    拒绝形态:首条 assistant / 首条孤 tool_result user。返回新 list,不 mutate 入参。"""
    out: list = []
    started = False
    for msg in messages:
        if not started:
            if msg.get("role") == "user" and not _is_orphan_tool_result_user(msg):
                started = True
                out.append(msg)
            elif _is_plain_user(msg):
                started = True
                out.append(msg)
            # 其它(assistant / orphan tool_result user)一律丢弃
            continue
        out.append(msg)
    return out


def sanitize_wire_head_openai(messages: list) -> list:
    """OpenAI wire 出口规整:system 之后的首条不能是 role=="tool" 或 assistant。
    期望:首条是 user(tool 必须跟在 assistant(tool_calls) 之后)。
    返回新 list,不 mutate 入参。"""
    out: list = []
    seen_non_system = False
    for msg in messages:
        if msg.get("role") == "system":
            out.append(msg)
            continue
        if not seen_non_system:
            if msg.get("role") == "user":
                seen_non_system = True
                out.append(msg)
            # 开头 tool / assistant 全部丢弃,直到遇到 user
            continue
        out.append(msg)
    return out
