import importlib.util, pathlib
_ROOT = pathlib.Path(__file__).resolve().parents[1]

def _load(mod_name, rel_path):
    spec = importlib.util.spec_from_file_location(mod_name, _ROOT / rel_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

cb = _load("popagent_context_budget", "agent_core/context_budget.py")

def test_estimate_tokens_char_over_4():
    assert cb.estimate_tokens("") == 0
    assert cb.estimate_tokens("abcd") == 1
    assert cb.estimate_tokens("abcde") == 2

def test_history_budget_256k():
    assert cb.history_budget(256000) == 228000

def test_history_budget_1m():
    assert cb.history_budget(1_000_000) == 972000

def test_history_budget_floor():
    assert cb.history_budget(1000) == 4000

import json as _json

def test_compact_screenshot_elides_base64():
    payload = {"ok": True, "image_base64": "A" * 50000, "format": "png"}
    out = cb.compact_tool_result(payload, max_chars=200)
    assert out["image_base64"] == "<image elided>"
    assert out["ok"] is True
    assert out["format"] == "png"

def test_compact_long_json_truncates_but_keeps_status():
    payload = {"ok": False, "error_kind": "boom", "blob": "x" * 50000}
    out = cb.compact_tool_result(payload, max_chars=200)
    assert out["ok"] is False
    assert out["error_kind"] == "boom"
    assert "elided" in _json.dumps(out)

def test_compact_small_dict_untouched():
    payload = {"ok": True, "result": "small"}
    out = cb.compact_tool_result(payload, max_chars=200)
    assert out == payload

def test_compact_string_payload_truncated():
    out = cb.compact_tool_result("y" * 5000, max_chars=100)
    assert len(out) < 5000 and "elided" in out

import types

def _msg(role, text="", tool_result_content=None, tool_calls=None,
         tool_result_id=""):
    return types.SimpleNamespace(
        role=role, text=text, images=[],
        tool_result_content=tool_result_content,
        tool_result_name="", tool_result_id=tool_result_id,
        tool_calls=tool_calls or [],
    )

def test_fit_keeps_recent_drops_oldest_when_over_budget():
    msgs = [_msg("user", "a" * 4000), _msg("assistant", "b" * 4000),
            _msg("user", "c" * 4000)]
    out = cb.fit_messages(msgs, budget_tokens=1100, keep_last_n=1)
    assert out[-1].text == "c" * 4000
    # L1:head user 受保护(不计入 budget)被保留,tail 必保;
    # 中间 assistant "b"*4000 cost≈1000,正好塞进 budget=1100,故 len 不减。
    # 关键断言:head + tail 都在,中间按预算取舍。
    assert out[0].role == "user" and out[0].text == "a" * 4000
    assert len(out) == 3  # 全部存活(budget 容得下)

def test_fit_compacts_old_tool_result_but_not_recent():
    big = {"ok": True, "image_base64": "Z" * 40000, "format": "png"}
    msgs = [
        _msg("tool_result", tool_result_content=dict(big)),
        _msg("user", "recent"),
        _msg("tool_result", tool_result_content=dict(big)),
    ]
    out = cb.fit_messages(msgs, budget_tokens=10_000_000, keep_last_n=1)
    assert out[0].tool_result_content["image_base64"] == "<image elided>"
    assert out[-1].tool_result_content["image_base64"] == "Z" * 40000

def test_fit_never_empties_when_keep_last_n_set():
    msgs = [_msg("user", "x" * 100000)]
    out = cb.fit_messages(msgs, budget_tokens=1, keep_last_n=1)
    assert len(out) == 1

def test_fit_strips_leading_orphan_tool_result_after_cut():
    # A cut that trims the assistant(tool_calls) but keeps its tool_result
    # would leave the window starting with an orphaned tool_result, which
    # both OpenAI and Anthropic reject with HTTP 400. The trimmer must clean it.
    msgs = [
        _msg("assistant", "a" * 4000),                       # ~1000 tok (gets cut)
        _msg("tool_result", tool_result_content="d" * 1200), # survives -> orphan
        _msg("user", "c" * 40),                              # protected newest
    ]
    out = cb.fit_messages(msgs, budget_tokens=120, keep_last_n=1)
    assert out[0].role == "user"
    assert all(m.role != "tool_result" for m in out)

def test_fit_preserves_valid_group_when_user_heads_window():
    # When a kept user message precedes the assistant(tool_calls)+tool_result
    # group, the boundary is already clean and nothing extra should be stripped.
    msgs = [
        _msg("user", "o" * 8000),                       # oldest -> cut
        _msg("user", "k" * 40),                         # heads the kept window
        _msg("assistant", "a" * 40),
        _msg("tool_result", tool_result_content="res"),
        _msg("user", "u" * 40),                         # protected newest
    ]
    out = cb.fit_messages(msgs, budget_tokens=100, keep_last_n=1)
    # L1:msgs[0] 是 user,受 head 保护,无条件保留(不计入 budget)。
    # 故 head 是 "o"*8000(原 oldest user),这是 L1 防止 400 的关键修复——
    # 旧实现会丢 head,然后 head 变成 "k"*40。本测试的 head 期望已更新。
    assert out[0].role == "user" and out[0].text == "o" * 8000
    assert any(m.role == "tool_result" for m in out)
    assert any(m.role == "assistant" for m in out)

# ── L1 regression: protect initial user when budget squeezes it out ──

def test_fit_protects_initial_user_when_over_budget():
    # 复刻 notes/2026-06-06-... 里的退化场景:initial user 巨大,14 轮历史,
    # budget 极紧。L1 之前会留下孤 tool_result,L1 之后 head 必须是 user。
    msgs = [_msg("user", "X" * 100000)]
    for _ in range(14):
        msgs.append(_msg("assistant", "a"))
        msgs.append(_msg("tool_result", tool_result_content="r"))
    out = cb.fit_messages(msgs, budget_tokens=1, keep_last_n=1)
    assert len(out) >= 1
    assert out[0].role == "user"
    # initial user 文本完整保留(它从未被 compact,只是要进 kept)
    assert out[0].text == "X" * 100000

def test_fit_head_user_survives_with_gap():
    # head 受保护时,中间被掏空是允许的;只要 head 仍为 user 即可。
    msgs = [
        _msg("user", "head"),                              # protected head
        _msg("assistant", "big" * 10000),                  # cut
        _msg("tool_result", tool_result_content="r" * 10000),  # cut
        _msg("user", "tail"),                              # protected newest
    ]
    out = cb.fit_messages(msgs, budget_tokens=20, keep_last_n=1)
    assert out[0].role == "user" and out[0].text == "head"
    assert out[-1].role == "user" and out[-1].text == "tail"

def test_fit_drops_tool_result_when_its_assistant_was_cut():
    call = types.SimpleNamespace(id="call_1")
    msgs = [
        _msg("user", "head"),
        _msg("assistant", "X" * 4000, tool_calls=[call]),
        _msg("tool_result", tool_result_content="ok", tool_result_id="call_1"),
        _msg("user", "tail"),
    ]
    out = cb.fit_messages(msgs, budget_tokens=10, keep_last_n=1)
    assert [msg.role for msg in out] == ["user", "user"]

def test_fit_keeps_complete_multi_tool_group():
    calls = [
        types.SimpleNamespace(id="call_1"),
        types.SimpleNamespace(id="call_2"),
    ]
    msgs = [
        _msg("user", "head"),
        _msg("assistant", tool_calls=calls),
        _msg("tool_result", tool_result_content="one", tool_result_id="call_1"),
        _msg("tool_result", tool_result_content="two", tool_result_id="call_2"),
        _msg("user", "tail"),
    ]
    out = cb.fit_messages(msgs, budget_tokens=100, keep_last_n=1)
    assert [msg.role for msg in out] == [
        "user", "assistant", "tool_result", "tool_result", "user"
    ]

# ── L2 regression: sanitize_wire_head_* helpers ──

def test_sanitize_wire_head_anthropic_strips_orphan_tool_result():
    # 模拟 to_anthropic 输出的退化形态:首条是 user(tool_result-only)
    # 且后面只有 assistant(无合法 plain user)。helper 会把 orphan 剥掉,
    # 然后把紧跟的 assistant 也剥(同样不合法),最终返回空——由调用方处理。
    messages = [
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "X", "content": "r"}
        ]},
        {"role": "assistant", "content": [
            {"type": "text", "text": "hi"}
        ]},
    ]
    out = cb.sanitize_wire_head_anthropic(messages)
    # orphan tool_result user + 紧跟 assistant 都不合法,全部剥掉
    assert out == []

