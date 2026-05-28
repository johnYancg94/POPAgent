"""Pure Python tests for agent loop policy helpers."""

from pathlib import Path
import importlib.util
import sys


ROOT = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location(
    "agent_policy", ROOT / "agent_core" / "agent_policy.py"
)
agent_policy = importlib.util.module_from_spec(spec)
sys.modules["agent_policy"] = agent_policy
spec.loader.exec_module(agent_policy)


def test_normalized_tool_signature_is_stable_for_dict_key_order():
    left = agent_policy.normalized_tool_signature(
        "blender.query",
        {"b": 2, "a": {"y": 1, "x": 0}},
    )
    right = agent_policy.normalized_tool_signature(
        "blender.query",
        {"a": {"x": 0, "y": 1}, "b": 2},
    )

    assert left == right


def test_normalized_tool_signature_changes_for_real_argument_change():
    left = agent_policy.normalized_tool_signature("blender.query", {"name": "Cube"})
    right = agent_policy.normalized_tool_signature("blender.query", {"name": "Sphere"})

    assert left != right


def test_dynamic_max_iters_respects_user_configured_ceiling():
    assert agent_policy.choose_max_iters("what is selected?", tool_count=2, configured_max=10) == 3
    assert agent_policy.choose_max_iters("build a complete material setup then verify it", tool_count=8, configured_max=10) == 10
    assert agent_policy.choose_max_iters("complex task", tool_count=10, configured_max=5) == 5


def run():
    test_normalized_tool_signature_is_stable_for_dict_key_order()
    test_normalized_tool_signature_changes_for_real_argument_change()
    test_dynamic_max_iters_respects_user_configured_ceiling()
    print("test_agent_policy OK")
    return True


if __name__ == "__main__":
    run()
