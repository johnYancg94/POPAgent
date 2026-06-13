"""Read-only activation tool for agentskills.io skill folders."""

from __future__ import annotations

try:
    from ..agent_core import agent_skill_registry
except ImportError:
    from agent_core import agent_skill_registry


def _handler_activate_agent_skill(
    context=None,
    name: str = "",
    resource: str = "",
) -> dict:
    del context
    if not name.strip():
        return {
            "ok": False,
            "error_kind": "missing_name",
            "error": "Agent Skill name is required",
        }
    return agent_skill_registry.registry.activate(name.strip(), resource.strip())


ACTIVATE_AGENT_SKILL = {
    "name": "agent.activate_skill",
    "description": (
        "Activate an agentskills.io Agent Skill before following its workflow. "
        "Pass the exact catalog name to load its SKILL.md instructions, or pass "
        "a relative resource path to read one referenced text file or inspect a "
        "binary asset. Read-only; never executes bundled scripts."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Exact Agent Skill name from the system catalog.",
            },
            "resource": {
                "type": "string",
                "description": (
                    "Optional relative path under the Skill root, such as "
                    "'references/guide.md' or 'scripts/helper.py'."
                ),
            },
        },
        "required": ["name"],
    },
    "owner": "builtin.agent-skills",
    "handler": _handler_activate_agent_skill,
    "metadata": {
        "modifies_scene": False,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": False,
        "requires_confirmation": "never",
        "requires_main_thread": False,
    },
}
