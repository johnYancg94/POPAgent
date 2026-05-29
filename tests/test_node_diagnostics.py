"""Pure Python tests for Blender node tree diagnostics helpers."""

from pathlib import Path
import importlib.util
import sys


ROOT = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location(
    "node_diagnostics", ROOT / "agent_core" / "node_diagnostics.py"
)
node_diagnostics = importlib.util.module_from_spec(spec)
sys.modules["node_diagnostics"] = node_diagnostics
spec.loader.exec_module(node_diagnostics)


def test_validate_material_requires_principled_shader():
    report = node_diagnostics.validate_material_snapshot({
        "materials": [{
            "name": "Mat",
            "use_nodes": True,
            "nodes": [{"name": "Output", "type": "OUTPUT_MATERIAL"}],
            "links": [],
        }]
    })

    assert report["ok"] is False
    assert report["issue_count"] == 1
    assert report["issues"][0]["kind"] == "missing_principled_bsdf"


def test_validate_material_reports_missing_image_paths():
    report = node_diagnostics.validate_material_snapshot({
        "materials": [{
            "name": "Mat",
            "use_nodes": True,
            "nodes": [
                {"name": "BSDF", "type": "BSDF_PRINCIPLED"},
                {"name": "Image", "type": "TEX_IMAGE", "image": {"name": "BaseColor", "filepath": ""}},
            ],
            "links": [],
        }]
    })

    kinds = {issue["kind"] for issue in report["issues"]}
    assert report["ok"] is False
    assert "missing_image_filepath" in kinds


def test_analyze_material_identifies_pbr_channels_connected_to_principled():
    analysis = node_diagnostics.analyze_material_snapshot({
        "materials": [{
            "name": "PBR Mat",
            "use_nodes": True,
            "nodes": [
                {"name": "BSDF", "type": "BSDF_PRINCIPLED"},
                {"name": "Base Color", "type": "TEX_IMAGE", "image": {"name": "rock_basecolor", "filepath": "base.png"}},
                {"name": "Roughness", "type": "TEX_IMAGE", "image": {"name": "rock_roughness", "filepath": "rough.png"}},
                {"name": "Normal Map", "type": "NORMAL_MAP"},
                {"name": "Normal", "type": "TEX_IMAGE", "image": {"name": "rock_normal", "filepath": "normal.png"}},
            ],
            "links": [
                {"from_node": "Base Color", "from_socket": "Color", "to_node": "BSDF", "to_socket": "Base Color"},
                {"from_node": "Roughness", "from_socket": "Color", "to_node": "BSDF", "to_socket": "Roughness"},
                {"from_node": "Normal", "from_socket": "Color", "to_node": "Normal Map", "to_socket": "Color"},
                {"from_node": "Normal Map", "from_socket": "Normal", "to_node": "BSDF", "to_socket": "Normal"},
            ],
        }]
    })

    material = analysis["materials"][0]
    assert material["pbr_score"] == 3
    assert material["channels"]["base_color"]["connected"] is True
    assert material["channels"]["roughness"]["connected"] is True
    assert material["channels"]["normal"]["connected"] is True


def test_plan_pbr_texture_paths_keeps_supported_channels_only():
    plan = node_diagnostics.plan_pbr_texture_paths({
        "base_color": "base.png",
        "roughness": "rough.png",
        "normal": "",
        "unsupported": "ignored.png",
    })

    assert plan["ok"] is True
    assert plan["channels"] == {
        "base_color": "base.png",
        "roughness": "rough.png",
    }
    assert plan["ignored_channels"] == ["unsupported"]


def test_plan_pbr_texture_paths_accepts_common_channel_aliases():
    plan = node_diagnostics.plan_pbr_texture_paths({
        "albedo": "albedo.png",
        "metalness": "metal.png",
        "opacity": "alpha.png",
    })

    assert plan["ok"] is True
    assert plan["channels"] == {
        "base_color": "albedo.png",
        "metallic": "metal.png",
        "alpha": "alpha.png",
    }
    assert plan["aliases"] == {
        "albedo": "base_color",
        "metalness": "metallic",
        "opacity": "alpha",
    }


def test_plan_pbr_texture_paths_reports_missing_paths():
    plan = node_diagnostics.plan_pbr_texture_paths({
        "base_color": "",
        "roughness": "rough.png",
    })

    assert plan["ok"] is True
    assert plan["missing_channels"] == ["base_color"]


def test_validate_material_reports_texture_that_looks_unconnected_to_expected_channel():
    report = node_diagnostics.validate_material_snapshot({
        "materials": [{
            "name": "PBR Mat",
            "use_nodes": True,
            "nodes": [
                {"name": "BSDF", "type": "BSDF_PRINCIPLED"},
                {"name": "Base Color", "type": "TEX_IMAGE", "image": {"name": "wood_basecolor", "filepath": "wood_basecolor.png"}},
            ],
            "links": [],
        }]
    })

    kinds = {issue["kind"] for issue in report["issues"]}
    assert "unconnected_pbr_texture" in kinds


def test_validate_material_requires_principled_connected_to_surface_output():
    report = node_diagnostics.validate_material_snapshot({
        "materials": [{
            "name": "Mat",
            "use_nodes": True,
            "nodes": [
                {"name": "BSDF", "type": "BSDF_PRINCIPLED"},
                {"name": "Output", "type": "OUTPUT_MATERIAL"},
            ],
            "links": [],
        }]
    })

    kinds = {issue["kind"] for issue in report["issues"]}
    assert "missing_surface_output_link" in kinds


