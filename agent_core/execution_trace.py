"""Execution trace helpers for POPAgent agent turns."""

from __future__ import annotations

import json
from typing import Any


TRACE_VERSION = 2
_PREVIEW_LIMIT = 220


def create_trace() -> dict:
    return {
        "version": TRACE_VERSION,
        "iterations": [],
        "summary": {
            "tool_count": 0,
            "error_count": 0,
            "aborted": False,
            "abort_reason": "",
        },
    }


def record_iteration(
    trace: dict,
    *,
    index: int,
    stream: bool,
    latency_ms: float,
    status_code: int,
    finish_reason: str,
    text: str = "",
    reasoning_content: str = "",
) -> dict:
    iteration = {
        "index": int(index),
        "stream": bool(stream),
        "latency_ms": max(0, int(latency_ms)),
        "status_code": int(status_code or 0),
        "finish_reason": finish_reason or "",
        "text_preview": preview_value(text),
        "reasoning_preview": preview_value(reasoning_content),
        "tool_calls": [],
    }
    trace.setdefault("iterations", []).append(iteration)
    return iteration


def record_tool_call(
    trace: dict,
    iteration: dict,
    *,
    name: str,
    arguments: dict,
    result: dict,
    duration_ms: float = 0,
) -> dict:
    ok = True
    if isinstance(result, dict):
        ok = bool(result.get("ok", True))
    error_kind = ""
    if isinstance(result, dict):
        error_kind = str(result.get("error_kind") or "")

    item = {
        "name": name,
        "ok": ok,
        "error_kind": error_kind,
        "duration_ms": max(0, int(duration_ms)),
        "arguments_preview": preview_value(arguments),
        "result_preview": preview_result(result),
    }
    if name.startswith("renderset.") and isinstance(result, dict):
        item["result"] = _bounded_renderset_result(result)
    iteration.setdefault("tool_calls", []).append(item)

    summary = trace.setdefault("summary", {})
    summary["tool_count"] = int(summary.get("tool_count", 0)) + 1
    if not ok:
        summary["error_count"] = int(summary.get("error_count", 0)) + 1
    return item


def _bounded_renderset_result(result: dict) -> dict:
    keep = (
        "status",
        "blocking_ambiguities",
        "warnings",
        "duplicate_contexts",
        "unmatched_contexts",
        "created",
        "updated",
        "migrated",
        "skipped",
        "failed",
        "validation_results",
        "saved",
        "render_started",
        "rolled_back",
    )
    out = {}
    for key in keep:
        if key not in result:
            continue
        value = result[key]
        if isinstance(value, list):
            out[key] = value[:20]
        else:
            out[key] = value
    return out


def record_abort(trace: dict, reason: str) -> None:
    summary = trace.setdefault("summary", {})
    summary["aborted"] = True
    if not summary.get("abort_reason"):
        summary["abort_reason"] = reason or ""


def parse_trace(raw: str | None) -> dict:
    if not raw:
        return create_trace()
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return create_trace()

    if isinstance(data, dict) and data.get("version") == TRACE_VERSION:
        return data
    if isinstance(data, list):
        errors = 0
        for item in data:
            result = item.get("result", {}) if isinstance(item, dict) else {}
            if isinstance(result, dict) and not result.get("ok", True):
                errors += 1
        return {
            "version": 1,
            "legacy_tool_calls": data,
            "iterations": [],
            "summary": {
                "tool_count": len(data),
                "error_count": errors,
                "aborted": False,
                "abort_reason": "",
            },
        }
    return create_trace()


def preview_value(value: Any, limit: int = _PREVIEW_LIMIT) -> str:
    if value is None:
        text = ""
    elif isinstance(value, str):
        text = " ".join(value.split())
    else:
        try:
            text = json.dumps(value, ensure_ascii=False, sort_keys=True)
        except TypeError:
            text = str(value)
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def preview_result(value: Any, limit: int = _PREVIEW_LIMIT) -> str:
    text = preview_value(value, limit)
    if not isinstance(value, dict) or value.get("ok", True):
        return text

    error = str(value.get("error") or "")
    tail = next(
        (line.strip() for line in reversed(error.splitlines()) if line.strip()),
        "",
    )
    if not tail or tail in text:
        return text
    suffix = f" | error_tail: {tail}"
    if len(suffix) >= limit:
        return suffix[-limit:]
    return text[: limit - len(suffix)] + suffix
