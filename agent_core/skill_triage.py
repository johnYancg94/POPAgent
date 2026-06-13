"""Callable Tool 两级分诊：超阈值时核心常驻 + 非核心降目录。纯逻辑，不 import bpy。

executor 按 name 查 registry 不受 tools 数组限制，故非核心 skill 不进 tools
仍可被调用——模型先 agent.list_skills(owner=X) 取 schema 再调。"""
from __future__ import annotations

# 默认阈值。现网注册 33 builtin + 28 poptools = 61，留余量以免单加一个 skill
# 或 multimodal 开关（screenshot skill 进/出）就把分诊从"关"翻成"开"。
DEFAULT_TRIAGE_THRESHOLD = 80

CORE_SKILL_NAMES = frozenset({
    "agent.list_skills",
    "agent.activate_skill",
    "agent.ask_human",
    "blender.query_scene",
    "blender.list_addons",
    "blender.select_objects",
    "blender.set_active",
    "blender.api_search",
    "web.search",
    "renderset.inspect",
    "renderset.prepare",
    "renderset.audit",
})


def should_triage(skill_count: int, threshold: int) -> bool:
    return skill_count > threshold


def partition_skills(skills: list[dict], *, threshold: int):
    """返回 (exposed_skills, catalog_briefs)。

    不触发 → (全部, [])，行为同现在。
    触发 → (核心常驻 skill, 非核心 skill 列表用作目录)。"""
    if not should_triage(len(skills), threshold):
        return list(skills), []
    exposed = [s for s in skills if s.get("name") in CORE_SKILL_NAMES]
    catalog = [s for s in skills if s.get("name") not in CORE_SKILL_NAMES]
    return exposed, catalog


def render_catalog(catalog_briefs: list[dict]) -> str:
    """把非核心 skill 渲染成注入 system prompt 的目录文本（按 owner 分组）。"""
    if not catalog_briefs:
        return ""
    by_owner: dict[str, list[dict]] = {}
    for s in catalog_briefs:
        by_owner.setdefault(s.get("owner", "unknown"), []).append(s)

    lines = [
        "Additional callable tools are available but not listed directly this "
        "turn (to save context). To use one, first call `agent.list_skills` with "
        "the owner prefix to fetch its full schema, then call it by name.",
        "",
        "Available callable-tool groups:",
    ]
    for owner in sorted(by_owner):
        lines.append(f"- {owner}:")
        for s in sorted(by_owner[owner], key=lambda x: x.get("name", "")):
            desc = (s.get("description", "") or "").strip().replace("\n", " ")
            lines.append(f"    - {s.get('name','')}: {desc[:100]}")
    return "\n".join(lines)
