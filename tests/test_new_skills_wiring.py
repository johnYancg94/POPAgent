"""Static guards for the P0-P2 capability skills added on top of the node set.

These modules import bpy, so we verify them by reading source text (the same
approach as test_blender_nodes_wiring). The checks below encode the invariants
that are easy to break silently.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def test_all_new_skills_registered_in_init():
    text = _read("builtin_skills/__init__.py")
    for symbol in (
        "HEALTH_CHECK", "SAVE_FILE", "UNDO", "REDO",
        "TRANSFORM_SET", "TRANSFORM_APPLY", "TRANSFORM_SET_ORIGIN",
        "DELETE_OBJECTS", "DUPLICATE_OBJECT", "PARENT_OBJECTS",
        "ORGANIZE_COLLECTION", "LIST_SKILLS", "OBJECT_RESULTS",
    ):
        assert symbol in text, f"{symbol} not wired into builtin_skills/__init__.py"


def test_skill_names_use_blender_agent_domains():
    names = {
        "builtin_skills/blender_mesh.py": "blender.mesh.health_check",
        "builtin_skills/blender_file.py": "blender.file.save",
        "builtin_skills/blender_edit.py": "blender.edit.undo",
        "builtin_skills/blender_transform.py": "blender.transform.set",
        "builtin_skills/blender_object.py": "blender.object.delete",
        "builtin_skills/blender_object_results.py": "blender.object_results",
        "builtin_skills/agent_meta.py": "agent.list_skills",
    }
    for path, name in names.items():
        assert name in _read(path), f"{name} missing from {path}"


def test_undo_redo_must_not_be_undoable():
    # If undo/redo were undoable=True the executor would push a fresh undo step
    # right after undoing, corrupting the stack.
    text = _read("builtin_skills/blender_edit.py")
    assert '"undoable": False' in text
    assert '"undoable": True' not in text


def test_file_save_and_delete_require_confirmation_always():
    save_text = _read("builtin_skills/blender_file.py")
    assert '"requires_confirmation": "always"' in save_text
    assert '"writes_files": True' in save_text

    obj_text = _read("builtin_skills/blender_object.py")
    # delete is the destructive one; its block (up to the next skill def) must be "always"
    delete_block = obj_text.split("DELETE_OBJECTS = {", 1)[1].split("DUPLICATE_OBJECT = {", 1)[0]
    assert '"requires_confirmation": "always"' in delete_block


def test_meta_and_diagnostic_skills_are_read_only():
    for path in (
        "builtin_skills/agent_meta.py",
        "builtin_skills/blender_mesh.py",
        "builtin_skills/blender_object_results.py",
    ):
        text = _read(path)
        assert '"modifies_scene": False' in text
        assert '"writes_files": False' in text
        assert '"requires_confirmation": "never"' in text


def test_handlers_do_not_wrap_run_on_main():
    # Handlers already execute on the main thread (dispatched by the executor),
    # so they must call bpy directly and never re-wrap run_on_main.
    for path in (
        "builtin_skills/blender_mesh.py",
        "builtin_skills/blender_file.py",
        "builtin_skills/blender_edit.py",
        "builtin_skills/blender_transform.py",
        "builtin_skills/blender_object.py",
    ):
        assert "run_on_main" not in _read(path), f"{path} must not call run_on_main"


def run():
    test_all_new_skills_registered_in_init()
    test_skill_names_use_blender_agent_domains()
    test_undo_redo_must_not_be_undoable()
    test_file_save_and_delete_require_confirmation_always()
    test_meta_and_diagnostic_skills_are_read_only()
    test_handlers_do_not_wrap_run_on_main()
    print("test_new_skills_wiring OK")
    return True


if __name__ == "__main__":
    run()
