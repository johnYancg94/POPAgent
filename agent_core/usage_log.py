"""Append-only JSONL usage sink for POPAgent agent turns.

This is a *side channel* to the in-memory execution_trace. The trace already
captures everything about a turn; this module reshapes one turn into a single
self-contained, aggregatable JSON line and appends it to disk, so multiple team
members' logs can be pooled and mined later (failure modes, denied skills,
unmatched requests, never-used skills).

Design constraints:
- stdlib only, NO bpy import — fully unit-testable off the main thread.
- metadata-only by default. Free-text args/results and the full prompt are
  opt-in (`include_args` / `include_results` / `include_prompt_full`), so
  client asset paths never leak unless the user explicitly turns it on.
- one line == one agent turn (episode). Stable, bounded, easy to aggregate.

The episode schema is versioned via SCHEMA_VERSION so old logs stay readable
as the agent evolves.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


SCHEMA_VERSION = 1
_PROMPT_PREVIEW_LIMIT = 80

# error_kind values produced by executor.run() (agent_core/executor.py).
_DENIED_KIND = "user_denied"
_NO_SKILL_KIND = "skill_not_found"


def new_user_id(seed: str | None = None) -> str:
    """Pseudonymous, stable-per-install id. Store the result in a pref and reuse.

    Not tied to the machine: a uuid4 stored in prefs is stable enough for
    per-person aggregation and leaks nothing about the host. `seed` exists only
    to make tests deterministic.
    """
    if seed is not None:
        import hashlib

        return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]
    return uuid.uuid4().hex[:12]


def _prompt_preview(prompt: str, limit: int = _PROMPT_PREVIEW_LIMIT) -> str:
    prompt = " ".join((prompt or "").split())
    if len(prompt) <= limit:
        return prompt
    return prompt[: limit - 3] + "..."


def _iter_tool_calls(trace: dict):
    """Yield every tool_call dict across all iterations, in order."""
    for iteration in trace.get("iterations", []) or []:
        for call in iteration.get("tool_calls", []) or []:
            yield call


def _flatten_tools(
    trace: dict,
    *,
    include_args: bool,
    include_results: bool,
    meta_lookup: Callable[[str], dict | None] | None,
) -> list[dict]:
    tools: list[dict] = []
    for call in _iter_tool_calls(trace):
        name = call.get("name", "")
        entry: dict[str, Any] = {
            "name": name,
            "ok": bool(call.get("ok", True)),
            "error_kind": call.get("error_kind", "") or "",
            "duration_ms": int(call.get("duration_ms", 0) or 0),
        }
        meta = meta_lookup(name) if meta_lookup else None
        if isinstance(meta, dict):
            entry["owner"] = meta.get("owner", "")
            entry["confirm_level"] = meta.get("confirm_level", "")
            for flag in (
                "writes_files",
                "modifies_scene",
                "undoable",
                "launches_external_process",
            ):
                if meta.get(flag):
                    entry[flag] = True
        if include_args:
            entry["args_preview"] = call.get("arguments_preview", "")
        if include_results:
            entry["result_preview"] = call.get("result_preview", "")
        tools.append(entry)
    return tools


def _extract_signals(trace: dict, tools: list[dict]) -> dict:
    summary = trace.get("summary", {}) or {}
    tool_count = summary.get("tool_count")
    if tool_count is None:
        tool_count = len(tools)
    error_count = summary.get("error_count")
    if error_count is None:
        error_count = sum(1 for t in tools if not t["ok"])

    kinds = {t["error_kind"] for t in tools}
    return {
        "tool_count": int(tool_count),
        "error_count": int(error_count),
        "aborted": bool(summary.get("aborted", False)),
        "abort_reason": summary.get("abort_reason", "") or "",
        "any_denied": _DENIED_KIND in kinds,
        "no_skill_matched": _NO_SKILL_KIND in kinds,
    }


def build_episode(
    *,
    trace: dict,
    user_id: str,
    env: dict,
    llm: dict,
    prompt: str,
    cost: dict,
    schema_version: int = SCHEMA_VERSION,
    include_args: bool = False,
    include_results: bool = False,
    include_prompt_full: bool = False,
    meta_lookup: Callable[[str], dict | None] | None = None,
    now: datetime | None = None,
    episode_id: str | None = None,
) -> dict:
    """Reshape one finished agent turn into a single aggregatable record."""
    ts = (now or datetime.now().astimezone()).isoformat(timespec="seconds")
    tools = _flatten_tools(
        trace,
        include_args=include_args,
        include_results=include_results,
        meta_lookup=meta_lookup,
    )
    request: dict[str, Any] = {"prompt_preview": _prompt_preview(prompt)}
    if include_prompt_full:
        request["prompt_full"] = prompt or ""

    return {
        "schema_version": int(schema_version),
        "episode_id": episode_id or uuid.uuid4().hex,
        "ts": ts,
        "user_id": user_id or "",
        "env": dict(env or {}),
        "llm": dict(llm or {}),
        "request": request,
        "tools": tools,
        "signals": _extract_signals(trace, tools),
        "cost": dict(cost or {}),
    }


def episode_to_line(episode: dict) -> str:
    return json.dumps(episode, ensure_ascii=False, sort_keys=True) + "\n"


def episode_log_path(log_dir: str | Path, user_id: str, day: str | None = None) -> Path:
    """`<log_dir>/<user_id>/<YYYY-MM-DD>.jsonl`. user_id+date never collides."""
    if not day:
        day = datetime.now().strftime("%Y-%m-%d")
    return Path(log_dir).expanduser() / (user_id or "unknown") / f"{day}.jsonl"


def append_episode(log_dir: str | Path, episode: dict) -> str:
    """Append one episode as a JSONL line. Returns the file path written.

    Day is taken from the episode's own ts so the filename matches the record.
    """
    user_id = episode.get("user_id", "") or "unknown"
    ts = episode.get("ts", "") or ""
    day = ts[:10] if len(ts) >= 10 else None
    path = episode_log_path(log_dir, user_id, day=day)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(episode_to_line(episode))
    return str(path)
