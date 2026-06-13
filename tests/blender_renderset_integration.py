"""Blender-only integration check for deterministic RenderSet preparation.

Run with:
    blender --background --python tests/blender_renderset_integration.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT.parent) not in sys.path:
    sys.path.insert(0, str(ROOT.parent))

from POPAgent.builtin_skills import renderset_planner, renderset_tools


def _collection(name, parent):
    value = bpy.data.collections.new(name)
    parent.children.link(value)
    return value


def _camera(name, parent, scale):
    data = bpy.data.cameras.new(name)
    data.type = "ORTHO"
    data.ortho_scale = scale
    value = bpy.data.objects.new(name, data)
    parent.objects.link(value)
    return value


def _cube(name, parent, x=0.0):
    mesh = bpy.data.meshes.new(f"{name}Mesh")
    value = bpy.data.objects.new(name, mesh)
    parent.objects.link(value)
    mesh.from_pydata(
        [
            (-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
            (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1),
        ],
        [],
        [
            (0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1),
            (1, 5, 6, 2), (2, 6, 7, 3), (4, 0, 3, 7),
        ],
    )
    value.location.x = x
    return value


def _build_scene():
    scene = bpy.data.scenes.new("POPAgent RenderSet Integration")
    scene_root = _collection("场景", scene.collection)
    region_root = _collection("区域", scene.collection)
    terrain_root = _collection("地形", scene.collection)
    particle_root = _collection("粒子", scene.collection)
    region_one = _collection("区域一", region_root)
    region_two = _collection("区域二", region_root)
    dock = _collection("码头", region_one)
    dock_body = _collection("本体", dock)
    front = _collection("前层", dock)
    warehouse = _collection("仓库", region_two)
    region_one_terrain = _collection("区域一地形", terrain_root)
    _collection("区域二地形", terrain_root)
    overall_terrain = _collection("整体地形", terrain_root)
    terrain_detail = _collection("地形细节", region_one_terrain)
    overall_terrain_detail = _collection("整体地形细节", overall_terrain)
    water = _collection("水面", scene.collection)
    scatter = _collection("植被散布", particle_root)

    _camera("整体场景相机", scene_root, 100)
    _camera("区域一相机", scene_root, 50)
    _camera("区域二相机", scene_root, 75)
    _cube("码头主体", dock_body)
    _cube("码头前层", front, 2)
    _cube("仓库主体", warehouse)
    _cube("区域地形细节块", terrain_detail)
    _cube("地形块", overall_terrain_detail)
    _cube("水面块", water)
    _cube("散布块", scatter)
    return scene


def _run_once(context):
    snapshot = renderset_tools._scan_scene(context, {"project_prefix": "测试岛"})
    plan = renderset_planner.build_context_plan(snapshot)
    assert not plan["blocking_ambiguities"], plan["blocking_ambiguities"]
    adapter = renderset_tools._RenderSetAdapter(context, snapshot)

    def no_disk_save():
        adapter._remove_backups()
        return "TEMP_NO_SAVE"

    adapter.save = no_disk_save
    return renderset_planner.execute_plan(adapter, plan)


def _switch_context(scene, name):
    index = next(
        index
        for index, item in enumerate(scene.renderset_contexts)
        if item.custom_name == name
    )
    if scene.renderset_context_index == index:
        scene.renderset_contexts[index].apply(bpy.context)
    else:
        scene.renderset_context_index = index


def _collection_layers(scene, collection_name):
    collection = bpy.data.collections[collection_name]
    root = renderset_tools._find_layer_collection(
        scene.view_layers[0].layer_collection, collection
    )
    assert root is not None, collection_name
    pending = [root]
    layers = []
    while pending:
        layer = pending.pop()
        layers.append(layer)
        pending.extend(layer.children)
    return layers


def _assert_recursive_collection_states(scene):
    _switch_context(scene, "测试岛整体场景_地形_shadow")
    terrain_layers = _collection_layers(scene, "地形")
    assert all(layer.indirect_only for layer in terrain_layers), [
        layer.name for layer in terrain_layers if not layer.indirect_only
    ]

    _switch_context(scene, "测试岛区域一_shadow")
    region_layers = _collection_layers(scene, "区域一")
    assert all(layer.indirect_only for layer in region_layers), [
        layer.name for layer in region_layers if not layer.indirect_only
    ]

    _switch_context(scene, "测试岛区域一_码头")
    terrain_layers = _collection_layers(scene, "地形")
    assert all(layer.indirect_only and layer.holdout for layer in terrain_layers), [
        layer.name
        for layer in terrain_layers
        if not layer.indirect_only or not layer.holdout
    ]
    water_layers = _collection_layers(scene, "水面")
    assert all(layer.indirect_only and layer.holdout for layer in water_layers), [
        layer.name
        for layer in water_layers
        if not layer.indirect_only or not layer.holdout
    ]


scene = _build_scene()
with bpy.context.temp_override(scene=scene, view_layer=scene.view_layers[0]):
    first = _run_once(bpy.context)
    _assert_recursive_collection_states(scene)
    second = _run_once(bpy.context)
    save_path = os.path.join(tempfile.gettempdir(), "popagent_renderset_integration.blend")
    bpy.ops.wm.save_as_mainfile(filepath=save_path)
    saved = renderset_tools._handler_prepare(
        context=bpy.context,
        decisions={"project_prefix": "测试岛"},
    )
    baseline_names = [item.custom_name for item in scene.renderset_contexts]
    rollback_snapshot = renderset_tools._scan_scene(
        bpy.context, {"project_prefix": "测试岛"}
    )
    rollback_plan = renderset_planner.build_context_plan(rollback_snapshot)
    rollback_adapter = renderset_tools._RenderSetAdapter(
        bpy.context, rollback_snapshot
    )

    def fail_after_cleanup():
        rollback_adapter._remove_backups()
        raise RuntimeError("intentional save failure")

    rollback_adapter.save = fail_after_cleanup
    rolled_back = renderset_planner.execute_plan(
        rollback_adapter, rollback_plan
    )

summary = {
    "first": {
        "status": first["status"],
        "created": len(first["created"]),
        "updated": len(first["updated"]),
        "failed": first["failed"],
        "total_ms": first["timings"]["total_ms"],
    },
    "second": {
        "status": second["status"],
        "created": len(second["created"]),
        "updated": len(second["updated"]),
        "failed": second["failed"],
        "total_ms": second["timings"]["total_ms"],
    },
    "context_count": len(scene.renderset_contexts),
    "saved": {
        "status": saved["status"],
        "saved": saved["saved"],
        "path_exists": os.path.isfile(save_path),
        "total_ms": saved["timings"].get("handler_total_ms"),
    },
    "rollback": {
        "status": rolled_back["status"],
        "rolled_back": rolled_back.get("rolled_back"),
        "context_count": len(scene.renderset_contexts),
    },
}
print("POPAGENT_RENDERSET_INTEGRATION=" + json.dumps(summary, ensure_ascii=False))

assert first["status"] == "success", first
assert second["status"] == "success", second
assert len(first["created"]) == 10
assert len(second["created"]) == 0
assert len(second["updated"]) == 10
assert len(scene.renderset_contexts) == 10
assert saved["status"] == "success", saved
assert saved["saved"] is True
assert os.path.isfile(save_path)
assert rolled_back["status"] == "failed", rolled_back
assert rolled_back["rolled_back"] is True, rolled_back
assert [item.custom_name for item in scene.renderset_contexts] == baseline_names
os.unlink(save_path)
