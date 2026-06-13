"""Deterministic RenderSet Pro inspection, preparation, and audit tools."""

from __future__ import annotations

import os
import re
import time
from collections import Counter

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

from .renderset_planner import build_context_plan, execute_plan


THRESHOLD_PATH = "bpy.context.scene.cycles.adaptive_threshold"
DEFAULT_REQUIRED_PATHS = (
    "bpy.context.scene.render.engine",
    "bpy.context.scene.render.film_transparent",
    "bpy.context.scene.render.resolution_x",
    "bpy.context.scene.render.resolution_y",
    "bpy.context.scene.render.resolution_percentage",
    "bpy.context.scene.cycles.samples",
    "bpy.context.scene.cycles.max_bounces",
)
EXTRA_STORED_SETTING_PATHS = (
    THRESHOLD_PATH,
    "bpy.context.scene.render.pixel_aspect_x",
    "bpy.context.scene.render.pixel_aspect_y",
    "bpy.context.scene.render.use_border",
    "bpy.context.scene.render.use_crop_to_border",
    "bpy.context.scene.render.border_min_x",
    "bpy.context.scene.render.border_max_x",
    "bpy.context.scene.render.border_min_y",
    "bpy.context.scene.render.border_max_y",
    "bpy.context.scene.cycles.use_adaptive_sampling",
    "bpy.context.scene.cycles.adaptive_min_samples",
    "bpy.context.scene.cycles.diffuse_bounces",
    "bpy.context.scene.cycles.glossy_bounces",
    "bpy.context.scene.cycles.transmission_bounces",
    "bpy.context.scene.cycles.volume_bounces",
    "bpy.context.scene.cycles.transparent_max_bounces",
    "bpy.context.scene.cycles.use_light_tree",
)


def _result(status, *, started, **extra):
    result = {
        "status": status,
        "created": [],
        "updated": [],
        "skipped": [],
        "failed": [],
        "blocking_ambiguities": [],
        "warnings": [],
        "validation_results": [],
        "timings": {"total_ms": round((time.perf_counter() - started) * 1000, 3)},
        "saved": False,
        "render_started": False,
    }
    result.update(extra)
    return result


def _children(collection):
    return list(getattr(collection, "children", ()))


def _semantic_name(name):
    return re.sub(r"\.\d{3}$", "", name)


def _find_named_collection(collections, exact_name):
    exact = [item for item in collections if item.name == exact_name]
    if len(exact) == 1:
        return exact[0], []
    fuzzy = [item for item in collections if exact_name in item.name]
    if len(fuzzy) == 1:
        return fuzzy[0], []
    if not fuzzy:
        return None, [{"kind": "missing_collection", "target": exact_name}]
    return None, [{
        "kind": "ambiguous_collection",
        "target": exact_name,
        "candidates": [item.name for item in fuzzy],
    }]


def _collection_index(scene):
    by_path = {}
    by_name = {}

    def visit(collection, prefix=""):
        for child in _children(collection):
            path = f"{prefix}/{child.name}" if prefix else child.name
            by_path[path] = child
            by_name.setdefault(child.name, []).append((path, child))
            visit(child, path)

    visit(scene.collection)
    return by_path, by_name


def _camera_info(camera):
    return {
        "name": camera.name,
        "type": camera.data.type,
        "ortho_scale": float(camera.data.ortho_scale),
    }


def _resolve_camera(cameras, label, decisions, *, overall=False):
    mapping = decisions.get("region_cameras", {}) if isinstance(decisions, dict) else {}
    requested = decisions.get("overall_camera") if overall else mapping.get(label)
    if requested:
        matches = [camera for camera in cameras if camera.name == requested]
    elif overall:
        matches = [
            camera for camera in cameras
            if "相机" in _semantic_name(camera.name)
            and ("整体" in _semantic_name(camera.name) or "全景" in _semantic_name(camera.name))
        ]
    else:
        matches = [
            camera for camera in cameras
            if label in _semantic_name(camera.name) and "相机" in _semantic_name(camera.name)
        ]

    if len(matches) == 1:
        return _camera_info(matches[0]), []
    kind = "missing_overall_camera" if overall else "missing_region_camera"
    if len(matches) > 1:
        kind = "ambiguous_overall_camera" if overall else "ambiguous_region_camera"
    return None, [{
        "kind": kind,
        "target": label,
        "candidates": [camera.name for camera in matches],
    }]


def _infer_prefix(scene, region_names, existing_names, decisions):
    explicit = decisions.get("project_prefix", "") if isinstance(decisions, dict) else ""
    if explicit:
        return explicit
    markers = ["整体场景"] + list(region_names)
    for context_name in existing_names:
        for marker in markers:
            token = f"{marker}_"
            if token in context_name:
                return context_name.split(token, 1)[0]
    stem = os.path.splitext(os.path.basename(bpy.data.filepath))[0]
    if stem:
        return stem
    return scene.name


