"""Pure Python tests for the JSONL usage sink (no bpy)."""

from datetime import datetime
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location(
    "usage_log", ROOT / "agent_core" / "usage_log.py"
)
usage_log = importlib.util.module_from_spec(spec)
sys.modules["usage_log"] = usage_log
spec.loader.exec_module(usage_log)


def _trace(*tool_calls, aborted=False, abort_reason=""):
    """Build a v2-shaped trace dict with the given tool_call dicts."""
    err = sum(1 for t in tool_calls if not t.get("ok", True))
    return {
        "version": 2,
        "iterations": [{"index": 0, "tool_calls": list(tool_calls)}],
        "summary": {
            "tool_count": len(tool_calls),
            "error_count": err,
            "aborted": aborted,
            "abort_reason": abort_reason,
        },
    }


def _call(name, ok=True, error_kind="", duration_ms=10,
          arguments_preview="A", result_preview="R"):
    return {
        "name": name,
        "ok": ok,
        "error_kind": error_kind,
        "duration_ms": duration_ms,
        "arguments_preview": arguments_preview,
        "result_preview": result_preview,
    }


_NOW = datetime(2026, 5, 29, 14, 3, 11)


def _episode(trace, **kw):
    base = dict(
        trace=trace,
        user_id="u1",
        env={"blender": "5.1"},
        llm={"org": "anthropic", "model": "x", "mode": "agent"},
        prompt="导出选中物体为fbx",
        cost={"total_tokens": 100},
        now=_NOW,
    )
    base.update(kw)
    return usage_log.build_episode(**base)


def test_basic_shape_and_metadata_only_by_default():
    ep = _episode(_trace(_call("blender.export.fbx")))
    assert ep["schema_version"] == usage_log.SCHEMA_VERSION
    assert ep["user_id"] == "u1"
    assert ep["ts"].startswith("2026-05-29T14:03:11")
    assert ep["request"]["prompt_preview"] == "导出选中物体为fbx"
    # opt-in fields absent by default
    assert "prompt_full" not in ep["request"]
    assert "args_preview" not in ep["tools"][0]
    assert "result_preview" not in ep["tools"][0]


def test_prompt_preview_truncates():
    ep = _episode(_trace(), prompt="x" * 200)
    assert len(ep["request"]["prompt_preview"]) == 80
    assert ep["request"]["prompt_preview"].endswith("...")


def test_include_flags_opt_in():
    ep = _episode(
        _trace(_call("s")),
        include_args=True,
        include_results=True,
        include_prompt_full=True,
    )
    assert ep["tools"][0]["args_preview"] == "A"
    assert ep["tools"][0]["result_preview"] == "R"
    assert ep["request"]["prompt_full"] == "导出选中物体为fbx"


def test_signal_no_skill_matched():
    ep = _episode(_trace(_call("ghost", ok=False, error_kind="skill_not_found")))
    assert ep["signals"]["no_skill_matched"] is True
    assert ep["signals"]["any_denied"] is False


def test_signal_any_denied():
    ep = _episode(_trace(_call("s", ok=False, error_kind="user_denied")))
    assert ep["signals"]["any_denied"] is True
    assert ep["signals"]["error_count"] == 1


def test_signal_abort_passthrough():
    ep = _episode(_trace(aborted=True, abort_reason="anti_loop"))
    assert ep["signals"]["aborted"] is True
    assert ep["signals"]["abort_reason"] == "anti_loop"


def test_meta_lookup_enriches_tools():
    def lookup(name):
        return {
            "owner": "poptools.export",
            "confirm_level": "first",
            "writes_files": True,
            "undoable": False,
        }

    ep = _episode(_trace(_call("blender.export.fbx")), meta_lookup=lookup)
    t = ep["tools"][0]
    assert t["owner"] == "poptools.export"
    assert t["confirm_level"] == "first"
    assert t["writes_files"] is True
    # falsy flags are omitted, not written as False
    assert "undoable" not in t


def test_multiple_iterations_flattened_in_order():
    trace = {
        "version": 2,
        "iterations": [
            {"index": 0, "tool_calls": [_call("a")]},
            {"index": 1, "tool_calls": [_call("b"), _call("c")]},
        ],
        "summary": {"tool_count": 3, "error_count": 0},
    }
    ep = _episode(trace)
    assert [t["name"] for t in ep["tools"]] == ["a", "b", "c"]
    assert ep["signals"]["tool_count"] == 3


