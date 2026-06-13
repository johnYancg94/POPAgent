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


def test_python_signature_preserves_differences_after_long_shared_prefix():
    prefix = "import bpy\n" + ("x = 1\n" * 40)
    left = agent_policy.normalized_tool_signature(
        "dev.run_python", {"code": prefix + "print('left')"}
    )
    right = agent_policy.normalized_tool_signature(
        "dev.run_python", {"code": prefix + "print('right')"}
    )
    assert left != right


def test_python_signature_preserves_indentation():
    left = agent_policy.normalized_tool_signature(
        "dev.run_python", {"code": "if True:\n    print('x')"}
    )
    right = agent_policy.normalized_tool_signature(
        "dev.run_python", {"code": "if True:\nprint('x')"}
    )
    assert left != right


def test_dynamic_max_iters_respects_user_configured_ceiling():
    # simple query, no marker, few tools -> simple cap (5) wins
    assert agent_policy.choose_max_iters("what is selected?", tool_count=2, configured_max=10) == 5
    # complex markers, configured=10 -> trust user (10), not hard cap
    assert agent_policy.choose_max_iters("build a complete material setup then verify it", tool_count=8, configured_max=10) == 10
    # "complex task" has no marker but tool_count=10 -> complex (trust user=5)
    assert agent_policy.choose_max_iters("complex task", tool_count=10, configured_max=5) == 5


def test_dynamic_max_iters_hard_cap_enforced():
    # huge configured + complex -> hard cap (200) bounds prefs tampering
    assert agent_policy.choose_max_iters("build it", tool_count=10, configured_max=9999) == 200
    # simple prompt with huge configured -> simple cap (5) wins before hard cap
    assert agent_policy.choose_max_iters("what is selected?", tool_count=2, configured_max=9999) == 5


def test_dynamic_max_iters_complex_trusts_user_fully():
    # complex + user set 100 -> 100, NOT 20 (long pipeline respect)
    assert agent_policy.choose_max_iters("run the export pipeline", tool_count=1, configured_max=100) == 100
    # complex + 5+ tools, user set 100 -> 100
    assert agent_policy.choose_max_iters("hello", tool_count=8, configured_max=100) == 100
    # Chinese marker
    assert agent_policy.choose_max_iters("分批次导出", tool_count=1, configured_max=100) == 100


def test_dynamic_max_iters_zero_configured_does_not_crash():
    result = agent_policy.choose_max_iters("hello", tool_count=1, configured_max=0)
    assert result >= 1


def test_dynamic_max_iters_simple_uses_cost_saving_cap():
    # 3-4 tools but no marker -> still simple, capped at 5
    assert agent_policy.choose_max_iters("hello", tool_count=3, configured_max=100) == 5
    assert agent_policy.choose_max_iters("hello", tool_count=4, configured_max=100) == 5
    # user set small -> simple cap doesn't push above user setting
    assert agent_policy.choose_max_iters("hello", tool_count=1, configured_max=3) == 3


def test_repeat_intervention_is_graduated():
    sig = ("dev.run_python", '{"code":"x"}')
    outcome = ("error", "exec_error", "SyntaxError")
    # no prior occurrence -> proceed
    history = []
    assert agent_policy.repeat_intervention(history, sig) == "proceed"
    # one prior identical outcome -> warn, but still execute
    history.append((sig, outcome))
    assert agent_policy.repeat_intervention(history, sig) == "warn"
    # two prior identical outcomes -> block only this call
    history.append((sig, outcome))
    assert agent_policy.repeat_intervention(history, sig) == "block"


def test_repeat_intervention_ignores_calls_outside_window():
    sig = ("dev.run_python", '{"code":"x"}')
    other = ("blender.query", "{}")
    outcome = ("error", "exec_error", "SyntaxError")
    # two matches separated past the window of 6 should not count together
    history = [(sig, outcome)] + [(other, ("ok", "", ""))] * 6
    assert agent_policy.repeat_intervention(history, sig, window=6) == "proceed"


def test_repeat_intervention_distinguishes_different_args():
    a = ("dev.run_python", '{"code":"a"}')
    b = ("dev.run_python", '{"code":"b"}')
    outcome = ("error", "exec_error", "SyntaxError")
    history = [(a, outcome), (b, outcome), (a, outcome)]
    assert agent_policy.repeat_intervention(history, b) == "warn"
    history.append((b, outcome))
    assert agent_policy.repeat_intervention(history, b) == "block"


def test_repeat_intervention_requires_same_outcome():
    sig = ("dev.run_python", '{"code":"x"}')
    failed = ("error", "exec_error", "SyntaxError")
    changed = ("error", "exec_error", "AttributeError")
    history = [(sig, failed), (sig, failed), (sig, changed)]
    assert agent_policy.repeat_intervention(history, sig) == "warn"


def test_successful_read_only_repeats_are_not_blocked():
    sig = ("blender.query", "hash")
    success = ("ok", "", "result-hash")
    history = [(sig, success), (sig, success), (sig, success)]

    assert agent_policy.repeat_intervention(history, sig) == "warn"
    assert agent_policy.repeat_intervention(
        history, sig, block_success=True
    ) == "block"


def test_result_signature_uses_exception_tail():
    first = {
        "ok": False,
        "error_kind": "exec_error",
        "error": "Traceback...\nSyntaxError: expected an indented block",
    }
    second = {
        "ok": False,
        "error_kind": "exec_error",
        "error": "Traceback...\nAttributeError: missing socket",
    }
    assert agent_policy.normalized_result_signature(first) != (
        agent_policy.normalized_result_signature(second)
    )


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
    test_python_signature_preserves_differences_after_long_shared_prefix()
    test_python_signature_preserves_indentation()
    test_dynamic_max_iters_respects_user_configured_ceiling()
    test_dynamic_max_iters_hard_cap_enforced()
    test_dynamic_max_iters_complex_trusts_user_fully()
    test_dynamic_max_iters_zero_configured_does_not_crash()
    test_dynamic_max_iters_simple_uses_cost_saving_cap()
    test_repeat_intervention_is_graduated()
    test_repeat_intervention_ignores_calls_outside_window()
    test_repeat_intervention_distinguishes_different_args()
    test_repeat_intervention_requires_same_outcome()
    test_successful_read_only_repeats_are_not_blocked()
    test_result_signature_uses_exception_tail()
    test_repeat_warning_text_names_the_skill_and_steers()
    test_is_parallel_safe_only_for_never_confirm_pure_reads()
    test_plan_tool_groups_collapses_runs_and_isolates_unsafe()
    print("test_agent_policy OK")
    return True


if __name__ == "__main__":
    run()
