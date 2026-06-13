"""
Let the LLM introspect registered callable tools at runtime.

Read-only against the process-level callable-tool registry. No bpy dependency, so the
handler can run on the main thread cheaply.

Why this exists: without it, every callable tool's full JSON schema must be
packed into the request up front. The legacy `agent.list_skills` API lets the
model fetch a compact catalog and pull one tool's full schema on demand.
"""

from __future__ import annotations

from ..agent_core import skill_registry


def _skill_brief(skill: dict) -> dict:
    meta = skill.get("metadata", {})
    return {
        "name": skill.get("name", ""),
        "owner": skill.get("owner", "unknown"),
        "description": (skill.get("description", "") or "").strip(),
        "modifies_scene": bool(meta.get("modifies_scene")),
        "writes_files": bool(meta.get("writes_files")),
        "requires_confirmation": meta.get("requires_confirmation", "never"),
    }


def _skill_full(skill: dict) -> dict:
    full = _skill_brief(skill)
    full["parameters"] = skill.get("parameters", {"type": "object", "properties": {}})
    full["metadata"] = skill.get("metadata", {})
    return full


def _handler_list_skills(context=None, name: str = "", owner: str = "") -> dict:
    """List registered skills, or return one skill's full schema when name is given."""
    del context

    if name:
        skill = skill_registry.get_skill_by_name(name)
        if skill is None:
            return {
                "ok": False,
                "error_kind": "skill_not_found",
                "error": f"No skill registered: {name}",
            }
        return {"ok": True, "skill": _skill_full(skill)}

    skills = skill_registry.all_skills()
    if owner:
        skills = [s for s in skills if s.get("owner", "").startswith(owner)]

    briefs = sorted(
        (_skill_brief(s) for s in skills),
        key=lambda s: (s["owner"], s["name"]),
    )
    owners = sorted({b["owner"] for b in briefs})
    return {
        "ok": True,
        "count": len(briefs),
        "owners": owners,
        "skills": briefs,
    }


LIST_SKILLS = {
    "name": "agent.list_skills",
    "description": (
        "List the agent's currently available callable tools. This is the legacy "
        "function-tool registry, not the agentskills.io Agent Skill catalog. Without "
        "arguments, returns a compact catalog for every enabled callable tool. Pass "
        "'name' to fetch one tool's full parameter schema and metadata. "
        "Pass 'owner' to filter the catalog by owner prefix (e.g. 'poptools', 'builtin')."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Exact skill name to fetch full schema for, e.g. 'poptools.export_fbx'.",
            },
            "owner": {
                "type": "string",
                "description": "Owner prefix to filter the catalog, e.g. 'poptools' or 'builtin'.",
            },
        },
        "required": [],
    },
    "owner": "builtin.agent",
    "handler": _handler_list_skills,
    "metadata": {
        "modifies_scene": False,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": False,
        "requires_confirmation": "never",
        "requires_main_thread": False,
    },
}
