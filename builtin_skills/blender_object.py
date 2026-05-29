"""
Object & collection management skills: delete, duplicate, parent, organize.

These fill the "tidy the outliner" gap in the naming/export pipeline. All use
bpy.data APIs directly (no operators) so they don't depend on viewport context,
except duplicate which copies data-blocks explicitly.

delete is destructive and non-trivial to reverse cleanly, so it is
requires_confirmation="always"; the rest are "first".
"""

from __future__ import annotations
import bpy


def _resolve_objects(context, names):
    if names:
        objs, missing = [], []
        for n in names:
            obj = bpy.data.objects.get(n)
            (objs if obj else missing).append(obj if obj else n)
        return [o for o in objs if o], missing
    return list(context.selected_objects), []


def _handler_delete(context=None, names=None) -> dict:
    if context is None:
        context = bpy.context
    objs, missing = _resolve_objects(context, names)
    if not objs:
        return {
            "ok": False,
            "error_kind": "no_target",
            "error": "No objects to delete (none selected and no valid names given).",
            "missing": missing,
        }
    deleted = [o.name for o in objs]
    for obj in objs:
        bpy.data.objects.remove(obj, do_unlink=True)
    return {"ok": True, "deleted": deleted, "count": len(deleted), "missing": missing}


def _handler_duplicate(context=None, name: str = "", new_name: str = "", linked: bool = False) -> dict:
    if context is None:
        context = bpy.context
    src = bpy.data.objects.get(name) if name else context.active_object
    if src is None:
        return {"ok": False, "error_kind": "not_found", "error": f"Source object not found: {name or '(active)'}"}

    new_obj = src.copy()
    if src.data is not None and not linked:
        new_obj.data = src.data.copy()
    if new_name:
        new_obj.name = new_name

    for coll in src.users_collection:
        coll.objects.link(new_obj)
    if not src.users_collection:
        context.scene.collection.objects.link(new_obj)

    return {"ok": True, "source": src.name, "created": new_obj.name, "linked_data": linked}


def _handler_parent(context=None, child_names=None, parent_name: str = "", keep_transform: bool = True) -> dict:
    if context is None:
        context = bpy.context
    parent = bpy.data.objects.get(parent_name)
    if parent is None:
        return {"ok": False, "error_kind": "not_found", "error": f"Parent object not found: {parent_name}"}

    children, missing = _resolve_objects(context, child_names)
    children = [c for c in children if c is not parent]
    if not children:
        return {"ok": False, "error_kind": "no_target", "error": "No valid child objects.", "missing": missing}

    parented = []
    for child in children:
        matrix = child.matrix_world.copy()
        child.parent = parent
        if keep_transform:
            child.matrix_parent_inverse = parent.matrix_world.inverted()
            child.matrix_world = matrix
        parented.append(child.name)
    return {"ok": True, "parent": parent.name, "children": parented, "missing": missing}


def _handler_organize_collection(context=None, collection_name: str = "", object_names=None) -> dict:
    if context is None:
        context = bpy.context
    if not collection_name:
        return {"ok": False, "error_kind": "invalid_arguments", "error": "collection_name is required."}

    coll = bpy.data.collections.get(collection_name)
    created = False
    if coll is None:
        coll = bpy.data.collections.new(collection_name)
        context.scene.collection.children.link(coll)
        created = True

    objs, missing = _resolve_objects(context, object_names)
    moved = []
    for obj in objs:
        for c in list(obj.users_collection):
            c.objects.unlink(obj)
        coll.objects.link(obj)
        moved.append(obj.name)

    return {
        "ok": True,
        "collection": coll.name,
        "created_collection": created,
        "moved": moved,
        "count": len(moved),
        "missing": missing,
    }


DELETE_OBJECTS = {
    "name": "blender.object.delete",
    "description": (
        "Delete objects from the scene. Pass 'names' for explicit objects, or omit "
        "to delete the current selection. This permanently removes the objects and "
        "their unused data."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "names": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Object names to delete. Omit to delete the current selection.",
            },
        },
        "required": [],
    },
    "owner": "builtin.object",
    "handler": _handler_delete,
    "metadata": {
        "modifies_scene": True,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": True,
        "requires_confirmation": "always",
    },
}

DUPLICATE_OBJECT = {
    "name": "blender.object.duplicate",
    "description": (
        "Duplicate an object (defaults to the active object). By default makes an "
        "independent copy of the mesh data; set linked=true to share data. The copy "
        "is linked into the same collection(s) as the source."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Source object name. Defaults to active object."},
            "new_name": {"type": "string", "description": "Optional name for the duplicate."},
            "linked": {"type": "boolean", "description": "Share mesh data instead of copying it (default false)."},
        },
        "required": [],
    },
    "owner": "builtin.object",
    "handler": _handler_duplicate,
    "metadata": {
        "modifies_scene": True,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": True,
        "requires_confirmation": "first",
    },
}

PARENT_OBJECTS = {
    "name": "blender.object.parent",
    "description": (
        "Parent one or more child objects to a parent object, preserving world "
        "transform by default. Pass child_names explicitly or omit to use the "
        "current selection as children."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "child_names": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Child object names. Omit to use the current selection.",
            },
            "parent_name": {"type": "string", "description": "Name of the parent object."},
            "keep_transform": {"type": "boolean", "description": "Preserve world transform (default true)."},
        },
        "required": ["parent_name"],
    },
    "owner": "builtin.object",
    "handler": _handler_parent,
    "metadata": {
        "modifies_scene": True,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": True,
        "requires_confirmation": "first",
    },
}

ORGANIZE_COLLECTION = {
    "name": "blender.collection.organize",
    "description": (
        "Move objects into a collection, creating the collection under the scene "
        "root if it does not exist. Objects are unlinked from their current "
        "collections first. Pass object_names or omit to use the current selection."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "collection_name": {"type": "string", "description": "Target collection name (created if missing)."},
            "object_names": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Objects to move. Omit to use the current selection.",
            },
        },
        "required": ["collection_name"],
    },
    "owner": "builtin.object",
    "handler": _handler_organize_collection,
    "metadata": {
        "modifies_scene": True,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": True,
        "requires_confirmation": "first",
    },
}
