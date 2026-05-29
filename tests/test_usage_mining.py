"""Pure Python tests for the JSONL usage *consumer* (no bpy).

Mirrors test_usage_log.py's importlib loading so it runs off the main thread.
"""

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location(
    "usage_mining", ROOT / "agent_core" / "usage_mining.py"
)
mining = importlib.util.module_from_spec(spec)
sys.modules["usage_mining"] = mining
spec.loader.exec_module(mining)


def _ep(episode_id, *, prompt="p", tools=(), signals=None, ts="2026-05-29T10:00:00"):
    sig = {
        "tool_count": len(tools),
        "error_count": sum(1 for t in tools if not t.get("ok", True)),
        "aborted": False,
        "abort_reason": "",
        "any_denied": any(t.get("error_kind") == "user_denied" for t in tools),
        "no_skill_matched": any(
            t.get("error_kind") == "skill_not_found" for t in tools
        ),
    }
    if signals:
        sig.update(signals)
    return {
        "episode_id": episode_id,
        "ts": ts,
        "request": {"prompt_preview": prompt},
        "tools": list(tools),
        "signals": sig,
    }


def _tool(name, *, ok=True, error_kind="", owner="builtin", confirm_level="never"):
    return {
        "name": name,
        "ok": ok,
        "error_kind": error_kind,
        "owner": owner,
        "confirm_level": confirm_level,
    }


def _write_jsonl(path, episodes):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for ep in episodes:
            fh.write(mining.json.dumps(ep, ensure_ascii=False) + "\n")


# ---- read_episodes ----------------------------------------------------------

def test_read_missing_dir_returns_empty(tmp_path):
    assert mining.read_episodes(tmp_path / "nope") == []


def test_read_merges_users_and_days_sorted_by_ts(tmp_path):
    _write_jsonl(tmp_path / "u1" / "2026-05-29.jsonl",
                 [_ep("b", ts="2026-05-29T12:00:00")])
    _write_jsonl(tmp_path / "u2" / "2026-05-28.jsonl",
                 [_ep("a", ts="2026-05-28T09:00:00")])
    eps = mining.read_episodes(tmp_path)
    assert [e["episode_id"] for e in eps] == ["a", "b"]


def test_read_skips_blank_and_malformed_lines(tmp_path):
    f = tmp_path / "u1" / "2026-05-29.jsonl"
    f.parent.mkdir(parents=True)
    f.write_text(
        mining.json.dumps(_ep("ok1")) + "\n"
        "\n"
        "{not valid json\n"
        + mining.json.dumps(_ep("ok2")) + "\n",
        encoding="utf-8",
    )
    eps = mining.read_episodes(tmp_path)
    assert {e["episode_id"] for e in eps} == {"ok1", "ok2"}


def test_read_user_and_day_filters(tmp_path):
    _write_jsonl(tmp_path / "u1" / "2026-05-29.jsonl", [_ep("a")])
    _write_jsonl(tmp_path / "u2" / "2026-05-29.jsonl", [_ep("b")])
    _write_jsonl(tmp_path / "u1" / "2026-05-30.jsonl", [_ep("c")])
    only_u1 = mining.read_episodes(tmp_path, user_ids=["u1"])
    assert {e["episode_id"] for e in only_u1} == {"a", "c"}
    only_day = mining.read_episodes(tmp_path, days=["2026-05-29"])
    assert {e["episode_id"] for e in only_day} == {"a", "b"}


# ---- aggregate --------------------------------------------------------------

def test_aggregate_counts_per_skill_and_errors():
    eps = [
        _ep("e1", tools=[_tool("export.fbx"), _tool("export.fbx", ok=False,
                                                     error_kind="exec_error")]),
        _ep("e2", tools=[_tool("export.fbx", ok=False, error_kind="exec_error")]),
    ]
    rep = mining.aggregate(eps)
    fbx = rep["per_skill"]["export.fbx"]
    assert fbx["calls"] == 3
    assert fbx["errors"] == 2
    assert fbx["error_kinds"] == {"exec_error": 2}
    assert rep["tool_call_count"] == 3
    assert rep["totals"]["error_count"] == 2


def test_aggregate_collects_no_skill_matched_prompts():
    eps = [
        _ep("g1", prompt="bake lightmaps",
            tools=[_tool("ghost", ok=False, error_kind="skill_not_found")]),
        _ep("g2", prompt="rig this character",
            tools=[_tool("ghost", ok=False, error_kind="skill_not_found")]),
    ]
    rep = mining.aggregate(eps)
    assert rep["no_skill_matched"]["count"] == 2
    prompts = [p["prompt"] for p in rep["no_skill_matched"]["prompts"]]
    assert "bake lightmaps" in prompts and "rig this character" in prompts


def test_aggregate_counts_denied_and_keeps_fail_samples():
    eps = [
        _ep("d1", tools=[_tool("object.delete", ok=False,
                               error_kind="user_denied", confirm_level="always")]),
    ]
    rep = mining.aggregate(eps)
    d = rep["per_skill"]["object.delete"]
    assert d["denied"] == 1
    assert d["fail_samples"] == ["d1"]
    assert rep["totals"]["any_denied"] == 1


def test_aggregate_aborts_grouped_by_reason():
    eps = [
        _ep("a1", signals={"aborted": True, "abort_reason": "anti_loop"}),
        _ep("a2", signals={"aborted": True, "abort_reason": "anti_loop"}),
        _ep("a3", signals={"aborted": True, "abort_reason": "max_iters"}),
    ]
    rep = mining.aggregate(eps)
    assert rep["aborts"] == {"anti_loop": 2, "max_iters": 1}
    assert rep["totals"]["aborted"] == 3


