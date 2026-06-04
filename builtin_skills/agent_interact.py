"""agent.ask_human：遇歧义向用户问一个澄清问题，同轮拿到答案继续。"""
from __future__ import annotations

from ..agent_core.ask_human_dialog import ask_user_blocking


def _handler_ask_human(context=None, question: str = "", options=None) -> dict:
    del context
    if not question.strip():
        return {"ok": False, "error_kind": "invalid_arguments",
                "error": "question 不能为空。"}
    if options is not None and not isinstance(options, list):
        options = [str(options)]
    return ask_user_blocking(question, options)


ASK_HUMAN = {
    "name": "agent.ask_human",
    "description": (
        "Ask the user one concise clarifying question when the request is "
        "ambiguous and a wrong guess would be hard to undo. Provide 'question' "
        "and optionally 'options' (a short list of choices). The user's answer "
        "is returned as text; act on it in the same turn. Do NOT use this for "
        "confirmation of destructive actions — the host already gates those."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "question": {"type": "string",
                "description": "The single clarifying question to ask the user."},
            "options": {"type": "array", "items": {"type": "string"},
                "description": "Optional shortlist of suggested answers."},
        },
        "required": ["question"],
    },
    "owner": "builtin.agent",
    "handler": _handler_ask_human,
    "metadata": {
        "modifies_scene": False,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": False,
        "requires_confirmation": "never",
        "requires_main_thread": False,
        "awaits_user": True,
    },
}
