from .blender_query import QUERY_SCENE, LIST_ADDONS, VIEWPORT_SCREENSHOT
from .blender_api_docs import BLENDER_API_SEARCH
from .blender_select import SELECT_OBJECTS, SET_ACTIVE
from .dev_skills import RUN_PYTHON
from ..agent_core import skill_registry

_BUILTIN_SKILLS = [
    QUERY_SCENE,
    LIST_ADDONS,
    VIEWPORT_SCREENSHOT,
    BLENDER_API_SEARCH,
    SELECT_OBJECTS,
    SET_ACTIVE,
    RUN_PYTHON,
]


def register():
    for skill in _BUILTIN_SKILLS:
        skill_registry.register_skill(skill)


def unregister():
    skill_registry.unregister_namespace("builtin")