def _scan_scene(context, decisions=None):
    decisions = decisions if isinstance(decisions, dict) else {}
    scene = context.scene
    paths, by_name = _collection_index(scene)
    top_level = _children(scene.collection)
    blockers = []
    warnings = []

    scene_root, issues = _find_named_collection(top_level, "场景")
    blockers.extend(issues)
    region_root, issues = _find_named_collection(top_level, "区域")
    blockers.extend(issues)
    terrain_root, issues = _find_named_collection(top_level, "地形")
    blockers.extend(issues)
    particle_root, particle_issues = _find_named_collection(top_level, "粒子")
    if particle_issues:
        warnings.extend(particle_issues)

    cameras = [obj for obj in scene.objects if obj.type == "CAMERA"]
    overall_camera, issues = _resolve_camera(cameras, "整体场景", decisions, overall=True)
    blockers.extend(issues)

    existing_names = [
        getattr(item, "custom_name", "") for item in getattr(scene, "renderset_contexts", ())
    ]
    duplicate_names = [
        name for name, count in Counter(existing_names).items() if name and count > 1
    ]
    for name in duplicate_names:
        blockers.append({"kind": "duplicate_context", "target": name})

    regions = []
    if region_root is not None:
        semantic_region_names = [_semantic_name(item.name) for item in _children(region_root)]
        duplicated_regions = {
            name for name, count in Counter(semantic_region_names).items() if count > 1
        }
        for region_collection in _children(region_root):
            region_name = _semantic_name(region_collection.name)
            region_path = f"{region_root.name}/{region_collection.name}"
            if region_name in duplicated_regions:
                blockers.append({
                    "kind": "ambiguous_region_semantic_name",
                    "target": region_name,
                    "candidates": [
                        item.name for item in _children(region_root)
                        if _semantic_name(item.name) == region_name
                    ],
                })
            camera, issues = _resolve_camera(cameras, region_name, decisions)
            blockers.extend(issues)
            buildings = []
            semantic_building_names = [
                _semantic_name(item.name) for item in _children(region_collection)
            ]
            duplicated_buildings = {
                name for name, count in Counter(semantic_building_names).items() if count > 1
            }
            for building_collection in _children(region_collection):
                building_name = _semantic_name(building_collection.name)
                if building_name in duplicated_buildings:
                    blockers.append({
                        "kind": "ambiguous_building_semantic_name",
                        "target": f"{region_name}/{building_name}",
                        "candidates": [
                            item.name for item in _children(region_collection)
                            if _semantic_name(item.name) == building_name
                        ],
                    })
                front_candidates = [
                    child for child in _children(building_collection)
                    if _semantic_name(child.name) == "前层"
                ]
                if len(front_candidates) > 1:
                    blockers.append({
                        "kind": "ambiguous_front_layer",
                        "target": f"{region_name}/{building_collection.name}",
                        "candidates": [child.name for child in front_candidates],
                    })
                if len(front_candidates) == 1:
                    direct_render_objects = [
                        obj.name for obj in building_collection.objects
                        if not obj.hide_render
                    ]
                    if direct_render_objects:
                        blockers.append({
                            "kind": "front_layer_parent_contains_objects",
                            "target": f"{region_name}/{building_name}",
                            "objects": direct_render_objects,
                            "message": (
                                "Move building-body objects into a child collection before "
                                "creating a collection-only 前层 context. No objects were moved."
                            ),
                        })
                building_path = f"{region_path}/{building_collection.name}"
                buildings.append({
                    "name": building_name,
                    "path": building_path,
                    "front_layer": (
                        f"{building_path}/{front_candidates[0].name}"
                        if len(front_candidates) == 1 else None
                    ),
                })

            terrain_path = None
            if terrain_root is not None:
                terrain_matches = [
                    child for child in _children(terrain_root)
                    if region_name in _semantic_name(child.name)
                    and "地形" in _semantic_name(child.name)
                ]
                if len(terrain_matches) == 1:
                    terrain_path = f"{terrain_root.name}/{terrain_matches[0].name}"
                elif len(terrain_matches) > 1:
                    blockers.append({
                        "kind": "ambiguous_region_terrain",
                        "target": region_name,
                        "candidates": [item.name for item in terrain_matches],
                    })

            regions.append({
                "name": region_name,
                "path": region_path,
                "camera": camera,
                "buildings": buildings,
                "terrain": terrain_path,
            })

    overall_terrain = None
    water = None
    if terrain_root is not None:
        for child in _children(terrain_root):
            path = f"{terrain_root.name}/{child.name}"
            if child.name == "整体地形":
                overall_terrain = path
            elif child.name == "水面":
                water = path
    if water is None:
        top_level_water = [
            collection for collection in top_level if collection.name == "水面"
        ]
        if len(top_level_water) == 1:
            water = top_level_water[0].name
        elif len(top_level_water) > 1:
            blockers.append({
                "kind": "ambiguous_water_collection",
                "target": "水面",
                "candidates": [collection.name for collection in top_level_water],
            })

    region_names = [region["name"] for region in regions]
    snapshot = {
        "project_prefix": _infer_prefix(scene, region_names, existing_names, decisions),
        "overall_camera": overall_camera,
        "regions": regions,
        "overall_terrain": overall_terrain,
        "water": water,
        "particles": (
            [f"{particle_root.name}/{child.name}" for child in _children(particle_root)]
            if particle_root is not None else []
        ),
        "existing_context_names": existing_names,
        "blocking_ambiguities": blockers,
        "warnings": warnings,
        "_paths": paths,
        "_roots": {
            "scene": scene_root.name if scene_root else None,
            "region": region_root.name if region_root else None,
            "terrain": terrain_root.name if terrain_root else None,
            "water": water,
            "particle": particle_root.name if particle_root else None,
        },
    }
    return snapshot


