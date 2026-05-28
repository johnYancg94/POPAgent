"""
Process-level skill registry.

Skills are keyed by (owner, name). Re-registering the same (owner, name)
overwrites the previous entry silently — safe for Blender hot-reloads.
"""

from __future__ import annotations
import json
import sys
import inspect
from typing import Callable


_registry: dict[tuple[str, str], dict] = {}
_disabled: set[tuple[str, str]] = set()
_permission_overrides: dict[tuple[str, str], str] = {}

_PERMISSION_LEVELS = {"never", "first", "always"}


def permission_key(owner: str, name: str) -> str:
    return f"{owner}::{name}"


def _split_permission_key(key: str) -> tuple[str, str] | None:
    if "::" not in key:
        return None
    owner, name = key.split("::", 1)
    if not owner or not name:
        return None
    return owner, name


def _normalized_permission_level(level: str | None) -> str | None:
    if level in _PERMISSION_LEVELS:
        return level
    return None


def _permission_overrides_from_prefs(prefs=None) -> dict[tuple[str, str], str]:
    if prefs is None:
        return {}
    raw = getattr(prefs, "skill_permission_overrides_json", "") or "{}"
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}

    overrides: dict[tuple[str, str], str] = {}
    for key, level in data.items():
        split = _split_permission_key(str(key))
        normalized = _normalized_permission_level(level)
        if split is not None and normalized is not None:
            overrides[split] = normalized
    return overrides


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


def set_permission_override(owner: str, name: str, level: str) -> None:
    normalized = _normalized_permission_level(level)
    if normalized is None:
        raise ValueError(f"Unsupported permission level: {level}")
    _permission_overrides[(owner, name)] = normalized


def clear_permission_overrides() -> None:
    _permission_overrides.clear()


def get_permission_level(skill: dict, prefs=None) -> str:
    owner = skill.get("owner", "unknown")
    name = skill.get("name", "")
    key = (owner, name)

    pref_override = _permission_overrides_from_prefs(prefs).get(key)
    if pref_override is not None:
        return pref_override

    runtime_override = _permission_overrides.get(key)
    if runtime_override is not None:
        return runtime_override

    meta = skill.get("metadata", {})
    return _normalized_permission_level(meta.get("requires_confirmation")) or "never"


def unregister_namespace(owner_prefix: str) -> None:
    """Remove all skills whose owner starts with owner_prefix."""
    to_remove = [k for k in _registry if k[0].startswith(owner_prefix)]
    for k in to_remove:
        del _registry[k]
        _disabled.discard(k)
        _permission_overrides.pop(k, None)


def clear_all() -> None:
    """Clear the entire registry (called on POPAgent unregister)."""
    _registry.clear()
    _disabled.clear()
    _permission_overrides.clear()


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
