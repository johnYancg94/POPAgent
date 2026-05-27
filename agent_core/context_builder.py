"""
Lightweight scene context builder.

Produces a compact, ≤200-token text summary of the current Blender scene, intended
to be injected as a system-prompt prefix at the start of each agent turn so the LLM
has just enough situational awareness to pick the right skill.

All bpy reads go through run_on_main — this module is safe to call from worker
coroutines.

Hard guard: output length is capped (~800 chars ≈ ~200 tokens) to keep the prompt
cheap. If the scene is huge we elide low-signal fields first (collections), then
truncate.
"""

from __future__ import annotations
import asyncio

from .main_thread import run_on_main
from . import skill_registry


_CHAR_GUARD = 800
_MAX_COLLECTIONS = 6
_MAX_OWNERS = 6


def _collect_scene_snapshot() -> dict:
    """Run on the main thread: snapshot bpy state into plain Python types."""
    import bpy

    scene = bpy.context.scene
    obj = bpy.context.view_layer.objects.active if bpy.context.view_layer else None

    mode = "OBJECT"
    try:
        mode = bpy.context.mode
    except Exception:
        pass

    selected = []
    try:
        selected = list(bpy.context.selected_objects or [])
    except Exception:
        pass

    collections: list[str] = []
    try:
        if scene and scene.collection:
            collections = [c.name for c in scene.collection.children][:_MAX_COLLECTIONS]
    except Exception:
        pass

    active_info = None
    if obj is not None:
        active_info = {
            "name": obj.name,
            "type": obj.type,
        }

    return {
        "mode": mode,
        "scene_name": getattr(scene, "name", "?"),
        "active": active_info,
        "selected_count": len(selected),
        "selected_sample": [o.name for o in selected[:3]],
        "collections": collections,
        "frame": getattr(scene, "frame_current", 0) if scene else 0,
    }


def _format_snapshot(snap: dict, owners: list[str]) -> str:
    parts: list[str] = ["# Blender Context"]
    parts.append(f"scene={snap['scene_name']}  mode={snap['mode']}  frame={snap['frame']}")

    active = snap.get("active")
    if active:
        parts.append(f"active={active['name']} ({active['type']})")
    else:
        parts.append("active=(none)")

    sel = snap.get("selected_count", 0)
    if sel:
        sample = ", ".join(snap.get("selected_sample") or [])
        more = "" if sel <= 3 else f" +{sel - 3}"
        parts.append(f"selected={sel} [{sample}{more}]")
    else:
        parts.append("selected=0")

    colls = snap.get("collections") or []
    if colls:
        parts.append("collections=" + ", ".join(colls))

    if owners:
        parts.append("skill_owners=" + ", ".join(owners[:_MAX_OWNERS]))

    text = "\n".join(parts)
    if len(text) > _CHAR_GUARD:
        text = text[: _CHAR_GUARD - 3] + "..."
    return text


def _distinct_owners() -> list[str]:
    seen: list[str] = []
    for skill in skill_registry.all_skills():
        owner = skill.get("owner", "unknown")
        if owner not in seen:
            seen.append(owner)
    return seen


async def build_scene_summary() -> str:
    """Return a ≤200-token summary string. Safe to call from worker coroutines."""
    loop = asyncio.get_event_loop()
    future = run_on_main(_collect_scene_snapshot)
    snap = await loop.run_in_executor(None, lambda: future.result(timeout=5))
    owners = _distinct_owners()
    return _format_snapshot(snap, owners)


def build_scene_summary_sync() -> str:
    """Main-thread variant for tests / panels. Calls the snapshot directly."""
    snap = _collect_scene_snapshot()
    owners = _distinct_owners()
    return _format_snapshot(snap, owners)
