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
