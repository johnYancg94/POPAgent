"""Compact, provider-neutral checkpoints for interrupted agent turns."""

from __future__ import annotations

import json
from typing import Any


_TEXT_LIMIT = 800
_ACTION_LIMIT = 12


def _bounded(value: Any, limit: int = _TEXT_LIMIT) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def build_resume_context(
    *,
    original_prompt: str,
    trace: dict | None,
    error_kind: str,
    error_message: str,
) -> dict:
    completed_actions = []
    failed_step = {}
    for iteration in (trace or {}).get("iterations", []) or []:
        for call in iteration.get("tool_calls", []) or []:
            action = {
                "name": _bounded(call.get("name"), 120),
                "arguments": _bounded(call.get("arguments_preview")),
                "result": _bounded(call.get("result_preview")),
            }
            if call.get("ok", True):
                completed_actions.append(action)
            else:
                failed_step = {
                    **action,
                    "error_kind": _bounded(call.get("error_kind"), 120),
                }

    return {
        "version": 1,
        "original_prompt": _bounded(original_prompt, 2000),
        "completed_actions": completed_actions[-_ACTION_LIMIT:],
        "failed_step": failed_step,
        "error_kind": _bounded(error_kind, 160),
        "error_message": _bounded(error_message),
        "remaining_goal": (
            "Continue the original task from the verified progress. "
            "Do not repeat completed actions unless validation shows they failed."
        ),
    }


def render_resume_context(checkpoint: dict) -> str:
    payload = {
        "original_prompt": checkpoint.get("original_prompt", ""),
        "completed_actions": checkpoint.get("completed_actions", []),
        "failed_step": checkpoint.get("failed_step", {}),
        "error_kind": checkpoint.get("error_kind", ""),
        "error_message": checkpoint.get("error_message", ""),
        "remaining_goal": checkpoint.get("remaining_goal", ""),
    }
    return (
        "A previous agent turn was interrupted. Resume from this checkpoint. "
        "Use the new user message to decide whether to continue, revise, or "
        "abandon it. Do not repeat completed actions unless validation shows "
        "they failed.\n"
        + json.dumps(payload, ensure_ascii=False, sort_keys=True)
    )


def parse_resume_context(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) and data.get("version") == 1 else {}
