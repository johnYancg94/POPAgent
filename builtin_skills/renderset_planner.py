"""Pure planning and transaction orchestration for RenderSet preparation."""

from __future__ import annotations

from time import perf_counter


NORMAL_SAMPLES = 600
NORMAL_THRESHOLD = 0.0
SHADOW_SAMPLES = 100
SHADOW_THRESHOLD = 0.005
BASE_RESOLUTION = 1920


def _context_spec(
    snapshot,
    *,
    name,
    kind,
    camera,
    region=None,
    region_path=None,
    building=None,
    target_path=None,
    render_region=False,
    include_in_render_all=True,
):
    is_shadow = name.endswith("_shadow")
    existing = snapshot.get("existing_context_names", [])
    return {
        "name": name,
        "kind": kind,
        "operation": "update" if name in existing else "create",
        "camera": camera["name"],
        "camera_type": camera["type"],
        "ortho_scale": camera["ortho_scale"],
        "resolution_x": BASE_RESOLUTION,
        "resolution_y": BASE_RESOLUTION,
        "resolution_percentage": round(camera["ortho_scale"] * 2),
        "samples": SHADOW_SAMPLES if is_shadow else NORMAL_SAMPLES,
        "noise_threshold": SHADOW_THRESHOLD if is_shadow else NORMAL_THRESHOLD,
        "include_in_render_all": include_in_render_all,
        "render_region": render_region,
        "region": region,
        "region_path": region_path,
        "building": building,
        "target_path": target_path,
    }


def _camera_ambiguities(snapshot):
    ambiguities = []
    overall = snapshot.get("overall_camera")
    if overall is None:
        ambiguities.append({"kind": "missing_overall_camera", "target": "整体场景"})
    elif overall.get("type") != "ORTHO":
        ambiguities.append(
            {"kind": "non_orthographic_camera", "target": overall.get("name")}
        )

    for region in snapshot.get("regions", []):
        camera = region.get("camera")
        if camera is None:
            ambiguities.append(
                {"kind": "missing_region_camera", "target": region.get("name")}
            )
        elif camera.get("type") != "ORTHO":
            ambiguities.append(
                {"kind": "non_orthographic_camera", "target": camera.get("name")}
            )
    return ambiguities


def _dedupe_ambiguities(items):
    result = []
    seen = set()
    for item in items:
        key = (item.get("kind"), item.get("target"))
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def build_context_plan(snapshot):
    """Compile a scene snapshot into deterministic ContextSpec dictionaries."""
    started = perf_counter()
    ambiguities = list(snapshot.get("blocking_ambiguities", []))
    ambiguities.extend(_camera_ambiguities(snapshot))
    ambiguities = _dedupe_ambiguities(ambiguities)
    if ambiguities:
        return {
            "contexts": [],
            "blocking_ambiguities": ambiguities,
            "warnings": list(snapshot.get("warnings", [])),
            "timings": {"plan_ms": round((perf_counter() - started) * 1000, 3)},
        }

    prefix = snapshot.get("project_prefix", "")
    overall_camera = snapshot["overall_camera"]
    contexts = [
        _context_spec(
            snapshot,
            name=f"{prefix}整体场景_完整体",
            kind="overall_preview",
            camera=overall_camera,
            include_in_render_all=False,
        ),
        _context_spec(
            snapshot,
            name=f"{prefix}整体场景_地形",
            kind="overall_terrain",
            camera=overall_camera,
        ),
        _context_spec(
            snapshot,
            name=f"{prefix}整体场景_地形_shadow",
            kind="overall_terrain_shadow",
            camera=overall_camera,
        ),
    ]

    for region in snapshot.get("regions", []):
        region_name = region["name"]
        camera = region["camera"]
        contexts.extend(
            [
                _context_spec(
                    snapshot,
                    name=f"{prefix}{region_name}_完整预览",
                    kind="region_preview",
                    camera=camera,
                    region=region_name,
                    region_path=region.get("path", f"区域/{region_name}"),
                    include_in_render_all=False,
                ),
                _context_spec(
                    snapshot,
                    name=f"{prefix}{region_name}_shadow",
                    kind="region_shadow",
                    camera=camera,
                    region=region_name,
                    region_path=region.get("path", f"区域/{region_name}"),
                ),
            ]
        )
        for building in region.get("buildings", []):
            building_name = building["name"]
            contexts.append(
                _context_spec(
                    snapshot,
                    name=f"{prefix}{region_name}_{building_name}",
                    kind="single_building",
                    camera=camera,
                    region=region_name,
                    region_path=region.get("path", f"区域/{region_name}"),
                    building=building_name,
                    target_path=building["path"],
                    render_region=True,
                )
            )
            front_layer = building.get("front_layer")
            if front_layer:
                contexts.append(
                    _context_spec(
                        snapshot,
                        name=f"{prefix}{region_name}_{building_name}_前层",
                        kind="front_layer",
                        camera=camera,
                        region=region_name,
                        region_path=region.get("path", f"区域/{region_name}"),
                        building=building_name,
                        target_path=front_layer,
                        render_region=True,
                    )
                )

    return {
        "contexts": contexts,
        "blocking_ambiguities": [],
        "warnings": list(snapshot.get("warnings", [])),
        "timings": {"plan_ms": round((perf_counter() - started) * 1000, 3)},
    }


def _base_result(status, plan):
    return {
        "status": status,
        "created": [],
        "updated": [],
        "skipped": [],
        "failed": [],
        "blocking_ambiguities": list(plan.get("blocking_ambiguities", [])),
        "warnings": list(plan.get("warnings", [])),
        "validation_results": [],
        "timings": dict(plan.get("timings", {})),
        "saved": False,
        "render_started": False,
    }


def execute_plan(adapter, plan):
    """Execute a ContextSpec plan atomically through an adapter."""
    if plan.get("blocking_ambiguities"):
        return _base_result("needs_input", plan)

    result = _base_result("failed", plan)
    total_started = perf_counter()
    token = None
    try:
        transaction_started = perf_counter()
        token = adapter.snapshot_transaction()
        result["timings"]["snapshot_ms"] = round(
            (perf_counter() - transaction_started) * 1000, 3
        )

        apply_started = perf_counter()
        for spec in plan.get("contexts", []):
            operation = adapter.apply_spec(spec)
            result["created" if operation == "created" else "updated"].append(spec["name"])
        result["timings"]["apply_ms"] = round(
            (perf_counter() - apply_started) * 1000, 3
        )

        audit_started = perf_counter()
        validation = adapter.audit_specs(plan.get("contexts", []))
        result["validation_results"] = validation
        result["timings"]["audit_ms"] = round(
            (perf_counter() - audit_started) * 1000, 3
        )
        failed = [item for item in validation if not item.get("ok")]
        if failed:
            result["failed"] = [item.get("name", "unknown") for item in failed]
            raise RuntimeError("RenderSet validation failed")

        adapter.restore_original_context()
        save_started = perf_counter()
        saved_path = adapter.save()
        result["timings"]["save_ms"] = round(
            (perf_counter() - save_started) * 1000, 3
        )
        result["saved"] = True
        result["saved_path"] = saved_path
        result["status"] = "success"
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        if token is not None:
            try:
                adapter.rollback(token)
                result["rolled_back"] = True
            except Exception as rollback_exc:
                result["rolled_back"] = False
                result["rollback_error"] = str(rollback_exc)
    finally:
        result["timings"]["total_ms"] = round(
            (perf_counter() - total_started) * 1000, 3
        )
    return result
