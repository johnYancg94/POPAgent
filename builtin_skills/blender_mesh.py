"""
Mesh health-check skill: the geometry-level counterpart to the node validators.

Extracts per-object mesh statistics with bmesh (non-manifold edges, loose verts/
edges, zero-area faces, n-gons, tri/quad counts, unapplied scale) and runs them
through the pure rules in agent_core.mesh_diagnostics. Read-only.

This is the pre-export self-check: a model can confirm geometry is export-safe
before calling poptools.export_*.
"""

from __future__ import annotations
import bpy
import bmesh

from ..agent_core.mesh_diagnostics import validate_mesh_snapshot

_ZERO_AREA_EPS = 1e-9
_FLATNESS_EPS = 1e-4


def _objects_for_scope(context, scope: str):
    if scope == "active":
        return [context.active_object] if context.active_object else []
    if scope == "selected":
        return list(context.selected_objects)
    return [o for o in bpy.data.objects if o.type == "MESH"]


def _has_unapplied_scale(obj) -> bool:
    return any(abs(s - 1.0) > 1e-4 for s in obj.scale)


def _mesh_stats(obj) -> dict:
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)

        tris = quads = ngons = zero_area = non_flat = 0
        for face in bm.faces:
            sides = len(face.verts)
            if sides == 3:
                tris += 1
            elif sides == 4:
                quads += 1
            elif sides > 4:
                ngons += 1
                if face.normal.length > 0:
                    n = face.normal.normalized()
                    center = face.calc_center_median()
                    for v in face.verts:
                        if abs((v.co - center).dot(n)) > _FLATNESS_EPS:
                            non_flat += 1
                            break
            if face.calc_area() < _ZERO_AREA_EPS:
                zero_area += 1

        non_manifold = sum(1 for e in bm.edges if not e.is_manifold)
        loose_edges = sum(1 for e in bm.edges if len(e.link_faces) == 0)
        loose_verts = sum(
            1 for v in bm.verts if len(v.link_faces) == 0 and len(v.link_edges) == 0
        )

        return {
            "name": obj.name,
            "type": obj.type,
            "verts": len(bm.verts),
            "edges": len(bm.edges),
            "faces": len(bm.faces),
            "tris": tris,
            "quads": quads,
            "ngons": ngons,
            "non_manifold_edges": non_manifold,
            "loose_verts": loose_verts,
            "loose_edges": loose_edges,
            "zero_area_faces": zero_area,
            "non_flat_ngons": non_flat,
            "has_unapplied_scale": _has_unapplied_scale(obj),
            "scale": [round(s, 4) for s in obj.scale],
        }
    finally:
        bm.free()


def _handler_health_check(context=None, scope: str = "active") -> dict:
    if context is None:
        context = bpy.context

    results = []
    for obj in _objects_for_scope(context, scope):
        if obj is None or obj.type != "MESH":
            continue
        stats = _mesh_stats(obj)
        stats["validation"] = validate_mesh_snapshot(stats)
        results.append(stats)

    if not results:
        return {
            "ok": True,
            "scope": scope,
            "mesh_count": 0,
            "meshes": [],
            "message": "No mesh objects found in scope.",
        }

    all_ok = all(m["validation"]["ok"] for m in results)
    total_errors = sum(m["validation"]["error_count"] for m in results)
    return {
        "ok": True,
        "scope": scope,
        "mesh_count": len(results),
        "all_export_safe": all_ok,
        "total_errors": total_errors,
        "meshes": results,
    }


HEALTH_CHECK = {
    "name": "blender.mesh.health_check",
    "description": (
        "Inspect mesh geometry health for the active, selected, or all mesh objects. "
        "Reports non-manifold edges, loose verts/edges, zero-area faces, n-gons, "
        "tri/quad counts, and unapplied scale — the common issues that break exports "
        "or bakes. Run this before exporting to confirm models are clean."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "scope": {
                "type": "string",
                "enum": ["active", "selected", "all"],
                "description": "Which mesh objects to inspect.",
            },
        },
        "required": [],
    },
    "owner": "builtin.mesh",
    "handler": _handler_health_check,
    "metadata": {
        "modifies_scene": False,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": False,
        "requires_confirmation": "never",
    },
}
