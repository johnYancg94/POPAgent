"""
Process-level skill registry.

Skills are keyed by (owner, name). Re-registering the same (owner, name)
overwrites the previous entry silently — safe for Blender hot-reloads.
"""

from __future__ import annotations
import sys
import inspect
from typing import Callable


_registry: dict[tuple[str, str], dict] = {}
_disabled: set[tuple[str, str]] = set()


def register_skill(skill: dict) -> None:
    """Register or overwrite a skill.

    Required keys: name, description, parameters (JSON Schema), owner, handler, metadata.
    """
    owner = skill.get("owner", "unknown")
    name = skill["name"]
    _registry[(owner, name)] = skill


def set_disabled(owner: str, name: str, disabled: bool) -> None:
    key = (owner, name)
    if disabled:
        _disabled.add(key)
    else:
        _disabled.discard(key)


def is_disabled(owner: str, name: str) -> bool:
    return (owner, name) in _disabled


def unregister_namespace(owner_prefix: str) -> None:
    """Remove all skills whose owner starts with owner_prefix."""
    to_remove = [k for k in _registry if k[0].startswith(owner_prefix)]
    for k in to_remove:
        del _registry[k]
        _disabled.discard(k)


def clear_all() -> None:
    """Clear the entire registry (called on POPAgent unregister)."""
    _registry.clear()
    _disabled.clear()


def get_skill(owner: str, name: str) -> dict | None:
    return _registry.get((owner, name))


def get_skill_by_name(name: str) -> dict | None:
    """Look up by skill name alone (scan all owners), skipping disabled entries."""
    for (o, n), skill in _registry.items():
        if n == name and (o, n) not in _disabled:
            return skill
    return None


def all_skills() -> list[dict]:
    """All enabled skills (disabled ones are hidden from agent dispatch)."""
    return [v for k, v in _registry.items() if k not in _disabled]


def all_skills_including_disabled() -> list[tuple[dict, bool]]:
    """For UI: every registered skill plus its disabled flag."""
    return [(v, k in _disabled) for k, v in _registry.items()]


def skills_by_owner(owner_prefix: str) -> list[dict]:
    return [
        v
        for (o, n), v in _registry.items()
        if o.startswith(owner_prefix) and (o, n) not in _disabled
    ]


def is_handler_valid(skill: dict) -> bool:
    """Check that the handler's module is still live in sys.modules."""
    handler: Callable = skill.get("handler")
    if handler is None:
        return False
    mod = inspect.getmodule(handler)
    if mod is None:
        return False
    mod_name = getattr(mod, "__name__", None)
    return mod_name in sys.modules and sys.modules[mod_name] is mod
