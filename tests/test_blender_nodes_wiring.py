"""Static guards for Blender material and geometry node skills."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_builtin_node_skills_are_registered():
    text = (ROOT / "builtin_skills" / "__init__.py").read_text(encoding="utf-8")

    assert "INSPECT_MATERIAL_NODES" in text
    assert "VALIDATE_MATERIAL_NODES" in text
    assert "CONNECT_PBR_TEXTURES" in text
    assert "ADD_MATERIAL_NODE" in text
    assert "CONNECT_MATERIAL_NODES" in text
    assert "SET_MATERIAL_NODE_INPUT" in text
    assert "INSPECT_GEOMETRY_NODES" in text
    assert "VALIDATE_GEOMETRY_NODES" in text
    assert "ENSURE_BASIC_GEOMETRY_NODES" in text
    assert "ADD_GEOMETRY_NODE" in text
    assert "CONNECT_GEOMETRY_NODES" in text
    assert "SET_GEOMETRY_NODE_INPUT" in text
    assert "SEARCH_NODE_TYPES" in text


def test_node_skills_are_read_only_and_named_for_blender_domains():
    text = (ROOT / "builtin_skills" / "blender_nodes.py").read_text(encoding="utf-8")

    assert "blender.material.inspect_nodes" in text
    assert "blender.material.validate_nodes" in text
    assert "blender.material.connect_pbr_textures" in text
    assert "blender.material.add_node" in text
    assert "blender.material.connect_nodes" in text
    assert "blender.material.set_node_input" in text
    assert "blender.nodes.search_types" in text
    assert "blender.geometry_nodes.inspect" in text
    assert "blender.geometry_nodes.validate" in text
    assert "blender.geometry_nodes.ensure_basic_group" in text
    assert "blender.geometry_nodes.add_node" in text
    assert "blender.geometry_nodes.connect_nodes" in text
    assert "blender.geometry_nodes.set_node_input" in text
    assert '"modifies_scene": False' in text
    assert '"requires_confirmation": "never"' in text
    assert "analyze_material_snapshot" in text
    assert "analyze_geometry_nodes_snapshot" in text
    assert "plan_pbr_texture_paths" in text
    assert "default_value" in text
    assert "_socket_default_value" in text
    assert '"requires_confirmation": "first"' in text
    assert "_node_group_interface_snapshot" in text
    assert "GeometryNodeTree" in text
    assert "ShaderNode" in text
    assert "GeometryNode" in text


def run():
    test_builtin_node_skills_are_registered()
    test_node_skills_are_read_only_and_named_for_blender_domains()
    print("test_blender_nodes_wiring OK")
    return True


if __name__ == "__main__":
    run()
