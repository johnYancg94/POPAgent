"""Static guards for Phase 2 trace and Phase 3 policy wiring."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_operator_ask_writes_version_2_execution_trace():
    text = (ROOT / "operators" / "operator_ask.py").read_text(encoding="utf-8")

    assert "create_trace" in text
    assert "record_iteration" in text
    assert "record_tool_call" in text
    assert "record_abort" in text
    assert "_active_trace" in text


def test_panel_output_uses_trace_reader_for_legacy_and_v2_debug_view():
    text = (ROOT / "panels" / "panel_output.py").read_text(encoding="utf-8")

    assert "parse_trace" in text
    assert "Execution Trace" in text
    assert "legacy_tool_calls" in text


def test_agent_loop_uses_policy_helpers():
    text = (ROOT / "operators" / "operator_ask.py").read_text(encoding="utf-8")

    assert "choose_max_iters" in text
    assert "normalized_tool_signature" in text
    assert "planning/reflection" in text


def test_operator_ask_records_error_usage_once():
    text = (ROOT / "operators" / "operator_ask.py").read_text(encoding="utf-8")

    assert "_record_usage" in text
    assert "_record_error_usage_once" in text
    assert "_usage_recorded" in text


def test_agent_loop_prefers_dedicated_blender_node_skills():
    text = (ROOT / "operators" / "operator_ask.py").read_text(encoding="utf-8")

    assert "Blender node expert rule" in text
    assert "blender.material.inspect_nodes" in text
    assert "blender.geometry_nodes.inspect" in text
    assert "blender.material.connect_pbr_textures" in text
    assert "blender.geometry_nodes.ensure_basic_group" in text
    assert "blender.nodes.search_types" in text
    assert "blender.material.add_node" in text
    assert "blender.material.connect_nodes" in text
    assert "blender.material.set_node_input" in text
    assert "blender.geometry_nodes.add_node" in text
    assert "blender.geometry_nodes.connect_nodes" in text
    assert "blender.geometry_nodes.set_node_input" in text


def run():
    test_operator_ask_writes_version_2_execution_trace()
    test_panel_output_uses_trace_reader_for_legacy_and_v2_debug_view()
    test_agent_loop_uses_policy_helpers()
    test_operator_ask_records_error_usage_once()
    test_agent_loop_prefers_dedicated_blender_node_skills()
    print("test_phase2_phase3_wiring OK")
    return True


if __name__ == "__main__":
    run()
