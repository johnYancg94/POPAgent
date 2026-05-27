"""
Reverse-pull: when POPAgent registers AFTER a sibling addon that ships an
`agent_skills` package, that sibling's `agent_skills.register()` was a no-op
(POPAgent wasn't importable yet). Scan sys.modules for already-loaded
`<addon>.agent_skills` packages and invoke their register() once.

Safe to call multiple times — skill_registry.register_skill overwrites on
duplicate (owner, name), so re-registration is idempotent.
"""

from __future__ import annotations
import sys


def pull_already_loaded_agent_skills() -> list[str]:
    """Find loaded `*.agent_skills` packages and call their register().

    Returns the list of fully-qualified module names that were pulled.
    """
    pulled: list[str] = []
    # Snapshot keys: we don't mutate sys.modules but the registered handlers may.
    for mod_name in list(sys.modules.keys()):
        if not mod_name.endswith(".agent_skills"):
            continue
        # Skip POPAgent's own agent_core internals (no such thing exists, but
        # be defensive in case any future addon is named "agent_skills" directly).
        parent = mod_name.rsplit(".", 1)[0]
        if parent == "POPAgent":
            continue

        mod = sys.modules.get(mod_name)
        if mod is None:
            continue
        register_fn = getattr(mod, "register", None)
        if not callable(register_fn):
            continue
        try:
            register_fn()
            pulled.append(mod_name)
        except Exception as exc:
            print(f"[reverse_pull] {mod_name}.register() failed: {exc}")
    return pulled
