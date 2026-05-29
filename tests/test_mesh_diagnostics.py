"""Pure Python tests for mesh health diagnostics rules."""

from pathlib import Path
import importlib.util
import sys


ROOT = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location(
    "mesh_diagnostics", ROOT / "agent_core" / "mesh_diagnostics.py"
)
mesh_diagnostics = importlib.util.module_from_spec(spec)
sys.modules["mesh_diagnostics"] = mesh_diagnostics
spec.loader.exec_module(mesh_diagnostics)

validate_mesh_snapshot = mesh_diagnostics.validate_mesh_snapshot


def _clean_stats(**overrides):
    base = {
        "name": "Mesh",
        "verts": 8, "edges": 12, "faces": 6,
        "tris": 0, "quads": 6, "ngons": 0,
        "non_manifold_edges": 0,
        "loose_verts": 0, "loose_edges": 0,
        "zero_area_faces": 0, "non_flat_ngons": 0,
        "has_unapplied_scale": False, "scale": [1, 1, 1],
    }
    base.update(overrides)
    return base


def test_clean_mesh_passes():
    report = validate_mesh_snapshot(_clean_stats())
    assert report["ok"] is True
    assert report["issue_count"] == 0
    assert report["error_count"] == 0


def test_non_manifold_is_an_error():
    report = validate_mesh_snapshot(_clean_stats(non_manifold_edges=3))
    assert report["ok"] is False
    assert report["error_count"] == 1
    assert report["issues"][0]["kind"] == "non_manifold"
    assert report["issues"][0]["severity"] == "error"


def test_zero_area_faces_is_an_error():
    report = validate_mesh_snapshot(_clean_stats(zero_area_faces=2))
    kinds = {i["kind"] for i in report["issues"]}
    assert "zero_area_faces" in kinds
    assert report["error_count"] == 1


def test_loose_geometry_is_warning_not_error():
    report = validate_mesh_snapshot(_clean_stats(loose_verts=5, loose_edges=1))
    assert report["ok"] is True  # warnings don't fail export-readiness
    assert report["error_count"] == 0
    kinds = {i["kind"] for i in report["issues"]}
    assert "loose_verts" in kinds
    assert "loose_edges" in kinds


def test_ngons_and_unapplied_scale_are_warnings():
    report = validate_mesh_snapshot(
        _clean_stats(ngons=2, non_flat_ngons=1, has_unapplied_scale=True, scale=[2, 1, 1])
    )
    kinds = {i["kind"] for i in report["issues"]}
    assert kinds == {"ngons", "non_flat_ngons", "unapplied_scale"}
    assert report["ok"] is True
    assert report["error_count"] == 0


def run():
    test_clean_mesh_passes()
    test_non_manifold_is_an_error()
    test_zero_area_faces_is_an_error()
    test_loose_geometry_is_warning_not_error()
    test_ngons_and_unapplied_scale_are_warnings()
    print("test_mesh_diagnostics OK")
    return True


if __name__ == "__main__":
    run()
