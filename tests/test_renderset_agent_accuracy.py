"""Release-gate tests for RenderSet Pro agent accuracy.

These tests intentionally stay pure Python. The Blender read-back behavior lives
in ``tests/blender_renderset_integration.py``; this file guards the agent-facing
contract that prevents a model from claiming RenderSet success after using the
wrong route or omitting the required result details.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_ARTIFACTS = {
    "renderset-agent-scenarios.jsonl",
    "renderset-context-readback.jsonl",
    "renderset-anomalies.md",
}
REQUIRED_REPORT_FIELDS = (
    "created",
    "updated",
    "migrated",
    "duplicate_contexts",
    "unmatched_contexts",
    "skipped",
    "failed",
    "warnings",
    "validation_results",
    "saved",
)
NATIVE_RENDERSET_TOOLS = {
    "renderset.inspect",
    "renderset.prepare",
    "renderset.audit",
}
FORBIDDEN_RENDERSET_TOOLS = {
    "dev.run_python",
    "blender.file.save",
    "blender.object.delete",
}
FORBIDDEN_TOOL_TEXT = (
    "bpy.ops.render.render",
    "Render All",
    "synced_data_json",
)


def _read(rel_path):
    return (ROOT / rel_path).read_text(encoding="utf-8")


def _tool_call(name, arguments=None, result=None):
    return {
        "name": name,
        "arguments": arguments or {},
        "result": result or {"status": "success"},
    }


def _standard_prepare_result():
    return {
        "status": "success",
        "created": [
            "农场岛整体场景_完整体",
            "农场岛整体场景_地形",
            "农场岛整体场景_地形_shadow",
            "农场岛区域一_完整预览",
            "农场岛区域一_shadow",
            "农场岛区域一_码头",
            "农场岛区域一_码头_前层",
        ],
        "updated": [],
        "migrated": [],
        "duplicate_contexts": [],
        "unmatched_contexts": [],
        "skipped": [],
        "failed": [],
        "warnings": [],
        "validation_results": [
            {"name": "农场岛区域一_码头", "ok": True, "errors": []},
            {"name": "农场岛区域一_码头_前层", "ok": True, "errors": []},
            {"name": "农场岛区域一_shadow", "ok": True, "errors": []},
        ],
        "saved": True,
        "render_started": False,
    }


def _final_answer(**overrides):
    fields = {name: "ok" for name in REQUIRED_REPORT_FIELDS}
    fields.update(overrides)
    return "\n".join(f"{name}: {value}" for name, value in fields.items())


def _assert_no_forbidden_renderset_route(trace):
    for call in trace["tool_calls"]:
        assert call["name"] not in FORBIDDEN_RENDERSET_TOOLS
        encoded = repr(call.get("arguments", {}))
        for forbidden in FORBIDDEN_TOOL_TEXT:
            assert forbidden not in encoded


def _assert_activation_before_native_tool(trace):
    names = [call["name"] for call in trace["tool_calls"]]
    assert "agent.activate_skill" in names
    native_indexes = [
        index for index, name in enumerate(names) if name in NATIVE_RENDERSET_TOOLS
    ]
    assert native_indexes, names
    activation_index = names.index("agent.activate_skill")
    assert activation_index < min(native_indexes), names
    activation = trace["tool_calls"][activation_index]
    assert activation["arguments"] == {"name": "prepare-renderset-contexts"}


def _assert_required_final_report_fields(trace):
    final_answer = trace["final_answer"]
    for field in REQUIRED_REPORT_FIELDS:
        assert field in final_answer


def _assert_release_artifacts(trace):
    assert set(trace["artifacts"]) >= REQUIRED_ARTIFACTS


def assert_valid_renderset_agent_trace(trace):
    _assert_no_forbidden_renderset_route(trace)
    _assert_activation_before_native_tool(trace)
    _assert_required_final_report_fields(trace)
    _assert_release_artifacts(trace)
    assert "已完成" != trace["final_answer"].strip()


def test_agent_prompt_forces_native_renderset_tools_not_dev_python():
    prompt_text = _read("agent_core/prompts.py")

    assert "RULE_RENDERSET" in prompt_text
    assert "`prepare-renderset-contexts`" in prompt_text
    assert "Agent " in prompt_text and "Skill" in prompt_text
    for tool_name in sorted(NATIVE_RENDERSET_TOOLS):
        assert f"`{tool_name}`" in prompt_text
    assert "must not use `dev.run_python` for RenderSet work" in prompt_text
    assert "ad-hoc Python fallback" in prompt_text


def test_renderset_skill_teaches_exact_safe_native_route():
    skill_text = _read("builtin_skills/resources/prepare-renderset-contexts/SKILL.md")

    assert "Never click `Render All`" in skill_text
    assert "call `bpy.ops.render.render`" in skill_text
    assert "Never edit RenderSet Pro's serialized `synced_data_json` directly" in skill_text
    assert "Never modify Color Management" in skill_text
    assert "Keep `ViewLayer.material_override = None`" in skill_text
    assert "Never use `dev.run_python`" in skill_text
    assert "POPAgent.builtin_skills.renderset_tools" in skill_text
    for handler in ("_handler_inspect", "_handler_prepare", "_handler_audit"):
        assert handler in skill_text


def test_renderset_tools_expose_required_native_handler_contracts():
    tool_text = _read("builtin_skills/renderset_tools.py")

    for name, handler in (
        ("renderset.inspect", "_handler_inspect"),
        ("renderset.prepare", "_handler_prepare"),
        ("renderset.audit", "_handler_audit"),
    ):
        assert f'"name": "{name}"' in tool_text
        assert f"def {handler}" in tool_text
    assert '"long_running": True' in tool_text
    assert '"requires_confirmation": "never"' in tool_text
    assert '"render_started": False' in tool_text


def test_standard_complete_scene_trace_requires_skill_activation_and_prepare():
    trace = {
        "tool_calls": [
            _tool_call(
                "agent.activate_skill",
                {"name": "prepare-renderset-contexts"},
                {"ok": True},
            ),
            _tool_call("renderset.prepare", {}, _standard_prepare_result()),
        ],
        "final_answer": _final_answer(saved=True, failed=[]),
        "artifacts": [
            "renderset-agent-scenarios.jsonl",
            "renderset-context-readback.jsonl",
            "renderset-anomalies.md",
        ],
    }

    assert_valid_renderset_agent_trace(trace)


def test_trace_rejects_dev_python_or_ad_hoc_renderset_json_edits():
    trace = {
        "tool_calls": [
            _tool_call("agent.activate_skill", {"name": "prepare-renderset-contexts"}),
            _tool_call(
                "dev.run_python",
                {"code": "bpy.context.scene.renderset_contexts[0].synced_data_json = '{}'"},
            ),
            _tool_call("renderset.prepare", {}, _standard_prepare_result()),
        ],
        "final_answer": _final_answer(),
        "artifacts": list(REQUIRED_ARTIFACTS),
    }

    try:
        assert_valid_renderset_agent_trace(trace)
    except AssertionError:
        return
    raise AssertionError("RenderSet agent trace accepted a forbidden Python fallback")


def test_needs_input_trace_asks_question_and_does_not_claim_success():
    trace = {
        "tool_calls": [
            _tool_call("agent.activate_skill", {"name": "prepare-renderset-contexts"}),
            _tool_call(
                "renderset.prepare",
                {},
                {
                    "status": "needs_input",
                    "blocking_ambiguities": [
                        {"kind": "missing_overall_camera", "target": "整体场景"},
                        {"kind": "invalid_project_prefix", "target": "项目名称"},
                    ],
                    "created": [],
                    "updated": [],
                    "render_started": False,
                },
            ),
        ],
        "final_answer": (
            "blocking_ambiguities: missing_overall_camera, invalid_project_prefix\n"
            "请确认项目名前缀和整体场景相机？"
        ),
        "artifacts": list(REQUIRED_ARTIFACTS),
    }

    _assert_no_forbidden_renderset_route(trace)
    _assert_activation_before_native_tool(trace)
    assert "needs_input" not in trace["final_answer"] or "已完成" not in trace["final_answer"]
    assert "?" in trace["final_answer"] or "？" in trace["final_answer"]
    result = trace["tool_calls"][-1]["result"]
    assert result["created"] == []
    assert result["updated"] == []
    assert result["render_started"] is False


def test_render_region_anomaly_trace_requires_warning_measurements():
    warning = {
        "kind": "render_region_high_priority",
        "name": "农场岛区域一_新向日葵田",
        "width": 0.99,
        "height": 0.41,
        "border": (0.0, 0.28, 0.99, 0.69),
        "objects": ["远处孤立小件"],
    }
    trace = {
        "tool_calls": [
            _tool_call("agent.activate_skill", {"name": "prepare-renderset-contexts"}),
            _tool_call(
                "renderset.prepare",
                {},
                {**_standard_prepare_result(), "warnings": [warning]},
            ),
        ],
        "final_answer": _final_answer(
            warnings=(
                "⚠ render_region_high_priority "
                "农场岛区域一_新向日葵田 width=0.99 height=0.41 "
                "border=(0.0, 0.28, 0.99, 0.69) object=远处孤立小件"
            ),
        ),
        "artifacts": list(REQUIRED_ARTIFACTS),
    }

    assert_valid_renderset_agent_trace(trace)
    assert "⚠" in trace["final_answer"]
    for token in ("width=0.99", "height=0.41", "border=", "远处孤立小件"):
        assert token in trace["final_answer"]


def test_failed_transaction_trace_must_report_rollback_not_success():
    failed_result = {
        **_standard_prepare_result(),
        "status": "failed",
        "failed": ["农场岛区域一_码头"],
        "saved": False,
        "rolled_back": True,
        "validation_results": [
            {"name": "农场岛区域一_码头", "ok": False, "errors": ["wrong camera"]}
        ],
    }
    trace = {
        "tool_calls": [
            _tool_call("agent.activate_skill", {"name": "prepare-renderset-contexts"}),
            _tool_call("renderset.prepare", {}, failed_result),
        ],
        "final_answer": _final_answer(
            failed=["农场岛区域一_码头"],
            saved=False,
            validation_results="wrong camera",
        )
        + "\nstatus: failed\nrolled_back: true",
        "artifacts": list(REQUIRED_ARTIFACTS),
    }

    assert_valid_renderset_agent_trace(trace)
    assert "status: failed" in trace["final_answer"]
    assert "rolled_back: true" in trace["final_answer"]
    assert "status: success" not in trace["final_answer"]


def run():
    for name, value in sorted(globals().items()):
        if name.startswith("test_") and callable(value):
            value()
    print("test_renderset_agent_accuracy OK")


if __name__ == "__main__":
    run()