def test_new_user_id_deterministic_with_seed():
    a = usage_log.new_user_id(seed="machine-abc")
    b = usage_log.new_user_id(seed="machine-abc")
    assert a == b and len(a) == 12
    assert usage_log.new_user_id(seed="other") != a


def test_append_roundtrip(tmp_path):
    ep = _episode(_trace(_call("s")))
    path = usage_log.append_episode(tmp_path, ep)
    # filename is <dir>/<user_id>/<day>.jsonl, day from ts
    assert path.endswith(str(Path("u1") / "2026-05-29.jsonl"))
    # second append on same day goes to same file (two lines)
    usage_log.append_episode(tmp_path, _episode(_trace()))
    lines = Path(path).read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    parsed = json.loads(lines[0])
    assert parsed["user_id"] == "u1"
    assert parsed["tools"][0]["name"] == "s"


def test_episode_to_line_is_single_json_line():
    line = usage_log.episode_to_line(_episode(_trace()))
    assert line.endswith("\n")
    assert "\n" not in line[:-1]
    json.loads(line)  # valid JSON


# --- feedback (thumbs up/down) ------------------------------------------

def test_apply_feedback_sets_and_clears():
    ep = _episode(_trace(), episode_id="e1")
    usage_log.apply_feedback(ep, "up", now=_NOW)
    assert ep["feedback"]["rating"] == "up"
    assert ep["feedback"]["ts"].startswith("2026-05-29T14:03:11")
    usage_log.apply_feedback(ep, "down", now=_NOW)
    assert ep["feedback"]["rating"] == "down"
    # empty / unknown rating clears the key entirely
    usage_log.apply_feedback(ep, "", now=_NOW)
    assert "feedback" not in ep
    usage_log.apply_feedback(ep, "garbage", now=_NOW)
    assert "feedback" not in ep


def test_rewrite_feedback_hits_only_matching_line(tmp_path):
    path = usage_log.append_episode(tmp_path, _episode(_trace(), episode_id="a"))
    usage_log.append_episode(tmp_path, _episode(_trace(), episode_id="b"))

    assert usage_log.rewrite_feedback(path, "b", "down", now=_NOW) is True
    lines = Path(path).read_text(encoding="utf-8").strip().splitlines()
    by_id = {json.loads(l)["episode_id"]: json.loads(l) for l in lines}
    assert by_id["b"]["feedback"]["rating"] == "down"
    assert "feedback" not in by_id["a"]  # untouched line stays clean


def test_rewrite_feedback_missing_id_returns_false(tmp_path):
    path = usage_log.append_episode(tmp_path, _episode(_trace(), episode_id="a"))
    assert usage_log.rewrite_feedback(path, "nope", "up") is False
    # nonexistent file path also returns False, no raise
    assert usage_log.rewrite_feedback(tmp_path / "missing.jsonl", "a", "up") is False


def test_rewrite_feedback_preserves_corrupt_lines(tmp_path):
    path = usage_log.append_episode(tmp_path, _episode(_trace(), episode_id="a"))
    with Path(path).open("a", encoding="utf-8") as fh:
        fh.write("{ this is not valid json\n")
    usage_log.append_episode(tmp_path, _episode(_trace(), episode_id="c"))

    assert usage_log.rewrite_feedback(path, "c", "up", now=_NOW) is True
    lines = Path(path).read_text(encoding="utf-8").strip().splitlines()
    assert "{ this is not valid json" in lines  # corrupt line kept verbatim
    # both real episodes still present and parseable
    ids = {json.loads(l)["episode_id"] for l in lines if _is_json(l)}
    assert ids == {"a", "c"}


def test_rewrite_feedback_keeps_unicode_unescaped(tmp_path):
    path = usage_log.append_episode(tmp_path, _episode(_trace(), episode_id="z"))
    usage_log.rewrite_feedback(path, "z", "up", now=_NOW)
    raw = Path(path).read_text(encoding="utf-8")
    assert "导出选中物体为fbx" in raw  # ensure_ascii=False convention upheld


def _is_json(line: str) -> bool:
    try:
        json.loads(line)
        return True
    except ValueError:
        return False
