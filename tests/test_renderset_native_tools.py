"""Pure-Python contract tests for deterministic RenderSet preparation."""

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load(name, relative_path):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


planner = _load(
    "popagent_renderset_planner",
    "builtin_skills/renderset_planner.py",
)


def _snapshot():
    return {
        "project_prefix": "测试岛",
        "overall_camera": {"name": "整体场景相机", "type": "ORTHO", "ortho_scale": 100},
        "regions": [
            {
                "name": "区域一",
                "camera": {"name": "区域一相机", "type": "ORTHO", "ortho_scale": 50},
                "buildings": [
                    {"name": "码头", "path": "区域/区域一/码头", "front_layer": "区域/区域一/码头/前层"},
                    {"name": "大门", "path": "区域/区域一/大门", "front_layer": None},
                ],
                "terrain": "地形/区域一地形",
            },
            {
                "name": "区域二",
                "camera": {"name": "区域二相机", "type": "ORTHO", "ortho_scale": 75},
                "buildings": [
                    {"name": "仓库", "path": "区域/区域二/仓库", "front_layer": None},
                ],
                "terrain": "地形/区域二地形",
            },
        ],
        "overall_terrain": "地形/整体地形",
        "water": "地形/水面",
        "particles": ["粒子/植被散布", "粒子/石头散布"],
        "existing_context_names": ["测试岛区域一_码头"],
    }


def test_build_plan_emits_complete_context_matrix():
    plan = planner.build_context_plan(_snapshot())

    assert plan["blocking_ambiguities"] == []
    names = [item["name"] for item in plan["contexts"]]
    assert names == [
        "测试岛整体场景_完整体",
        "测试岛整体场景_地形",
        "测试岛整体场景_地形_shadow",
        "测试岛区域一_完整预览",
        "测试岛区域一_shadow",
        "测试岛区域一_码头",
        "测试岛区域一_码头_前层",
        "测试岛区域一_大门",
        "测试岛区域二_完整预览",
        "测试岛区域二_shadow",
        "测试岛区域二_仓库",
    ]

    by_name = {item["name"]: item for item in plan["contexts"]}
    assert by_name["测试岛区域一_码头"]["operation"] == "update"
    assert by_name["测试岛区域一_大门"]["operation"] == "create"
    assert by_name["测试岛区域一_shadow"]["samples"] == 100
    assert by_name["测试岛区域一_shadow"]["noise_threshold"] == 0.005
    assert by_name["测试岛区域一_码头"]["samples"] == 600
    assert by_name["测试岛区域一_码头"]["noise_threshold"] == 0.0
    assert by_name["测试岛区域一_码头"]["render_region"] is True
    assert by_name["测试岛区域一_完整预览"]["include_in_render_all"] is False
    assert by_name["测试岛区域一_shadow"]["include_in_render_all"] is True
    assert by_name["测试岛区域二_仓库"]["resolution_percentage"] == 150


def test_plan_blocks_missing_or_non_orthographic_region_camera():
    snapshot = _snapshot()
    snapshot["regions"][0]["camera"] = None
    snapshot["regions"][1]["camera"]["type"] = "PERSP"

    plan = planner.build_context_plan(snapshot)

    assert plan["contexts"] == []
    assert {item["kind"] for item in plan["blocking_ambiguities"]} == {
        "missing_region_camera",
        "non_orthographic_camera",
    }


def test_plan_deduplicates_scanner_and_camera_ambiguities():
    snapshot = _snapshot()
    snapshot["overall_camera"] = None
    snapshot["blocking_ambiguities"] = [
        {"kind": "missing_overall_camera", "target": "整体场景", "candidates": []}
    ]

    plan = planner.build_context_plan(snapshot)

    assert plan["blocking_ambiguities"] == [
        {"kind": "missing_overall_camera", "target": "整体场景", "candidates": []}
    ]


def test_plan_uses_semantic_names_but_preserves_real_collection_paths():
    snapshot = _snapshot()
    snapshot["regions"][0]["name"] = "区域一"
    snapshot["regions"][0]["path"] = "区域/区域一.001"
    snapshot["regions"][0]["buildings"][0] = {
        "name": "码头",
        "path": "区域/区域一.001/码头.001",
        "front_layer": "区域/区域一.001/码头.001/前层.001",
    }

    plan = planner.build_context_plan(snapshot)
    dock = next(item for item in plan["contexts"] if item["name"] == "测试岛区域一_码头")

    assert dock["region_path"] == "区域/区域一.001"
    assert dock["target_path"] == "区域/区域一.001/码头.001"


def test_plan_migrates_one_high_confidence_legacy_context():
    snapshot = _snapshot()
    snapshot["existing_context_names"] = [
        "测试岛旧版本区域一_大门",
    ]

    plan = planner.build_context_plan(snapshot)
    gate = next(
        item for item in plan["contexts"]
        if item["name"] == "测试岛区域一_大门"
    )

    assert gate["operation"] == "migrate"
    assert gate["source_name"] == "测试岛旧版本区域一_大门"
    assert plan["duplicate_contexts"] == []
    assert plan["unmatched_contexts"] == []


def test_plan_reports_safe_duplicate_when_canonical_context_exists():
    snapshot = _snapshot()
    snapshot["existing_context_names"] = [
        "测试岛区域一_大门",
        "测试岛旧版本区域一_大门",
    ]

    plan = planner.build_context_plan(snapshot)

    assert plan["duplicate_contexts"] == [{
        "name": "测试岛旧版本区域一_大门",
        "canonical_name": "测试岛区域一_大门",
        "confidence": "high",
        "recommended_action": "delete_after_confirmation",
    }]