def test_sanitize_wire_head_anthropic_strips_leading_assistant():
    messages = [
        {"role": "assistant", "content": [{"type": "text", "text": "no"}]},
        {"role": "user", "content": "ok"},
    ]
    out = cb.sanitize_wire_head_anthropic(messages)
    assert out[0]["role"] == "user" and out[0]["content"] == "ok"
    assert len(out) == 1

def test_sanitize_wire_head_openai_skips_system():
    # OpenAI system 放最前,helper 必须保留 system,只规整其后。
    messages = [
        {"role": "system", "content": "you are helpful"},
        {"role": "tool", "tool_call_id": "x", "content": "orphan"},
        {"role": "user", "content": "hi"},
        {"role": "tool", "tool_call_id": "y", "content": "ok"},
    ]
    out = cb.sanitize_wire_head_openai(messages)
    assert out[0]["role"] == "system"
    # orphan tool 被剥,合法配对的 tool 保留
    assert [m["role"] for m in out] == ["system", "user", "tool"]

def test_sanitize_wire_head_noop_on_healthy_sequence():
    # 健康序列:Anthropic plain user 开头 / OpenAI system + user 开头,原样返回。
    healthy_anthropic = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": [{"type": "text", "text": "ok"}]},
    ]
    assert cb.sanitize_wire_head_anthropic(healthy_anthropic) == healthy_anthropic

    healthy_openai = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hi"},
    ]
    assert cb.sanitize_wire_head_openai(healthy_openai) == healthy_openai
