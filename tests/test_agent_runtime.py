"""Tests for agent.runtime_info — the skill that lets the agent fetch its own
authoritative provider/model/context facts instead of guessing.

The skill module does relative imports (`from ..agent_core import ...`), so it
can't be imported standalone under bare pytest. We load it via importlib with a
stub package so the handler logic can be exercised directly, and add static
wiring guards on top.
"""

import importlib.util
import os
import sys
import types
from pathlib import Path


ROOT = Path(os.environ.get("POPAGENT_ROOT", str(Path(__file__).resolve().parents[1])))


def _read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def _load_runtime_module():
    """Load agent_runtime.py with stubbed sibling packages (no bpy)."""
    pkg = types.ModuleType("popagent_rt_pkg")
    pkg.__path__ = []
    sys.modules["popagent_rt_pkg"] = pkg

    # stub ..agent_core.context_budget
    agent_core = types.ModuleType("popagent_rt_pkg.agent_core")
    agent_core.__path__ = []
    cb = types.ModuleType("popagent_rt_pkg.agent_core.context_budget")
    cb.history_budget = lambda w, **k: max(4000, w - 8000 - 20000)
    agent_core.context_budget = cb
    sys.modules["popagent_rt_pkg.agent_core"] = agent_core
    sys.modules["popagent_rt_pkg.agent_core.context_budget"] = cb

    # stub ..utils.usage_stats.get_current_model
    utils = types.ModuleType("popagent_rt_pkg.utils")
    utils.__path__ = []
    us = types.ModuleType("popagent_rt_pkg.utils.usage_stats")

    def _get_current_model(prefs):
        org = getattr(prefs, "llm_organization", "")
        return {
            "openai": getattr(prefs, "open_ai_model", ""),
            "mimo": getattr(prefs, "mimo_model", ""),
            "deepseek": getattr(prefs, "deepseek_model", ""),
            "anthropic": getattr(prefs, "anthropic_model", ""),
        }.get(org, "")

    us.get_current_model = _get_current_model
    utils.usage_stats = us
    sys.modules["popagent_rt_pkg.utils"] = utils
    sys.modules["popagent_rt_pkg.utils.usage_stats"] = us

    spec = importlib.util.spec_from_file_location(
        "popagent_rt_pkg.builtin_skills.agent_runtime",
        ROOT / "builtin_skills" / "agent_runtime.py",
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class _Prefs:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class _Ctx:
    """A context whose .preferences.addons['POPAgent'].preferences is prefs."""

    def __init__(self, prefs):
        addon = types.SimpleNamespace(preferences=prefs)
        self.preferences = types.SimpleNamespace(addons={"POPAgent": addon})


def test_reports_active_deepseek_model_not_default_anthropic():
    mod = _load_runtime_module()
    prefs = _Prefs(
        llm_organization="deepseek",
        deepseek_model="deepseek-v4-pro",
        anthropic_model="claude-sonnet-4-6",  # default-valued field; must be ignored
        agent_context_1m_enabled=False,
        agent_context_window=256000,
    )
    out = mod._handler_runtime_info(context=_Ctx(prefs))
    assert out["ok"] is True
    assert out["provider"] == "deepseek"
    assert out["model"] == "deepseek-v4-pro"
    assert "claude" not in out["model"]


def test_1m_flag_drives_effective_window():
    mod = _load_runtime_module()
    prefs = _Prefs(
        llm_organization="deepseek",
        deepseek_model="deepseek-v4-pro",
        agent_context_1m_enabled=True,
        agent_context_window=256000,
    )
    out = mod._handler_runtime_info(context=_Ctx(prefs))
    assert out["context_1m_enabled"] is True
    assert out["effective_context_window"] == 1_000_000
    assert out["configured_context_window"] == 256000
    assert out["history_token_budget"] == max(4000, 1_000_000 - 8000 - 20000)


def test_no_1m_uses_configured_window():
    mod = _load_runtime_module()
    prefs = _Prefs(
        llm_organization="anthropic",
        anthropic_model="claude-sonnet-4-6",
        agent_context_1m_enabled=False,
        agent_context_window=200000,
    )
    out = mod._handler_runtime_info(context=_Ctx(prefs))
    assert out["model"] == "claude-sonnet-4-6"
    assert out["effective_context_window"] == 200000


def test_prefs_unavailable_returns_error_not_guess():
    mod = _load_runtime_module()
    out = mod._handler_runtime_info(context=types.SimpleNamespace(preferences=None))
    assert out["ok"] is False
    assert out["error_kind"] == "prefs_unavailable"


def test_skill_is_read_only_and_never_confirms():
    meta = _load_runtime_module().RUNTIME_INFO["metadata"]
    assert meta["modifies_scene"] is False
    assert meta["writes_files"] is False
    assert meta["requires_confirmation"] == "never"
    assert meta["requires_main_thread"] is False


def test_runtime_info_wired_into_builtins():
    text = _read("builtin_skills/__init__.py")
    assert "RUNTIME_INFO" in text
    assert "agent_runtime" in text


def test_identity_rule_in_prompt_and_references_tool():
    text = _read("agent_core/prompts.py")
    assert "RULE_IDENTITY" in text
    assert "agent.runtime_info" in text
    # The rule must tell the model NOT to read anthropic_model directly.
    assert "anthropic_model" in text
