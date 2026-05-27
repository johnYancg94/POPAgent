from .blender_query import QUERY_SCENE, LIST_ADDONS, VIEWPORT_SCREENSHOT
from .blender_select import SELECT_OBJECTS, SET_ACTIVE
from .dev_skills import RUN_PYTHON
from ..agent_core import skill_registry

_BUILTIN_SKILLS = [
    QUERY_SCENE,
    LIST_ADDONS,
    VIEWPORT_SCREENSHOT,
    SELECT_OBJECTS,
    SET_ACTIVE,
]


def register():
    for skill in _BUILTIN_SKILLS:
        skill_registry.register_skill(skill)
    _maybe_register_dev_skills()


def _maybe_register_dev_skills():
    """Register dev.run_python only when developer_mode is enabled."""
    try:
        import bpy
        prefs = bpy.context.preferences.addons[__package__.split(".")[0]].preferences
        if getattr(prefs, "developer_mode", False):
            skill_registry.register_skill(RUN_PYTHON)
    except Exception:
        pass  # prefs not yet available during first load; operator_ask re-checks live


def unregister():
    skill_registry.unregister_namespace("builtin")
