from .blender_query import QUERY_SCENE, LIST_ADDONS, VIEWPORT_SCREENSHOT
from .blender_api_docs import BLENDER_API_SEARCH
from .web_search import WEB_SEARCH
from .blender_select import SELECT_OBJECTS, SET_ACTIVE
from .blender_object_results import OBJECT_RESULTS
from .blender_nodes import (
    SEARCH_NODE_TYPES,
    INSPECT_MATERIAL_NODES,
    VALIDATE_MATERIAL_NODES,
    CONNECT_PBR_TEXTURES,
    ADD_MATERIAL_NODE,
    CONNECT_MATERIAL_NODES,
    SET_MATERIAL_NODE_INPUT,
    INSPECT_GEOMETRY_NODES,
    VALIDATE_GEOMETRY_NODES,
    ENSURE_BASIC_GEOMETRY_NODES,
    ADD_GEOMETRY_NODE,
    CONNECT_GEOMETRY_NODES,
    SET_GEOMETRY_NODE_INPUT,
)
from .blender_mesh import HEALTH_CHECK
from .blender_file import SAVE_FILE
from .blender_edit import UNDO, REDO
from .blender_transform import TRANSFORM_SET, TRANSFORM_APPLY, TRANSFORM_SET_ORIGIN
from .blender_object import (
    DELETE_OBJECTS,
    DUPLICATE_OBJECT,
    PARENT_OBJECTS,
    ORGANIZE_COLLECTION,
)
from .agent_meta import LIST_SKILLS
from .agent_skill_activation import ACTIVATE_AGENT_SKILL
from .agent_runtime import RUNTIME_INFO
from .agent_interact import ASK_HUMAN
from .dev_skills import RUN_PYTHON
from .renderset_tools import RENDERSET_INSPECT, RENDERSET_PREPARE, RENDERSET_AUDIT
from ..agent_core import agent_skill_registry, skill_registry
from pathlib import Path

_BUILTIN_SKILLS = [
    QUERY_SCENE,
    LIST_ADDONS,
    VIEWPORT_SCREENSHOT,
    BLENDER_API_SEARCH,
    WEB_SEARCH,
    SELECT_OBJECTS,
    SET_ACTIVE,
    OBJECT_RESULTS,
    SEARCH_NODE_TYPES,
    INSPECT_MATERIAL_NODES,
    VALIDATE_MATERIAL_NODES,
    CONNECT_PBR_TEXTURES,
    ADD_MATERIAL_NODE,
    CONNECT_MATERIAL_NODES,
    SET_MATERIAL_NODE_INPUT,
    INSPECT_GEOMETRY_NODES,
    VALIDATE_GEOMETRY_NODES,
    ENSURE_BASIC_GEOMETRY_NODES,
    ADD_GEOMETRY_NODE,
    CONNECT_GEOMETRY_NODES,
    SET_GEOMETRY_NODE_INPUT,
    HEALTH_CHECK,
    SAVE_FILE,
    UNDO,
    REDO,
    TRANSFORM_SET,
    TRANSFORM_APPLY,
    TRANSFORM_SET_ORIGIN,
    DELETE_OBJECTS,
    DUPLICATE_OBJECT,
    PARENT_OBJECTS,
    ORGANIZE_COLLECTION,
    LIST_SKILLS,
    ACTIVATE_AGENT_SKILL,
    RUNTIME_INFO,
    ASK_HUMAN,
    RUN_PYTHON,
    RENDERSET_INSPECT,
    RENDERSET_PREPARE,
    RENDERSET_AUDIT,
]

_BUNDLED_AGENT_SKILLS = (
    Path(__file__).with_name("resources"),
)


def register():
    for skill in _BUILTIN_SKILLS:
        skill_registry.register_skill(skill)
    for root in _BUNDLED_AGENT_SKILLS:
        agent_skill_registry.registry.register_bundled_root("popagent", root)


def unregister():
    skill_registry.unregister_namespace("builtin")
    agent_skill_registry.registry.unregister_bundled_root("popagent")