def test_aggregate_never_used_only_with_known_skills():
    eps = [_ep("e1", tools=[_tool("export.fbx")])]
    plain = mining.aggregate(eps)
    assert "never_used" not in plain
    known = mining.aggregate(eps, known_skills=["export.fbx", "naming.rename"])
    assert known["never_used"] == ["naming.rename"]


def test_aggregate_fail_samples_capped():
    eps = [
        _ep(f"x{i}", tools=[_tool("s", ok=False, error_kind="exec_error")])
        for i in range(10)
    ]
    rep = mining.aggregate(eps)
    assert len(rep["per_skill"]["s"]["fail_samples"]) == mining._SAMPLE_LIMIT


# ---- format_report ----------------------------------------------------------

def test_format_report_surfaces_each_section():
    eps = [
        _ep("e1", prompt="bake lightmaps",
            tools=[_tool("ghost", ok=False, error_kind="skill_not_found")]),
        _ep("e2", tools=[_tool("export.fbx", ok=False, error_kind="exec_error")]),
        _ep("e3", tools=[_tool("object.delete", ok=False,
                               error_kind="user_denied", confirm_level="always")]),
        _ep("e4", signals={"aborted": True, "abort_reason": "anti_loop"}),
    ]
    rep = mining.aggregate(eps, known_skills=["export.fbx", "naming.rename"])
    text = mining.format_report(rep)
    assert "no_skill_matched" in text
    assert "bake lightmaps" in text
    assert "export.fbx" in text
    assert "object.delete" in text
    assert "anti_loop" in text
    assert "naming.rename" in text  # never used


def test_format_report_empty_is_safe():
    text = mining.format_report(mining.aggregate([]))
    assert "0 episodes" in text


# ---- export_and_archive ----------------------------------------------------

def _zipfile():
    return mining.zipfile


def test_export_writes_zip_with_report_and_raw_logs(tmp_path):
    logs = tmp_path / "logs"
    _write_jsonl(logs / "u1" / "2026-05-29.jsonl",
                 [_ep("e1", tools=[_tool("export.fbx", ok=False,
                                         error_kind="exec_error")])])
    dest = tmp_path / "out"
    res = mining.export_and_archive(logs, dest, label="xiao wang!",
                                    today="2026-05-29")
    assert res["skipped"] is False
    assert res["episode_count"] == 1 and res["archived_files"] == 1
    zp = mining.Path(res["zip_path"])
    assert zp.exists() and zp.name == "popagent_xiao_wang_2026-05-29.zip"
    with _zipfile().ZipFile(zp) as zf:
        names = zf.namelist()
    assert "report.txt" in names
    assert any(n.endswith("2026-05-29.jsonl") for n in names)


def test_export_empties_live_area_and_archives(tmp_path):
    logs = tmp_path / "logs"
    live = logs / "u1" / "2026-05-29.jsonl"
    _write_jsonl(live, [_ep("e1", tools=[_tool("s")])])
    mining.export_and_archive(logs, tmp_path / "out", today="2026-05-29")
    assert not live.exists()                      # live file moved out
    archived = list((logs / "_archive").rglob("*.jsonl"))
    assert len(archived) == 1                     # ...into _archive


def test_archived_logs_not_recounted_on_next_read(tmp_path):
    logs = tmp_path / "logs"
    _write_jsonl(logs / "u1" / "2026-05-29.jsonl", [_ep("e1", tools=[_tool("s")])])
    mining.export_and_archive(logs, tmp_path / "out", today="2026-05-29")
    # archive dir now holds the old log; a fresh read must ignore it
    assert mining.read_episodes(logs) == []


def test_second_export_is_incremental(tmp_path):
    logs = tmp_path / "logs"
    dest = tmp_path / "out"
    _write_jsonl(logs / "u1" / "2026-05-29.jsonl", [_ep("e1", tools=[_tool("s")])])
    first = mining.export_and_archive(logs, dest, today="2026-05-29")
    assert first["episode_count"] == 1
    # new week: only fresh data lands in the live area
    _write_jsonl(logs / "u1" / "2026-06-05.jsonl", [_ep("e2", tools=[_tool("s")])])
    second = mining.export_and_archive(logs, dest, today="2026-06-05")
    assert second["episode_count"] == 1           # not 2 -> incremental


def test_export_unique_name_on_collision(tmp_path):
    logs = tmp_path / "logs"
    dest = tmp_path / "out"
    _write_jsonl(logs / "u1" / "2026-05-29.jsonl", [_ep("e1", tools=[_tool("s")])])
    r1 = mining.export_and_archive(logs, dest, label="bob", today="2026-05-29")
    _write_jsonl(logs / "u1" / "2026-05-29.jsonl", [_ep("e2", tools=[_tool("s")])])
    r2 = mining.export_and_archive(logs, dest, label="bob", today="2026-05-29")
    assert r1["zip_path"] != r2["zip_path"]
    assert mining.Path(r2["zip_path"]).name == "popagent_bob_2026-05-29-2.zip"


def test_export_empty_logs_is_skipped(tmp_path):
    res = mining.export_and_archive(tmp_path / "nope", tmp_path / "out")
    assert res["skipped"] is True
    assert res["zip_path"] is None