def _find_layer_collection(root, collection):
    if root.collection == collection:
        return root
    for child in root.children:
        found = _find_layer_collection(child, collection)
        if found is not None:
            return found
    return None


def _walk_layer_collections(root):
    yield root
    for child in root.children:
        yield from _walk_layer_collections(child)


def _set_layer_state(layer, *, enabled, holdout=False, indirect_only=False, recursive=False):
    targets = _walk_layer_collections(layer) if recursive else (layer,)
    for target in targets:
        target.exclude = not enabled
        target.collection.hide_render = not enabled
        target.holdout = holdout if enabled else False
        target.indirect_only = indirect_only if enabled else False


def _fixed_render_settings(scene):
    scene.render.engine = "CYCLES"
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_min_samples = 0
    scene.cycles.max_bounces = 12
    scene.cycles.diffuse_bounces = 4
    scene.cycles.glossy_bounces = 4
    scene.cycles.transmission_bounces = 12
    scene.cycles.volume_bounces = 0
    scene.cycles.transparent_max_bounces = 8
    scene.cycles.use_light_tree = True
    scene.render.film_transparent = True
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1920
    scene.render.pixel_aspect_x = 1.0
    scene.render.pixel_aspect_y = 1.0
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.render.image_settings.compression = 15


def _projectable_points(context, collection, camera):
    scene = context.scene
    depsgraph = context.evaluated_depsgraph_get()
    source_objects = list(collection.all_objects)
    source_ids = {obj.original.as_pointer() if hasattr(obj, "original") else obj.as_pointer()
                  for obj in source_objects}
    points = []
    per_object = {}

    def add_object_points(name, obj, matrix):
        if obj.hide_render or not getattr(obj, "bound_box", None):
            return
        projected_points = []
        for corner in obj.bound_box:
            projected = world_to_camera_view(scene, camera, matrix @ Vector(corner))
            if projected.z >= 0:
                point = (float(projected.x), float(projected.y))
                points.append(point)
                projected_points.append(point)
        if projected_points:
            per_object.setdefault(name, []).extend(projected_points)

    for obj in source_objects:
        evaluated = obj.evaluated_get(depsgraph)
        add_object_points(obj.name, evaluated, evaluated.matrix_world)

    for instance in depsgraph.object_instances:
        if not instance.is_instance:
            continue
        parent = getattr(instance, "parent", None)
        original = getattr(parent, "original", None) if parent else None
        if original is None or original.as_pointer() not in source_ids:
            continue
        add_object_points(instance.object.name, instance.object, instance.matrix_world)
    return points, per_object


def _calculate_border(context, collection, camera):
    points, per_object = _projectable_points(context, collection, camera)
    if not points:
        raise ValueError(f"No projectable render geometry in {collection.name}")
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    pad_x = (max_x - min_x) * 0.10
    pad_y = (max_y - min_y) * 0.10
    border = {
        "min_x": max(0.0, min_x - pad_x),
        "max_x": min(1.0, max_x + pad_x),
        "min_y": max(0.0, min_y - pad_y),
        "max_y": min(1.0, max_y + pad_y),
    }
    border["width"] = border["max_x"] - border["min_x"]
    border["height"] = border["max_y"] - border["min_y"]
    border["objects"] = sorted(per_object)
    return border