def test_plan_keeps_ambiguous_legacy_context_unmatched():
    snapshot = _snapshot()
    snapshot["existing_context_names"] = [
        "测试岛旧版区域一_大门",
        "测试岛备份区域一_大门",
        "区域二建筑",
    ]

    plan = planner.build_context_plan(snapshot)
    gate = next(
        item for item in plan["contexts"]
        if item["name"] == "测试岛区域一_大门"
    )

    assert "source_name" not in gate
    assert plan["blocking_ambiguities"] == []
    assert plan["duplicate_contexts"] == []
    assert plan["unmatched_contexts"] == snapshot["existing_context_names"]
    assert plan["warnings"][-1]["kind"] == "ambiguous_legacy_contexts"


def test_transaction_does_not_mutate_when_plan_needs_input():
    class Adapter:
        def __init__(self):
            self.calls = []

        def snapshot_transaction(self):
            self.calls.append("snapshot")

        def apply_spec(self, spec):
            self.calls.append(("apply", spec["name"]))

    adapter = Adapter()
    result = planner.execute_plan(
        adapter,
        {"contexts": [], "blocking_ambiguities": [{"kind": "missing_region_camera"}]},
    )

    assert result["status"] == "needs_input"
    assert adapter.calls == []
    assert result["render_started"] is False


def test_transaction_rolls_back_on_validation_failure():
    class Adapter:
        def __init__(self):
            self.calls = []

        def snapshot_transaction(self):
            self.calls.append("snapshot")
            return "token"

        def apply_spec(self, spec):
            self.calls.append(("apply", spec["name"]))
            return "created"

        def apply_context_selection_policy(self, specs):
            self.calls.append("selection_policy")
            return []

        def audit_context_selection_policy(self, specs):
            self.calls.append("selection_audit")
            return []

        def audit_specs(self, specs):
            self.calls.append("audit")
            return [{"name": specs[0]["name"], "ok": False, "errors": ["camera"]}]

        def rollback(self, token):
            self.calls.append(("rollback", token))

        def restore_original_context(self):
            self.calls.append("restore")

        def save(self):
            self.calls.append("save")

    adapter = Adapter()
    result = planner.execute_plan(
        adapter,
        {"contexts": [{"name": "测试"}], "blocking_ambiguities": []},
    )

    assert result["status"] == "failed"
    assert result["saved"] is False
    assert ("rollback", "token") in adapter.calls
    assert "save" not in adapter.calls


def test_transaction_saves_only_after_successful_audit():
    class Adapter:
        def __init__(self):
            self.calls = []

        def snapshot_transaction(self):
            self.calls.append("snapshot")
            return "token"

        def apply_spec(self, spec):
            self.calls.append(("apply", spec["name"]))
            return "migrated" if spec.get("operation") == "migrate" else "updated"

        def apply_context_selection_policy(self, specs):
            self.calls.append("selection_policy")
            return ["旧任务"]

        def audit_context_selection_policy(self, specs):
            self.calls.append("selection_audit")
            return [{"name": "旧任务", "ok": True, "errors": []}]

        def audit_specs(self, specs):
            self.calls.append("audit")
            return [{"name": specs[0]["name"], "ok": True, "errors": []}]

        def restore_original_context(self):
            self.calls.append("restore")

        def rollback(self, token):
            self.calls.append(("rollback", token))

        def save(self):
            self.calls.append("save")
            return "C:/scene.blend"

    adapter = Adapter()
    result = planner.execute_plan(
        adapter,
        {
            "contexts": [
                {
                    "name": "测试",
                    "operation": "migrate",
                    "source_name": "旧测试",
                }
            ],
            "blocking_ambiguities": [],
            "duplicate_contexts": [{"name": "重复测试"}],
            "unmatched_contexts": ["模糊测试"],
        },
    )

    assert result["status"] == "success"
    assert result["saved"] is True
    assert result["migrated"] == [
        {"from": "旧测试", "to": "测试"}
    ]
    assert result["updated"] == ["旧任务"]
    assert result["duplicate_contexts"] == [{"name": "重复测试"}]
    assert result["unmatched_contexts"] == ["模糊测试"]
    assert adapter.calls.index("audit") < adapter.calls.index("selection_policy")
    assert adapter.calls.index("selection_policy") < adapter.calls.index("selection_audit")
    assert adapter.calls[-2:] == ["restore", "save"]
    assert not any(call[0] == "rollback" for call in adapter.calls if isinstance(call, tuple))


def test_native_tools_are_registered_and_core_routed():
    init_text = (ROOT / "builtin_skills" / "__init__.py").read_text(encoding="utf-8")
    triage_text = (ROOT / "agent_core" / "skill_triage.py").read_text(encoding="utf-8")
    prompt_text = (ROOT / "agent_core" / "prompts.py").read_text(encoding="utf-8")
    tool_text = (ROOT / "builtin_skills" / "renderset_tools.py").read_text(encoding="utf-8")

    for symbol in ("RENDERSET_INSPECT", "RENDERSET_PREPARE", "RENDERSET_AUDIT"):
        assert symbol in init_text
    for name in ("renderset.inspect", "renderset.prepare", "renderset.audit"):
        assert name in triage_text
        assert name in tool_text
    assert "must not use `dev.run_python`" in prompt_text
    assert '"requires_confirmation": "never"' in tool_text
    assert '"long_running": True' in tool_text


def run():
    for name, value in sorted(globals().items()):
        if name.startswith("test_") and callable(value):
            value()
    print("test_renderset_native_tools OK")


if __name__ == "__main__":
    run()
