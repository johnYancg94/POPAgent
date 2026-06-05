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

def _msg(role, text="", tool_result_content=None):
    return types.SimpleNamespace(
        role=role, text=text, images=[],
        tool_result_content=tool_result_content,
        tool_result_name="", tool_result_id="", tool_calls=[],
    )

def test_fit_keeps_recent_drops_oldest_when_over_budget():
    msgs = [_msg("user", "a" * 4000), _msg("assistant", "b" * 4000),
            _msg("user", "c" * 4000)]
    out = cb.fit_messages(msgs, budget_tokens=1100, keep_last_n=1)
    assert out[-1].text == "c" * 4000
    assert len(out) < len(msgs)

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