class _RenderSetAdapter:
    def __init__(self, context, snapshot):
        self.context = context
        self.scene = context.scene
        self.snapshot = snapshot
        self.paths = snapshot["_paths"]
        self.roots = snapshot["_roots"]
        self.original_index = int(self.scene.renderset_context_index)
        self.original_count = len(self.scene.renderset_contexts)
        self.backup_count = 0
        self.backups_cleaned = False
        self.expected_states = {}
        self.border_reports = {}

    def _switch(self, index):
        if index < 0 or index >= len(self.scene.renderset_contexts):
            raise IndexError(f"Invalid RenderSet context index: {index}")
        if self.scene.renderset_context_index == index:
            item = self.scene.renderset_contexts[index]
            item.apply(self.context)
            return item
        self.scene.renderset_context_index = index
        if self.scene.renderset_context_index != index:
            raise RuntimeError(f"RenderSet context switch failed: {index}")
        return self.scene.renderset_contexts[index]

    def snapshot_transaction(self):
        original_names = []
        public_states = []
        for index in range(self.original_count):
            source = self._switch(index)
            source.sync(self.context)
            original_names.append(source.custom_name)
            public_states.append(self._capture_public_state(source))
            self.scene.renderset_contexts.add()
            source = self.scene.renderset_contexts[index]
            backup = self.scene.renderset_contexts[-1]
            backup.init_from(self.context, source)
            self.backup_count += 1
        if self.original_count:
            self._switch(min(self.original_index, self.original_count - 1))
        return {
            "original_count": self.original_count,
            "original_index": self.original_index,
            "original_names": original_names,
            "public_states": public_states,
        }

    def _capture_public_state(self, item):
        scene = self.scene
        render = scene.render
        cycles = scene.cycles
        return {
            "custom_name": item.custom_name,
            "include_in_render_all": bool(item.include_in_render_all),
            "camera": scene.camera.name if scene.camera else None,
            "material_override": (
                self.context.view_layer.material_override.name
                if self.context.view_layer.material_override else None
            ),
            "render": {
                "engine": render.engine,
                "film_transparent": bool(render.film_transparent),
                "resolution_x": render.resolution_x,
                "resolution_y": render.resolution_y,
                "resolution_percentage": render.resolution_percentage,
                "pixel_aspect_x": render.pixel_aspect_x,
                "pixel_aspect_y": render.pixel_aspect_y,
                "use_border": bool(render.use_border),
                "use_crop_to_border": bool(render.use_crop_to_border),
                "border_min_x": render.border_min_x,
                "border_max_x": render.border_max_x,
                "border_min_y": render.border_min_y,
                "border_max_y": render.border_max_y,
                "file_format": render.image_settings.file_format,
                "color_mode": render.image_settings.color_mode,
                "color_depth": render.image_settings.color_depth,
                "compression": render.image_settings.compression,
            },
            "cycles": {
                "use_adaptive_sampling": bool(cycles.use_adaptive_sampling),
                "adaptive_min_samples": cycles.adaptive_min_samples,
                "adaptive_threshold": cycles.adaptive_threshold,
                "samples": cycles.samples,
                "max_bounces": cycles.max_bounces,
                "diffuse_bounces": cycles.diffuse_bounces,
                "glossy_bounces": cycles.glossy_bounces,
                "transmission_bounces": cycles.transmission_bounces,
                "volume_bounces": cycles.volume_bounces,
                "transparent_max_bounces": cycles.transparent_max_bounces,
                "use_light_tree": bool(cycles.use_light_tree),
            },
            "collections": self._capture_collection_states(),
            "overrides_add": set(item.overrides.add),
            "overrides_remove": set(item.overrides.remove),
        }

    def _capture_collection_states(self):
        states = []
        for path, collection in self.paths.items():
            layer = _find_layer_collection(
                self.context.view_layer.layer_collection, collection
            )
            if layer is None:
                continue
            states.append({
                "path": path,
                "exclude": bool(layer.exclude),
                "hide_render": bool(collection.hide_render),
                "holdout": bool(layer.holdout),
                "indirect_only": bool(layer.indirect_only),
            })
        return states

    def _restore_public_state(self, item, state):
        scene = self.scene
        render = scene.render
        cycles = scene.cycles
        scene.camera = bpy.data.objects.get(state["camera"]) if state["camera"] else None
        material_name = state["material_override"]
        self.context.view_layer.material_override = (
            bpy.data.materials.get(material_name) if material_name else None
        )
        for key, value in state["render"].items():
            if key in {"file_format", "color_mode", "color_depth", "compression"}:
                setattr(render.image_settings, key, value)
            else:
                setattr(render, key, value)
        for key, value in state["cycles"].items():
            setattr(cycles, key, value)
        for collection_state in state["collections"]:
            layer = self._layer(collection_state["path"])
            layer.exclude = collection_state["exclude"]
            layer.collection.hide_render = collection_state["hide_render"]
            layer.holdout = collection_state["holdout"]
            layer.indirect_only = collection_state["indirect_only"]

        item.custom_name = state["custom_name"]
        item.include_in_render_all = state["include_in_render_all"]
        current = item.overrides
        store_paths = (
            state["overrides_add"] - current.add
        ) | (
            current.remove - state["overrides_remove"]
        )
        if store_paths:
            item.add_overrides(store_paths, True)
        item.sync(self.context)
        current = item.overrides
        remove_paths = (
            current.add - state["overrides_add"]
        ) | (
            state["overrides_remove"] - current.remove
        )
        if remove_paths:
            item.add_overrides(remove_paths, False)

    def _context_search_indexes(self):
        backup_start = self.original_count
        backup_end = backup_start + self.backup_count
        return [
            index for index in range(len(self.scene.renderset_contexts))
            if not (backup_start <= index < backup_end)
        ]

    def _find_context(self, name):
        matches = [
            index for index in self._context_search_indexes()
            if self.scene.renderset_contexts[index].custom_name == name
        ]
        if len(matches) > 1:
            raise RuntimeError(f"Duplicate RenderSet context blocks update: {name}")
        return matches[0] if matches else None

    def _collection(self, path):
        collection = self.paths.get(path)
        if collection is None:
            raise KeyError(f"Collection path not found: {path}")
        return collection

    def _layer(self, path):
        collection = self._collection(path)
        layer = _find_layer_collection(self.context.view_layer.layer_collection, collection)
        if layer is None:
            raise KeyError(f"LayerCollection not found: {path}")
        return layer

    def _reset_managed_collections(self):
        for root_name in (
            self.roots["region"],
            self.roots["terrain"],
            self.roots["water"],
            self.roots["particle"],
        ):
            if not root_name:
                continue
            _set_layer_state(self._layer(root_name), enabled=True, recursive=True)

    def _exclude_other_regions(self, target_region_path):
        region_root = self._collection(self.roots["region"])
        for region in _children(region_root):
            path = f"{region_root.name}/{region.name}"
            _set_layer_state(
                self._layer(path),
                enabled=path == target_region_path,
                recursive=path != target_region_path,
            )

    def _isolate_building(self, region_path, target_building_path):
        region_collection = self._collection(region_path)
        for building in _children(region_collection):
            path = f"{region_path}/{building.name}"
            _set_layer_state(
                self._layer(path),
                enabled=path == target_building_path,
                recursive=path != target_building_path,
            )

    def _apply_collection_matrix(self, spec):
        self._reset_managed_collections()
        kind = spec["kind"]
        if kind in {"overall_terrain", "overall_terrain_shadow"}:
            _set_layer_state(
                self._layer(self.roots["region"]), enabled=False, recursive=True
            )
        if kind == "overall_terrain_shadow":
            _set_layer_state(
                self._layer(self.roots["terrain"]),
                enabled=True,
                indirect_only=True,
                recursive=True,
            )
        if kind in {"region_preview", "region_shadow", "single_building", "front_layer"}:
            self._exclude_other_regions(spec["region_path"])
        if kind == "region_shadow":
            _set_layer_state(
                self._layer(spec["region_path"]),
                enabled=True,
                indirect_only=True,
                recursive=True,
            )
            if self.roots["particle"]:
                _set_layer_state(
                    self._layer(self.roots["particle"]), enabled=False, recursive=True
                )
        if kind in {"single_building", "front_layer"}:
            building_path = (
                spec["target_path"].rsplit("/", 1)[0]
                if kind == "front_layer" else spec["target_path"]
            )
            self._isolate_building(spec["region_path"], building_path)
            _set_layer_state(
                self._layer(self.roots["terrain"]),
                enabled=True,
                holdout=True,
                indirect_only=True,
                recursive=True,
            )
            if self.roots["water"]:
                _set_layer_state(
                    self._layer(self.roots["water"]),
                    enabled=True,
                    holdout=True,
                    indirect_only=True,
                    recursive=True,
                )
            if self.roots["particle"]:
                _set_layer_state(
                    self._layer(self.roots["particle"]), enabled=False, recursive=True
                )
        if kind == "front_layer":
            target_collection = self._collection(spec["target_path"])
            building_path = spec["target_path"].rsplit("/", 1)[0]
            building_collection = self._collection(building_path)
            for child in _children(building_collection):
                child_path = f"{building_path}/{child.name}"
                _set_layer_state(
                    self._layer(child_path),
                    enabled=child == target_collection,
                    recursive=child != target_collection,
                )

    def _planned_expected_states(self, spec):
        states = {}
        managed_roots = tuple(
            root for root in (
                self.roots["region"],
                self.roots["terrain"],
                self.roots["water"],
                self.roots["particle"],
            ) if root
        )
        for path in self.paths:
            if any(path == root or path.startswith(f"{root}/") for root in managed_roots):
                states[path] = {
                    "path": path,
                    "exclude": False,
                    "hide_render": False,
                    "holdout": False,
                    "indirect_only": False,
                }

        def set_state(path, *, enabled, holdout=False, indirect_only=False, recursive=False):
            targets = [
                candidate for candidate in states
                if candidate == path or (recursive and candidate.startswith(f"{path}/"))
            ]
            for target in targets:
                states[target].update({
                    "exclude": not enabled,
                    "hide_render": not enabled,
                    "holdout": holdout if enabled else False,
                    "indirect_only": indirect_only if enabled else False,
                })

        kind = spec["kind"]
        if kind in {"overall_terrain", "overall_terrain_shadow"}:
            set_state(self.roots["region"], enabled=False, recursive=True)
        if kind == "overall_terrain_shadow":
            set_state(
                self.roots["terrain"],
                enabled=True,
                indirect_only=True,
                recursive=True,
            )
        if kind in {"region_preview", "region_shadow", "single_building", "front_layer"}:
            for region in self.snapshot["regions"]:
                path = region["path"]
                set_state(
                    path,
                    enabled=path == spec["region_path"],
                    recursive=path != spec["region_path"],
                )
        if kind == "region_shadow":
            set_state(
                spec["region_path"],
                enabled=True,
                indirect_only=True,
                recursive=True,
            )
            if self.roots["particle"]:
                set_state(self.roots["particle"], enabled=False, recursive=True)
        if kind in {"single_building", "front_layer"}:
            target_building = (
                spec["target_path"].rsplit("/", 1)[0]
                if kind == "front_layer" else spec["target_path"]
            )
            region = next(
                item for item in self.snapshot["regions"]
                if item["path"] == spec["region_path"]
            )
            for building in region["buildings"]:
                set_state(
                    building["path"],
                    enabled=building["path"] == target_building,
                    recursive=building["path"] != target_building,
                )
            set_state(
                self.roots["terrain"],
                enabled=True,
                holdout=True,
                indirect_only=True,
                recursive=True,
            )
            if self.roots["water"]:
                set_state(
                    self.roots["water"],
                    enabled=True,
                    holdout=True,
                    indirect_only=True,
                    recursive=True,
                )
            if self.roots["particle"]:
                set_state(self.roots["particle"], enabled=False, recursive=True)
        if kind == "front_layer":
            building_path = spec["target_path"].rsplit("/", 1)[0]
            for candidate in states:
                if (
                    candidate.startswith(f"{building_path}/")
                    and candidate.count("/") == building_path.count("/") + 1
                ):
                    set_state(
                        candidate,
                        enabled=candidate == spec["target_path"],
                        recursive=candidate != spec["target_path"],
                    )
        return list(states.values())

    def _apply_render_region(self, spec, camera):
        render = self.scene.render
        render.use_crop_to_border = False
        if not spec["render_region"]:
            render.use_border = False
            return
        border = _calculate_border(self.context, self._collection(spec["target_path"]), camera)
        render.use_border = True
        render.border_min_x = border["min_x"]
        render.border_max_x = border["max_x"]
        render.border_min_y = border["min_y"]
        render.border_max_y = border["max_y"]
        self.border_reports[spec["name"]] = border

    def _ensure_stored_settings(self, item):
        overrides = item.overrides
        missing = [
            path for path in EXTRA_STORED_SETTING_PATHS
            if path not in overrides.add
        ]
        missing.extend(
            path for path in DEFAULT_REQUIRED_PATHS
            if path in overrides.remove
        )
        if missing:
            item.add_overrides(missing, True)

    def apply_spec(self, spec):
        index = self._find_context(spec["name"])
        created = index is None
        if created:
            source_index = (
                self.scene.renderset_context_index
                if len(self.scene.renderset_contexts) else None
            )
            self.scene.renderset_contexts.add()
            item = self.scene.renderset_contexts[-1]
            if source_index is None:
                item.init_default(self.context)
            else:
                source = self.scene.renderset_contexts[source_index]
                item.init_from(self.context, source)
            index = len(self.scene.renderset_contexts) - 1
            item.custom_name = spec["name"]

        item = self.scene.renderset_contexts[index]
        item.custom_name = spec["name"]
        camera = bpy.data.objects.get(spec["camera"])
        if camera is None or camera.type != "CAMERA":
            raise RuntimeError(f"Camera not found: {spec['camera']}")
        if camera.data.type != "ORTHO":
            raise RuntimeError(f"Formal render camera is not ORTHO: {camera.name}")

        self.scene.camera = camera
        self.context.view_layer.material_override = None
        _fixed_render_settings(self.scene)
        self.scene.cycles.samples = spec["samples"]
        self.scene.cycles.adaptive_threshold = spec["noise_threshold"]
        self.scene.render.resolution_percentage = spec["resolution_percentage"]
        item.include_in_render_all = spec["include_in_render_all"]
        self._apply_collection_matrix(spec)
        self._apply_render_region(spec, camera)
        self._ensure_stored_settings(item)
        item.sync(self.context)
        self.expected_states[spec["name"]] = self._planned_expected_states(spec)
        return "created" if created else "updated"

    def _audit_one(self, spec):
        index = self._find_context(spec["name"])
        errors = []
        warnings = []
        if index is None:
            return {"name": spec["name"], "ok": False, "errors": ["context missing"]}
        item = self._switch(index)
        scene = self.scene
        camera = scene.camera
        checks = (
            (camera is not None and camera.name == spec["camera"], "wrong camera"),
            (camera is not None and camera.data.type == "ORTHO", "camera is not ORTHO"),
            (scene.render.resolution_x == 1920, "resolution_x is not 1920"),
            (scene.render.resolution_y == 1920, "resolution_y is not 1920"),
            (
                scene.render.resolution_percentage == spec["resolution_percentage"],
                "resolution percentage mismatch",
            ),
            (scene.cycles.samples == spec["samples"], "samples mismatch"),
            (
                abs(scene.cycles.adaptive_threshold - spec["noise_threshold"]) < 1e-8,
                "noise threshold mismatch",
            ),
            (
                bool(item.include_in_render_all) == spec["include_in_render_all"],
                "Include in Render All mismatch",
            ),
            (self.context.view_layer.material_override is None, "material override is not empty"),
            (scene.render.use_border == spec["render_region"], "Render Region mismatch"),
            (scene.render.use_crop_to_border is False, "Crop to Render Region is enabled"),
        )
        errors.extend(message for passed, message in checks if not passed)

        for expected in self.expected_states.get(spec["name"], []):
            layer = self._layer(expected["path"])
            actual = {
                "exclude": bool(layer.exclude),
                "hide_render": bool(layer.collection.hide_render),
                "holdout": bool(layer.holdout),
                "indirect_only": bool(layer.indirect_only),
            }
            mismatch = [
                key for key, value in actual.items() if value != expected[key]
            ]
            if mismatch:
                errors.append(
                    f"collection state mismatch: {expected['path']} ({', '.join(mismatch)})"
                )
        border = self.border_reports.get(spec["name"])
        if border:
            if border["width"] >= 0.98 or border["height"] >= 0.98:
                warnings.append({
                    "kind": "render_region_high_priority",
                    "width": border["width"],
                    "height": border["height"],
                    "objects": border["objects"],
                })
            elif border["width"] >= 0.90 or border["height"] >= 0.90:
                warnings.append({
                    "kind": "render_region_suspicious",
                    "width": border["width"],
                    "height": border["height"],
                    "objects": border["objects"],
                })
            if any(border[key] in {0.0, 1.0} for key in ("min_x", "max_x", "min_y", "max_y")):
                warnings.append({"kind": "render_region_touches_edge"})
        return {"name": spec["name"], "ok": not errors, "errors": errors, "warnings": warnings}

    def audit_specs(self, specs):
        active_index = self.scene.renderset_context_index
        if 0 <= active_index < len(self.scene.renderset_contexts):
            self.scene.renderset_contexts[active_index].apply(self.context)
        return [self._audit_one(spec) for spec in specs]

    def restore_original_context(self):
        if self.original_count:
            self._switch(min(self.original_index, self.original_count - 1))

    def _remove_backups(self):
        for _ in range(self.backup_count):
            self.scene.renderset_contexts.remove(self.original_count)
        self.backup_count = 0
        self.backups_cleaned = True
        self.restore_original_context()

    def save(self):
        self._remove_backups()
        target = bpy.data.filepath
        if not target:
            raise RuntimeError("The .blend file has never been saved")
        result = bpy.ops.wm.save_as_mainfile(filepath=target)
        if "FINISHED" not in result:
            raise RuntimeError(f"Blender save failed: {result}")
        return bpy.data.filepath

    def rollback(self, token):
        if self.backups_cleaned:
            while len(self.scene.renderset_contexts) > token["original_count"]:
                self.scene.renderset_contexts.remove(
                    len(self.scene.renderset_contexts) - 1
                )
            for index, state in enumerate(token["public_states"]):
                item = self.scene.renderset_contexts[index]
                self._restore_public_state(item, state)
            if token["original_count"]:
                self._switch(
                    min(token["original_index"], token["original_count"] - 1)
                )
            return

        original_count = token["original_count"]
        backup_count = self.backup_count
        while len(self.scene.renderset_contexts) > original_count + backup_count:
            self.scene.renderset_contexts.remove(len(self.scene.renderset_contexts) - 1)
        for _ in range(original_count):
            self.scene.renderset_contexts.remove(0)
        for index, name in enumerate(token["original_names"]):
            self.scene.renderset_contexts[index].custom_name = name
        self.backup_count = 0
        self.original_count = original_count
        if original_count:
            self._switch(min(token["original_index"], original_count - 1))


