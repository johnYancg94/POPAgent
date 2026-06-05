"""
Agent runtime introspection skill: lets the LLM fetch authoritative facts about
its own running configuration — active provider, active model, and the effective
context budget for this turn.

Why this exists: the system prompt never states which model the agent runs on.
Without a tool that reports it, the model invents an identity from training-data
priors (e.g. "I'm Claude, 200K") or reads the wrong preference field
(`anthropic_model` is a default-valued field present regardless of the active
provider, so reading it directly misidentifies the model). This skill is the
single correct source: it routes through the same helpers the request path uses
(`get_current_model`, `history_budget`) so what the model reports matches what
actually goes on the wire.

Read-only against addon preferences. No scene access.
"""

from __future__ import annotations

from ..agent_core import context_budget


def _resolve_prefs(context):
    """Return POPAgent addon preferences, or None if unavailable."""
    if context is not None:
        prefs = getattr(
            getattr(context, "preferences", None), "addons", None
        )
        if prefs is not None:
            for key in ("POPAgent",):
                try:
                    return prefs[key].preferences
                except Exception:
                    pass
    try:
        import bpy

        addons = bpy.context.preferences.addons
        for key in ("POPAgent",):
            try:
                return addons[key].preferences
            except Exception:
                pass
    except Exception:
        return None
    return None


def _handler_runtime_info(context=None) -> dict:
    """Report the agent's live provider/model/context configuration."""
    prefs = _resolve_prefs(context)
    if prefs is None:
        return {
            "ok": False,
            "error_kind": "prefs_unavailable",
            "error": "Could not read POPAgent addon preferences.",
        }

    from ..utils.usage_stats import get_current_model

    org = getattr(prefs, "llm_organization", "") or ""
    model = get_current_model(prefs) or ""
    one_m = bool(getattr(prefs, "agent_context_1m_enabled", False))
    configured_window = int(getattr(prefs, "agent_context_window", 256000))
    effective_window = 1_000_000 if one_m else configured_window
    history_budget = context_budget.history_budget(effective_window)

    return {
        "ok": True,
        "provider": org,
        "model": model,
        "context_1m_enabled": one_m,
        "configured_context_window": configured_window,
        "effective_context_window": effective_window,
        "history_token_budget": history_budget,
        "note": (
            "These are the live runtime values. 'model' is the active model for "
            "the selected provider; do not infer the model from other preference "
            "fields. 'effective_context_window' is the token ceiling actually "
            "used this turn (1,000,000 when context_1m_enabled, else the "
            "configured window). The real upper limit is whatever the named "
            "model supports."
        ),
    }


RUNTIME_INFO = {
    "name": "agent.runtime_info",
    "description": (
        "Report the agent's authoritative runtime configuration: the active LLM "
        "provider, the active model name, whether the 1M-context option is "
        "enabled, and the effective context-window/token budget for this turn. "
        "Call this whenever the user asks who you are, which model you run on, or "
        "how much context you support — answer from this result instead of "
        "guessing or reading preference fields directly."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
    },
    "owner": "builtin.agent",
    "handler": _handler_runtime_info,
    "metadata": {
        "modifies_scene": False,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": False,
        "requires_confirmation": "never",
        "requires_main_thread": False,
    },
}