def test_validate_material_reports_data_texture_using_color_space():
    report = node_diagnostics.validate_material_snapshot({
        "materials": [{
            "name": "Mat",
            "use_nodes": True,
            "nodes": [
                {"name": "BSDF", "type": "BSDF_PRINCIPLED"},
                {
                    "name": "Roughness",
                    "type": "TEX_IMAGE",
                    "image": {
                        "name": "mat_roughness",
                        "filepath": "roughness.png",
                        "color_space": "sRGB",
                    },
                },
            ],
            "links": [
                {"from_node": "Roughness", "from_socket": "Color", "to_node": "BSDF", "to_socket": "Roughness"},
            ],
        }]
    })

    kinds = {issue["kind"] for issue in report["issues"]}
    assert "wrong_texture_color_space" in kinds


def test_validate_geometry_nodes_requires_group_input_output():
    report = node_diagnostics.validate_geometry_nodes_snapshot({
        "objects": [{
            "name": "Cube",
            "modifiers": [{
                "name": "GeometryNodes",
                "type": "NODES",
                "node_group": {
                    "name": "GN",
                    "nodes": [{"name": "Mesh Cube", "type": "MESH_CUBE"}],
                    "links": [],
                },
            }],
        }]
    })

    kinds = {issue["kind"] for issue in report["issues"]}
    assert report["ok"] is False
    assert "missing_group_input" in kinds
    assert "missing_group_output" in kinds


def test_validate_geometry_nodes_reports_invalid_links():
    report = node_diagnostics.validate_geometry_nodes_snapshot({
        "objects": [{
            "name": "Cube",
            "modifiers": [{
                "name": "GeometryNodes",
                "type": "NODES",
                "node_group": {
                    "name": "GN",
                    "nodes": [
                        {"name": "Group Input", "type": "GROUP_INPUT"},
                        {"name": "Group Output", "type": "GROUP_OUTPUT"},
                    ],
                    "links": [{"from_node": "", "from_socket": "Geometry", "to_node": "Group Output", "to_socket": ""}],
                },
            }],
        }]
    })

    kinds = {issue["kind"] for issue in report["issues"]}
    assert report["ok"] is False
    assert "invalid_link" in kinds


def test_validate_geometry_nodes_requires_geometry_output_link():
    report = node_diagnostics.validate_geometry_nodes_snapshot({
        "objects": [{
            "name": "Cube",
            "modifiers": [{
                "name": "GeometryNodes",
                "type": "NODES",
                "node_group": {
                    "name": "GN",
                    "interface": [
                        {"name": "Geometry", "in_out": "INPUT", "socket_type": "NodeSocketGeometry"},
                        {"name": "Geometry", "in_out": "OUTPUT", "socket_type": "NodeSocketGeometry"},
                    ],
                    "nodes": [
                        {"name": "Group Input", "type": "GROUP_INPUT"},
                        {"name": "Group Output", "type": "GROUP_OUTPUT"},
                    ],
                    "links": [],
                },
            }],
        }]
    })

    kinds = {issue["kind"] for issue in report["issues"]}
    assert "missing_geometry_output_link" in kinds


def test_analyze_geometry_nodes_summarizes_interface_sockets():
    analysis = node_diagnostics.analyze_geometry_nodes_snapshot({
        "objects": [{
            "name": "Cube",
            "modifiers": [{
                "name": "GeometryNodes",
                "type": "NODES",
                "node_group": {
                    "name": "GN",
                    "interface": [
                        {"name": "Geometry", "in_out": "INPUT", "socket_type": "NodeSocketGeometry"},
                        {"name": "Density", "in_out": "INPUT", "socket_type": "NodeSocketFloat"},
                        {"name": "Geometry", "in_out": "OUTPUT", "socket_type": "NodeSocketGeometry"},
                    ],
                    "nodes": [
                        {"name": "Group Input", "type": "GROUP_INPUT"},
                        {"name": "Group Output", "type": "GROUP_OUTPUT"},
                    ],
                    "links": [],
                },
            }],
        }]
    })

    group = analysis["objects"][0]["modifiers"][0]["node_group"]
    assert group["interface_summary"]["input_count"] == 2
    assert group["interface_summary"]["output_count"] == 1
    assert group["interface_summary"]["geometry_inputs"] == ["Geometry"]
    assert group["interface_summary"]["geometry_outputs"] == ["Geometry"]


def run():
    test_validate_material_requires_principled_shader()
    test_validate_material_reports_missing_image_paths()
    test_analyze_material_identifies_pbr_channels_connected_to_principled()
    test_plan_pbr_texture_paths_keeps_supported_channels_only()
    test_plan_pbr_texture_paths_accepts_common_channel_aliases()
    test_plan_pbr_texture_paths_reports_missing_paths()
    test_validate_material_reports_texture_that_looks_unconnected_to_expected_channel()
    test_validate_material_requires_principled_connected_to_surface_output()
    test_validate_material_reports_data_texture_using_color_space()
    test_validate_geometry_nodes_requires_group_input_output()
    test_validate_geometry_nodes_reports_invalid_links()
    test_validate_geometry_nodes_requires_geometry_output_link()
    test_analyze_geometry_nodes_summarizes_interface_sockets()
    print("test_node_diagnostics OK")
    return True


if __name__ == "__main__":
    run()