def _validate_adapter(context):
    scene = context.scene
    if not hasattr(scene, "renderset_contexts") or not hasattr(scene, "renderset_context_index"):
        return "RenderSet Pro 2.x scene properties are unavailable"
    contexts = scene.renderset_contexts
    if len(contexts):
        required = ("init_from", "sync", "apply", "add_overrides", "custom_name")
        missing = [name for name in required if not hasattr(contexts[0], name)]
        if missing:
            return f"Unsupported RenderSet Pro API; missing: {', '.join(missing)}"
    return None


def _handler_inspect(context=None, decisions=None):
    started = time.perf_counter()
    context = context or bpy.context
    error = _validate_adapter(context)
    if error:
        return _result("failed", started=started, failed=["adapter"], error=error)
    scan_started = time.perf_counter()
    snapshot = _scan_scene(context, decisions)
    plan = build_context_plan(snapshot)
    plan["timings"]["scan_ms"] = round((time.perf_counter() - scan_started) * 1000, 3)
    return _result(
        "needs_input" if plan["blocking_ambiguities"] else "success",
        started=started,
        blocking_ambiguities=plan["blocking_ambiguities"],
        warnings=plan["warnings"],
        timings={**plan["timings"], "total_ms": round((time.perf_counter() - started) * 1000, 3)},
        context_plan=plan["contexts"],
        scene_summary={
            "project_prefix": snapshot["project_prefix"],
            "regions": [
                {
                    "name": region["name"],
                    "camera": region["camera"]["name"] if region["camera"] else None,
                    "buildings": [item["name"] for item in region["buildings"]],
                }
                for region in snapshot["regions"]
            ],
            "existing_context_count": len(snapshot["existing_context_names"]),
        },
    )


