"""Static guards for Codex-style progress wiring in the agent loop."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_agent_prompt_rules_are_built_centrally():
    text = (ROOT / "operators" / "operator_ask.py").read_text(encoding="utf-8")
    agent_query = text.split("async def _agent_query", 1)[1].split(
        "async def _agent_stream_iter", 1
    )[0]

    assert agent_query.count("agent_prompts.build_system_prompt") == 1
    assert "Blender node expert rule" not in agent_query


def test_agent_loop_uses_progress_sink_for_live_status():
    text = (ROOT / "operators" / "operator_ask.py").read_text(encoding="utf-8")

    assert "ProgressSink" in text
    assert "tool_call_start" in text
    assert "finalizing" in text


def test_agent_loop_uses_evidence_contract_not_keyword_guards():
    text = (ROOT / "operators" / "operator_ask.py").read_text(encoding="utf-8")
    prompts = (ROOT / "agent_core" / "prompts.py").read_text(encoding="utf-8")

    assert "requires_tool_for_scene_change" not in text
    assert "requires_tool_for_live_scene_state" not in text
    assert "no_tool_correction_used" not in text
    assert "agent_prompts.build_system_prompt" in text
    assert "RULE_EVIDENCE" in prompts


def test_stream_error_body_is_read_before_status_raise():
    text = (ROOT / "operators" / "operator_ask.py").read_text(encoding="utf-8")
    stream_iter = text.split("async def _agent_stream_iter", 1)[1].split(
        "async def _post_with_retries", 1
    )[0]

    assert stream_iter.index("await response.aread()") < stream_iter.index(
        "response.raise_for_status()"
    )


def run():
    test_agent_prompt_rules_are_built_centrally()
    test_agent_loop_uses_progress_sink_for_live_status()
    test_agent_loop_uses_evidence_contract_not_keyword_guards()
    test_stream_error_body_is_read_before_status_raise()
    print("test_operator_progress_wiring OK")
    return True


if __name__ == "__main__":
    run()
