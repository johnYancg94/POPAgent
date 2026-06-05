import importlib.util, pathlib
_ROOT = pathlib.Path(__file__).resolve().parents[1]

def _load(mod_name, rel_path):
    spec = importlib.util.spec_from_file_location(mod_name, _ROOT / rel_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

cb = _load("popagent_context_budget", "agent_core/context_budget.py")

def test_estimate_tokens_char_over_4():
    assert cb.estimate_tokens("") == 0
    assert cb.estimate_tokens("abcd") == 1
    assert cb.estimate_tokens("abcde") == 2

def test_history_budget_256k():
    assert cb.history_budget(256000) == 228000

def test_history_budget_1m():
    assert cb.history_budget(1_000_000) == 972000

def test_history_budget_floor():
    assert cb.history_budget(1000) == 4000
