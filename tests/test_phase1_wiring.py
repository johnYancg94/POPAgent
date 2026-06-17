"""Static guards for Phase 1 stability wiring."""

from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[1]


def _tree(path):
    return ast.parse((ROOT / path).read_text(encoding="utf-8"))


def test_executor_validates_arguments_before_main_thread_dispatch():
    tree = _tree("agent_core/executor.py")
    run_fn = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "run"
    )

    validate_line = None
    run_on_main_line = None
    for node in ast.walk(run_fn):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == "validate_arguments":
                validate_line = min(validate_line or node.lineno, node.lineno)
            if isinstance(func, ast.Name) and func.id == "run_on_main":
                run_on_main_line = min(run_on_main_line or node.lineno, node.lineno)

    assert validate_line is not None
    assert run_on_main_line is not None
    assert validate_line < run_on_main_line


def test_operator_ask_uses_retry_helper_for_provider_requests():
    text = (ROOT / "operators" / "operator_ask.py").read_text(encoding="utf-8")

    assert "run_with_retries" in text
    assert "_post_with_retries" in text
    assert "RetryPolicy" in text


def test_cancel_operator_is_registered_and_visible_while_waiting():
    init_text = (ROOT / "__init__.py").read_text(encoding="utf-8")
    prompt_text = (ROOT / "panels" / "panel_prompt.py").read_text(encoding="utf-8")

    assert "CHAT_COMPANION_OT_cancel_request" in init_text
    assert "chat_companion.cancel_request" in prompt_text
    assert "props.waiting_for_answer" in prompt_text


def test_connection_test_button_is_inline_with_model_help():
    prompt_text = (ROOT / "panels" / "panel_prompt.py").read_text(encoding="utf-8")

    assert "test_row: UILayout = layout.row(align=True)" not in prompt_text
    assert 'text="Test Connection"' not in prompt_text
    for model_prop in (
        "open_ai_model",
        "mimo_model",
        "deepseek_model",
        "minimax_model",
    ):
        model_section = prompt_text.split(
            f'.prop(prefs, "{model_prop}", text="")', 1
        )[1].split("model_info_link =", 1)[0]
        assert "draw_connection_test_button(" in model_section


def test_http_error_handler_uses_exception_response_not_unbound_local():
    text = (ROOT / "operators" / "operator_ask.py").read_text(encoding="utf-8")
    http_error_block = text.split("except httpx.HTTPError as e:", 1)[1].split(
        "except httpx.StreamError as e:", 1
    )[0]

    assert "http_response = getattr(e, \"response\", None)" in http_error_block
    assert "status_code = getattr(http_response, \"status_code\", 0)" in http_error_block
    assert "response.status_code" not in http_error_block


def run():
    test_executor_validates_arguments_before_main_thread_dispatch()
    test_operator_ask_uses_retry_helper_for_provider_requests()
    test_cancel_operator_is_registered_and_visible_while_waiting()
    test_connection_test_button_is_inline_with_model_help()
    test_http_error_handler_uses_exception_response_not_unbound_local()
    print("test_phase1_wiring OK")
    return True


if __name__ == "__main__":
    run()
