"""
Pure helpers for diagnosing mesh geometry health from a plain-dict snapshot.

No bpy/bmesh dependency — the bmesh extraction lives in builtin_skills/blender_mesh.py
and hands a stats dict here. Keeping the rules pure makes the export-readiness
thresholds unit-testable without Blender.

Snapshot shape (per object), as produced by the skill handler:
    {
      "name": str, "type": str,
      "verts": int, "edges": int, "faces": int,
      "tris": int, "quads": int, "ngons": int,
      "non_manifold_edges": int,
      "loose_verts": int,
      "loose_edges": int,
      "zero_area_faces": int,
      "non_flat_ngons": int,
      "has_unapplied_scale": bool,
      "scale": [x, y, z],
    }
"""

from __future__ import annotations

from typing import Any


def _issue(kind: str, message: str, severity: str = "warning", **context) -> dict:
    data = {"kind": kind, "message": message, "severity": severity}
    data.update({k: v for k, v in context.items() if v is not None})
    return data


def _report(issues: list[dict]) -> dict:
    errors = [i for i in issues if i.get("severity") == "error"]
    return {
        "ok": len(errors) == 0,
        "issue_count": len(issues),
        "error_count": len(errors),
        "issues": issues,
    }


def validate_mesh_snapshot(snapshot: dict[str, Any]) -> dict:
    """Apply export-readiness rules to one mesh stats dict."""
    issues: list[dict] = []
    name = snapshot.get("name", "<mesh>")

    if snapshot.get("non_manifold_edges", 0) > 0:
        issues.append(_issue(
            "non_manifold",
            f"Mesh '{name}' has {snapshot['non_manifold_edges']} non-manifold edge(s).",
            severity="error",
            count=snapshot["non_manifold_edges"],
        ))

    if snapshot.get("zero_area_faces", 0) > 0:
        issues.append(_issue(
            "zero_area_faces",
            f"Mesh '{name}' has {snapshot['zero_area_faces']} degenerate (zero-area) face(s).",
            severity="error",
            count=snapshot["zero_area_faces"],
        ))

    loose = snapshot.get("loose_verts", 0)
    if loose > 0:
        issues.append(_issue(
            "loose_verts",
            f"Mesh '{name}' has {loose} loose vertex/vertices not used by any face.",
            severity="warning",
            count=loose,
        ))

    if snapshot.get("loose_edges", 0) > 0:
        issues.append(_issue(
            "loose_edges",
            f"Mesh '{name}' has {snapshot['loose_edges']} wire/loose edge(s).",
            severity="warning",
            count=snapshot["loose_edges"],
        ))

    if snapshot.get("ngons", 0) > 0:
        issues.append(_issue(
            "ngons",
            f"Mesh '{name}' has {snapshot['ngons']} n-gon(s) (faces with >4 sides).",
            severity="warning",
            count=snapshot["ngons"],
        ))

    if snapshot.get("non_flat_ngons", 0) > 0:
        issues.append(_issue(
            "non_flat_ngons",
            f"Mesh '{name}' has {snapshot['non_flat_ngons']} non-planar n-gon(s) that may triangulate badly.",
            severity="warning",
            count=snapshot["non_flat_ngons"],
        ))

    if snapshot.get("has_unapplied_scale"):
        scale = snapshot.get("scale") or []
        issues.append(_issue(
            "unapplied_scale",
            f"Mesh '{name}' has a non-uniform/unapplied object scale {scale}; apply scale before export.",
            severity="warning",
            scale=scale,
        ))

    return _report(issues)
