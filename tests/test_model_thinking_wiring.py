"""Static guards for model timeout and thinking UI wiring."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_operator_ask_wraps_provider_waits_with_model_timeout():
    text = (ROOT / "operators" / "operator_ask.py").read_text(encoding="utf-8")

    assert "ModelServerTimeoutError" in text
    assert "run_with_model_timeout" in text
    assert "build_httpx_timeout" in text
    assert "_set_model_thinking" in text
    assert "Model is thinking" in text
    assert "Model Server Busy" in text
    assert "except ModelServerTimeoutError:" in text


def test_output_panel_shows_waiting_string_while_waiting_for_answer():
    text = (ROOT / "panels" / "panel_output.py").read_text(encoding="utf-8")

    assert "props.waiting_for_answer and props.waiting_string" in text


def run():
    test_operator_ask_wraps_provider_waits_with_model_timeout()
    test_output_panel_shows_waiting_string_while_waiting_for_answer()
    print("test_model_thinking_wiring OK")
    return True


if __name__ == "__main__":
    run()
