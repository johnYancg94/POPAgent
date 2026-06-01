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


def test_repeat_intervention_is_graduated():
    sig = ("dev.run_python", '{"code":"x"}')
    # first occurrence -> proceed
    assert agent_policy.repeat_intervention([sig], sig) == "proceed"
    # second identical -> warn (still executes)
    assert agent_policy.repeat_intervention([sig, sig], sig) == "warn"
    # third identical -> abort
    assert agent_policy.repeat_intervention([sig, sig, sig], sig) == "abort"


def test_repeat_intervention_ignores_calls_outside_window():
    sig = ("dev.run_python", '{"code":"x"}')
    other = ("blender.query", "{}")
    # two matches separated past the window of 6 should not count together
    history = [sig] + [other] * 6 + [sig]
    assert agent_policy.repeat_intervention(history, sig, window=6) == "proceed"


def test_repeat_intervention_distinguishes_different_args():
    a = ("dev.run_python", '{"code":"a"}')
    b = ("dev.run_python", '{"code":"b"}')
    assert agent_policy.repeat_intervention([a, b, a, b], b) == "warn"
    assert agent_policy.repeat_intervention([a, b, a, b, b], b) == "abort"


def test_repeat_warning_text_names_the_skill_and_steers():
    text = agent_policy.repeat_warning_text("dev.run_python")
    assert "dev.run_python" in text
    assert "api_search" in text


def test_is_parallel_safe_only_for_never_confirm_pure_reads():
    # read-only, no side effects, never confirms -> safe
    assert agent_policy.is_parallel_safe("never", {}) is True
    assert agent_policy.is_parallel_safe("never", {"undoable": True}) is True
    # any confirmation level disqualifies (would hit single-flight popup)
    assert agent_policy.is_parallel_safe("always", {}) is False
    assert agent_policy.is_parallel_safe("session", {}) is False
    # any declared side effect disqualifies even at never
    assert agent_policy.is_parallel_safe("never", {"modifies_scene": True}) is False
    assert agent_policy.is_parallel_safe("never", {"writes_files": True}) is False
    assert agent_policy.is_parallel_safe("never", {"launches_external_process": True}) is False
    assert agent_policy.is_parallel_safe("never", None) is True


def test_plan_tool_groups_collapses_runs_and_isolates_unsafe():
    # all safe -> one group
    assert agent_policy.plan_tool_groups([True, True, True]) == [[0, 1, 2]]
    # all unsafe -> singletons in order
    assert agent_policy.plan_tool_groups([False, False]) == [[0], [1]]
    # mixed: consecutive safe collapse, unsafe split
    assert agent_policy.plan_tool_groups([True, True, False, True]) == [[0, 1], [2], [3]]
    assert agent_policy.plan_tool_groups([False, True, True]) == [[0], [1, 2]]
    # empty
    assert agent_policy.plan_tool_groups([]) == []


def run():
    test_normalized_tool_signature_is_stable_for_dict_key_order()
    test_normalized_tool_signature_changes_for_real_argument_change()
    test_dynamic_max_iters_respects_user_configured_ceiling()
    test_repeat_intervention_is_graduated()
    test_repeat_intervention_ignores_calls_outside_window()
    test_repeat_intervention_distinguishes_different_args()
    test_repeat_warning_text_names_the_skill_and_steers()
    test_is_parallel_safe_only_for_never_confirm_pure_reads()
    test_plan_tool_groups_collapses_runs_and_isolates_unsafe()
    print("test_agent_policy OK")
    return True


if __name__ == "__main__":
    run()
