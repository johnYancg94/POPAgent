"""Pure Python tests for provider image-input capability gates."""

from pathlib import Path
import importlib.util
import sys
import types


ROOT = Path(__file__).resolve().parents[1]
PROVIDERS = ROOT / "providers"

pkg = types.ModuleType("providers")
pkg.__path__ = [str(PROVIDERS)]
sys.modules["providers"] = pkg

for name in ("base", "openai_compat", "anthropic"):
    spec = importlib.util.spec_from_file_location(
        f"providers.{name}", PROVIDERS / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"providers.{name}"] = module
    spec.loader.exec_module(module)

OpenAICompatProvider = sys.modules["providers.openai_compat"].OpenAICompatProvider
AnthropicProvider = sys.modules["providers.anthropic"].AnthropicProvider


class _Prefs:
    open_ai_model = ""
    deepseek_model = ""
    minimax_model = ""


def test_non_deepseek_openai_compatible_models_default_to_image_input():
    prefs = _Prefs()
    provider = OpenAICompatProvider("openai")

    for model in ("gpt-4o", "custom-vision-model", "future-model"):
        prefs.open_ai_model = model
        assert provider.supports_image_input(prefs), model


def test_deepseek_does_not_support_image_input():
    prefs = _Prefs()
    prefs.deepseek_model = "deepseek-chat"

    assert not OpenAICompatProvider("deepseek").supports_image_input(prefs)


def test_minimax_supports_image_input():
    prefs = _Prefs()
    prefs.minimax_model = "MiniMax-M3"

    assert AnthropicProvider().supports_image_input(prefs)


def test_minimax_unknown_model_defaults_to_no_image_input():
    """Empty / unknown model names must not silently claim vision support."""
    prefs = _Prefs()
    prefs.minimax_model = ""

    assert not AnthropicProvider().supports_image_input(prefs)


def run():
    test_non_deepseek_openai_compatible_models_default_to_image_input()
    test_deepseek_does_not_support_image_input()
    test_minimax_supports_image_input()
    test_minimax_unknown_model_defaults_to_no_image_input()
    print("test_provider_vision_support OK")
    return True


if __name__ == "__main__":
    run()
