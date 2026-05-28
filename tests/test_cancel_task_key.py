"""Pure Python guard for async operator task registry keys."""

from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[1]


def test_async_loop_uses_class_bl_idname_for_task_registry():
    text = (ROOT / "utils" / "async_loop.py").read_text(encoding="utf-8")

    assert "def _operator_task_key" in text
    assert "getattr(type(operator), \"bl_idname\", None)" in text
    assert "cc_globals.active_async_tasks[task_key]" in text


def test_cancel_operator_looks_up_chat_companion_ask_idname():
    text = (ROOT / "operators" / "operator_cancel.py").read_text(encoding="utf-8")
    tree = ast.parse(text)
    constants = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }

    assert "chat_companion.ask" in constants
    assert "props.waiting_for_answer = False" in text
    assert "props.is_streaming = False" in text


def run():
    test_async_loop_uses_class_bl_idname_for_task_registry()
    test_cancel_operator_looks_up_chat_companion_ask_idname()
    print("test_cancel_task_key OK")
    return True


if __name__ == "__main__":
    run()
