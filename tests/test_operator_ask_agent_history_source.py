"""Static guard for agent history wiring in operator_ask."""

from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[1]


def test_agent_query_defines_history_before_using_it():
    tree = ast.parse((ROOT / "operators" / "operator_ask.py").read_text(encoding="utf-8"))
    agent_query = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "_agent_query"
    )

    first_history_load = None
    first_history_store = None
    for node in ast.walk(agent_query):
        if isinstance(node, ast.Name) and node.id == "history":
            if isinstance(node.ctx, ast.Load):
                first_history_load = min(first_history_load or node.lineno, node.lineno)
            elif isinstance(node.ctx, ast.Store):
                first_history_store = min(first_history_store or node.lineno, node.lineno)

    assert first_history_store is not None
    assert first_history_load is not None
    assert first_history_store < first_history_load


def run():
    test_agent_query_defines_history_before_using_it()
    print("test_operator_ask_agent_history_source OK")
    return True


if __name__ == "__main__":
    run()
