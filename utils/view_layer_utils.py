"""Pure helpers for reasoning about view-layer collection trees (bpy-free)."""

from __future__ import annotations


def find_layer_collection_chain(layer_collection, object_name: str):
    """Return the layer collections from root down to the one whose collection
    directly contains ``object_name``, or ``None`` if the object is in no
    collection under this tree.

    Duck-typed so it can be unit tested without bpy: each node must expose
    ``.collection.objects`` (supporting ``name in objects``) and ``.children``
    (an iterable of child nodes). The returned chain includes every ancestor so
    callers can clear the whole ``exclude`` cascade, not just the leaf.
    """
    collection = getattr(layer_collection, "collection", None)
    if collection is not None:
        objects = getattr(collection, "objects", None)
        if objects is not None and object_name in objects:
            return [layer_collection]
    for child in getattr(layer_collection, "children", []) or []:
        sub = find_layer_collection_chain(child, object_name)
        if sub:
            return [layer_collection] + sub
    return None
