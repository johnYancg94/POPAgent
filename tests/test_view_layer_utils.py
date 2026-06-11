"""Pure Python tests for view-layer collection chain resolution."""

from pathlib import Path
import importlib.util


ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "view_layer_utils", ROOT / "utils" / "view_layer_utils.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
find_layer_collection_chain = _mod.find_layer_collection_chain


class _Collection:
    def __init__(self, name, object_names=()):
        self.name = name
        self.objects = set(object_names)


class _LayerCollection:
    """Minimal duck-typed stand-in for bpy LayerCollection."""

    def __init__(self, name, object_names=(), children=()):
        self.collection = _Collection(name, object_names)
        self.children = list(children)


def test_returns_none_when_object_absent():
    root = _LayerCollection("Scene Collection", children=[_LayerCollection("A")])
    assert find_layer_collection_chain(root, "Ghost") is None


def test_finds_object_in_root():
    root = _LayerCollection("Scene Collection", object_names=["Cube"])
    chain = find_layer_collection_chain(root, "Cube")
    assert [lc.collection.name for lc in chain] == ["Scene Collection"]


def test_returns_full_ancestor_chain_for_nested_object():
    leaf = _LayerCollection("Inner", object_names=["Suzanne"])
    mid = _LayerCollection("Outer", children=[leaf])
    root = _LayerCollection("Scene Collection", children=[mid])
    chain = find_layer_collection_chain(root, "Suzanne")
    assert [lc.collection.name for lc in chain] == ["Scene Collection", "Outer", "Inner"]


def test_first_matching_branch_wins():
    branch_a = _LayerCollection("A", object_names=["Cube"])
    branch_b = _LayerCollection("B", object_names=["Cube"])
    root = _LayerCollection("Scene Collection", children=[branch_a, branch_b])
    chain = find_layer_collection_chain(root, "Cube")
    assert [lc.collection.name for lc in chain] == ["Scene Collection", "A"]


def test_handles_missing_collection_attr():
    class _Bare:
        children = []

    assert find_layer_collection_chain(_Bare(), "Cube") is None


def run():
    test_returns_none_when_object_absent()
    test_finds_object_in_root()
    test_returns_full_ancestor_chain_for_nested_object()
    test_first_matching_branch_wins()
    test_handles_missing_collection_attr()
    print("test_view_layer_utils OK")
    return True


if __name__ == "__main__":
    run()