def _handler_prepare(context=None, decisions=None):
    started = time.perf_counter()
    context = context or bpy.context
    error = _validate_adapter(context)
    if error:
        return _result("failed", started=started, failed=["adapter"], error=error)
    if not bpy.data.filepath:
        return _result(
            "needs_input",
            started=started,
            blocking_ambiguities=[{
                "kind": "unsaved_blend_file",
                "target": "current file",
                "message": "Save the .blend once before automatic RenderSet preparation.",
            }],
        )
    snapshot = _scan_scene(context, decisions)
    plan = build_context_plan(snapshot)
    if plan["blocking_ambiguities"]:
        return _result(
            "needs_input",
            started=started,
            blocking_ambiguities=plan["blocking_ambiguities"],
            warnings=plan["warnings"],
            context_plan=plan["contexts"],
        )
    adapter = _RenderSetAdapter(context, snapshot)
    result = execute_plan(adapter, plan)
    result["warnings"].extend(
        warning
        for validation in result.get("validation_results", [])
        for warning in validation.get("warnings", [])
    )
    result["timings"]["handler_total_ms"] = round(
        (time.perf_counter() - started) * 1000, 3
    )
    return result


def _handler_audit(context=None, decisions=None):
    started = time.perf_counter()
    context = context or bpy.context
    error = _validate_adapter(context)
    if error:
        return _result("failed", started=started, failed=["adapter"], error=error)
    snapshot = _scan_scene(context, decisions)
    plan = build_context_plan(snapshot)
    if plan["blocking_ambiguities"]:
        return _result(
            "needs_input",
            started=started,
            blocking_ambiguities=plan["blocking_ambiguities"],
            warnings=plan["warnings"],
        )
    adapter = _RenderSetAdapter(context, snapshot)
    adapter.expected_states = {
        spec["name"]: adapter._planned_expected_states(spec)
        for spec in plan["contexts"]
    }
    original_index = int(context.scene.renderset_context_index)
    try:
        validation = adapter.audit_specs(plan["contexts"])
    finally:
        if len(context.scene.renderset_contexts):
            context.scene.renderset_context_index = min(
                original_index, len(context.scene.renderset_contexts) - 1
            )
    failed = [item["name"] for item in validation if not item["ok"]]
    warnings = list(plan["warnings"])
    warnings.extend(
        warning for item in validation for warning in item.get("warnings", [])
    )
    return _result(
        "failed" if failed else "success",
        started=started,
        failed=failed,
        warnings=warnings,
        validation_results=validation,
    )


