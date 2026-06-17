"""Deterministic fallback answers for interrupted Agent turns."""

from __future__ import annotations

import json
from typing import Any


FORBIDDEN_RENDERSET_FALLBACK_TOOLS = {
    "dev.run_python",
    "blender.file.save",
    "blender.object.delete",
    "renderset.prepare",
    "renderset.audit",
}
REPORT_FIELDS = (
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
)


def iter_tool_calls(trace: dict) -> list[dict]:
    calls: list[dict] = []
    for iteration in trace.get("iterations", []) or []:
        calls.extend(iteration.get("tool_calls", []) or [])
    if trace.get("version") == 1:
        calls.extend(trace.get("legacy_tool_calls", []) or [])
    return calls


def fallback_answer_for_trace(
    trace: dict | None,
    *,
    error_kind: str,
    error_message: str = "",
) -> str | None:
    """Return a safe fallback answer from completed RenderSet inspect results."""
    if not isinstance(trace, dict):
        return None
    calls = iter_tool_calls(trace)
    names = [str(call.get("name") or "") for call in calls]
    if any(name in FORBIDDEN_RENDERSET_FALLBACK_TOOLS for name in names):
        return None

    inspect_call = next(
        (
            call for call in reversed(calls)
            if call.get("name") == "renderset.inspect" and call.get("ok", True)
        ),
        None,
    )
    if inspect_call is None:
        return None

    result = _extract_result(inspect_call)
    if not isinstance(result, dict):
        return None

    lines = [
        f"Agent final response was interrupted ({error_kind}).",
        "Using the completed native `renderset.inspect` result instead of guessing.",
    ]
    if error_message:
        lines.append(f"error: {_single_line(error_message)}")
    lines.append("")
    for field in REPORT_FIELDS:
        lines.append(f"{field}: {_format_value(result.get(field, _empty_for(field)))}")
    return "\n".join(lines)


def _extract_result(call: dict) -> dict | None:
    result = call.get("result")
    if isinstance(result, dict):
        return result
    preview = call.get("result_preview")
    if not isinstance(preview, str) or not preview.strip():
        return None
    try:
        parsed = json.loads(preview)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _empty_for(field: str) -> Any:
    if field in {"saved", "render_started"}:
        return False
    if field == "status":
        return "unknown"
    return []


def _format_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _single_line(value: str) -> str:
    return " ".join(str(value).split())
