# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.

from bpy.types import Operator, Context


RENDER_PREP_PROMPT = """请启动并使用 $prepare-renderset-contexts，按照 RenderSet Pro Agent 工作流准备当前 Blender 场景的渲染 Context。

目标：
1. 调用 renderset.prepare；不要使用 dev.run_python，不要手写临时 Python，不要启动渲染。
2. 自动识别 XX岛 前缀、区域、相机、建筑、前层、地形、水面、粒子实例、资产、杂项。
3. 创建或更新完整预览、整体地形、地形_shadow、区域完整预览、区域_shadow、单体建筑、前层 Context。
4. 正确设置 Include in Render All、Exclude、hide_render、Holdout、Indirect Only、采样、1920x1920、分辨率倍率、Render Region；Material Override 保持为空，不修改 Color Management。
5. 识别并迁移高置信旧 Context；重复候选只报告并取消 Render All，不自动删除。
6. 全量切换回读审计，通过后保存 .blend；失败整批回滚。

请把裁切区域异常的建筑放在回答最前面，并使用 ⚠️ 提醒符号增强提醒；然后用简短报告说明 created、updated、migrated、duplicate_contexts、unmatched_contexts、warnings 和保存状态。"""


class CHAT_COMPANION_OT_set_render_prep_prompt(Operator):
    bl_idname = "chat_companion.set_render_prep_prompt"
    bl_label = "准备渲染"
    bl_description = "Load the island RenderSet preparation prompt into the input field"
    bl_options = {"REGISTER", "INTERNAL"}

    def execute(self, context: Context):
        props = context.scene.chat_companion_properties
        props.user_prompt = RENDER_PREP_PROMPT
        return {"FINISHED"}
