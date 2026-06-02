"""Static guards for Codex-style progress wiring in the agent loop."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_node_expert_rule_is_not_duplicated_in_agent_prompt():
    text = (ROOT / "operators" / "operator_ask.py").read_text(encoding="utf-8")
    agent_query = text.split("async def _agent_query", 1)[1].split(
        "async def _agent_stream_iter", 1
    )[0]

    assert agent_query.count("Blender node expert rule") == 1


def test_agent_loop_uses_progress_sink_for_live_status():
    text = (ROOT / "operators" / "operator_ask.py").read_text(encoding="utf-8")

    assert "ProgressSink" in text
    assert "tool_call_start" in text
    assert "finalizing" in text


def test_agent_loop_uses_evidence_contract_not_keyword_guards():
    text = (ROOT / "operators" / "operator_ask.py").read_text(encoding="utf-8")

    assert "requires_tool_for_scene_change" not in text
    assert "requires_tool_for_live_scene_state" not in text
    assert "no_tool_correction_used" not in text
    assert "Evidence rule" in text


def run():
    test_node_expert_rule_is_not_duplicated_in_agent_prompt()
    test_agent_loop_uses_progress_sink_for_live_status()
    test_agent_loop_uses_evidence_contract_not_keyword_guards()
    print("test_operator_progress_wiring OK")
    return True


if __name__ == "__main__":
    run()
