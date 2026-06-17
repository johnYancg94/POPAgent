"""Small helpers for answer-process UI events."""

from __future__ import annotations

import json


MAX_PROCESS_EVENTS = 80


def append_process_event_json(raw_json: str, message: str, icon: str = "INFO") -> str:
    if not message:
        return raw_json or ""
    events = parse_process_events(raw_json)
    events.append({"message": message, "icon": icon or "INFO"})
    if len(events) > MAX_PROCESS_EVENTS:
        events = events[-MAX_PROCESS_EVENTS:]
    return json.dumps(events, ensure_ascii=False)


def parse_process_events(raw_json: str | None) -> list[dict]:
    if not raw_json:
        return []
    try:
        data = json.loads(raw_json)
    except (TypeError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    return [
        item
        for item in data
        if isinstance(item, dict) and str(item.get("message") or "").strip()
    ]


def events_from_trace(trace: dict | None) -> list[dict]:
    if not isinstance(trace, dict):
        return []

    if trace.get("version") == 1:
        return [_event_from_tool_call(call) for call in trace.get("legacy_tool_calls", [])]

    events = []
    for iteration in trace.get("iterations", []) or []:
        index = int(iteration.get("index", 0) or 0)
        latency = int(iteration.get("latency_ms", 0) or 0)
        events.append(
            {
                "message": f"Iter {index} planned next step ({latency} ms)",
                "icon": "TIME",
            }
        )
        for call in iteration.get("tool_calls", []) or []:
            events.append(_event_from_tool_call(call))

    summary = trace.get("summary", {}) or {}
    if summary.get("aborted"):
        reason = str(summary.get("abort_reason") or "unknown")
        events.append({"message": f"Interrupted: {reason}", "icon": "ERROR"})
    return events


def process_summary(events: list[dict], trace: dict | None = None) -> str:
    if isinstance(trace, dict):
        summary = trace.get("summary", {}) or {}
        tool_count = int(summary.get("tool_count", 0) or 0)
        error_count = int(summary.get("error_count", 0) or 0)
        if tool_count or error_count:
            return f"Process ({tool_count} tools, {error_count} errors)"
    count = len(events)
    return f"Process ({count} steps)" if count else "Process"


def _event_from_tool_call(call: dict) -> dict:
    if not isinstance(call, dict):
        return {"message": "Finished: unknown tool", "icon": "CHECKMARK"}
    name = str(call.get("name") or "?")
    ok = bool(call.get("ok", True))
    duration = int(call.get("duration_ms", 0) or 0)
    prefix = "Finished" if ok else "Failed"
    suffix = f" [{call.get('error_kind')}]" if call.get("error_kind") else ""
    return {
        "message": f"{prefix}: {name} ({duration} ms){suffix}",
        "icon": "CHECKMARK" if ok else "ERROR",
    }