_DECISIONS_SCHEMA = {
    "type": "object",
    "description": "Answers returned from a previous needs_input result.",
    "properties": {
        "project_prefix": {"type": "string"},
        "overall_camera": {"type": "string"},
        "region_cameras": {
            "type": "object",
            "additionalProperties": {"type": "string"},
        },
    },
    "additionalProperties": True,
}


RENDERSET_INSPECT = {
    "name": "renderset.inspect",
    "description": (
        "Read-only deterministic inspection of the current Chinese collection hierarchy, "
        "RenderSet contexts, cameras, and the exact proposed context plan."
    ),
    "parameters": {
        "type": "object",
        "properties": {"decisions": _DECISIONS_SCHEMA},
        "required": [],
    },
    "owner": "builtin.renderset",
    "handler": _handler_inspect,
    "metadata": {
        "modifies_scene": False,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": False,
        "requires_confirmation": "never",
    },
}

RENDERSET_PREPARE = {
    "name": "renderset.prepare",
    "description": (
        "Atomically create or repair all RenderSet Pro contexts, audit every result, "
        "restore the original context, and save the current .blend. Never renders."
    ),
    "parameters": {
        "type": "object",
        "properties": {"decisions": _DECISIONS_SCHEMA},
        "required": [],
    },
    "owner": "builtin.renderset",
    "handler": _handler_prepare,
    "metadata": {
        "modifies_scene": True,
        "writes_files": True,
        "launches_external_process": False,
        "undoable": False,
        "requires_confirmation": "never",
        "long_running": True,
    },
}

RENDERSET_AUDIT = {
    "name": "renderset.audit",
    "description": (
        "Switch through planned RenderSet Pro contexts, read back render settings, "
        "sampling, cameras, and Render Region, then restore the original context."
    ),
    "parameters": {
        "type": "object",
        "properties": {"decisions": _DECISIONS_SCHEMA},
        "required": [],
    },
    "owner": "builtin.renderset",
    "handler": _handler_audit,
    "metadata": {
        "modifies_scene": True,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": False,
        "requires_confirmation": "never",
        "long_running": True,
    },
}
