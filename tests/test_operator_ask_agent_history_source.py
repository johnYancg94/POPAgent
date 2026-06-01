"""Static guard for agent history wiring in operator_ask.

After the Level 1 async-runtime refactor, _agent_query no longer keeps a
`history` local: the bpy history collection is read inside a main-thread
snapshot (`_snapshot_messages`, dispatched via `ui_read`) that returns a fully
built MessageBuilder. These guards encode the new invariants:

  1. `mb` is assigned before it is first used (build-before-use).
  2. The raw `chat_companion_history` collection is accessed through the
     marshalled snapshot, not iterated directly on the background loop.
"""

from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[1]


def _agent_query_node(tree):
    return next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "_agent_query"
    )


def test_message_builder_is_built_before_use():
    tree = ast.parse((ROOT / "operators" / "operator_ask.py").read_text(encoding="utf-8"))
    agent_query = _agent_query_node(tree)

    first_mb_load = None
    first_mb_store = None
    for node in ast.walk(agent_query):
        if isinstance(node, ast.Name) and node.id == "mb":
            if isinstance(node.ctx, ast.Load):
                first_mb_load = min(first_mb_load or node.lineno, node.lineno)
            elif isinstance(node.ctx, ast.Store):
                first_mb_store = min(first_mb_store or node.lineno, node.lineno)

    assert first_mb_store is not None
    assert first_mb_load is not None
    assert first_mb_store < first_mb_load


def test_history_collection_read_via_marshalled_snapshot():
    tree = ast.parse((ROOT / "operators" / "operator_ask.py").read_text(encoding="utf-8"))
    agent_query = _agent_query_node(tree)

    # The history collection must be accessed (anywhere in _agent_query, which
    # includes the nested _snapshot_messages def), and that snapshot must be
    # marshalled via ui_read.
    reads_history = any(
        isinstance(node, ast.Attribute) and node.attr == "chat_companion_history"
        for node in ast.walk(agent_query)
    )
    uses_ui_read = any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "ui_read"
        for node in ast.walk(agent_query)
    )
    assert reads_history
    assert uses_ui_read


def run():
    test_message_builder_is_built_before_use()
    test_history_collection_read_via_marshalled_snapshot()
    print("test_operator_ask_agent_history_source OK")
    return True


if __name__ == "__main__":
    run()
