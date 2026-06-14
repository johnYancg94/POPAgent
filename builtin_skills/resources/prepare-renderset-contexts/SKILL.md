---
name: prepare-renderset-contexts
description: Prepare, create, repair, and validate RenderSet Pro contexts in Blender through Blender MCP. Use for Chinese collection hierarchies, normal/shadow/single-building/front-layer render tasks, Include in Render All, Cycles sampling, orthographic resolution scaling, Render Region, and render-readiness audits. Never starts long renders.
license: MIT
compatibility: Blender 5.1+, RenderSet Pro 2.x, and Blender Python access such as Blender MCP
metadata:
  author: t7597-team
  version: "2.3.0"
---

# Prepare RenderSet Pro Contexts

Turn an artist-maintained Chinese collection hierarchy into reliable RenderSet Pro contexts through POPAgent's deterministic native tools. The Skill defines the workflow contract; the tools perform all Blender and RenderSet operations.

## Safety Boundary

- Never click `Render All`, call `bpy.ops.render.render`, or wait for a long render.
- Never delete contexts, collections, or objects unless the user explicitly requests it.
- Never move suspicious objects between collections automatically.
- Never edit RenderSet Pro's serialized `synced_data_json` directly.
- Never modify Color Management. Read and report its current state only.
- Keep `ViewLayer.material_override = None`.
- Preserve plugin-owned structures such as `Cutters`.
- Prefer updating a same-name context; create only when it is missing.
- Migrate exactly one high-confidence legacy semantic match to the canonical
  name. Never automatically delete duplicate candidates.
- Never use `dev.run_python` for this workflow while the native RenderSet tools are available.

## Load References

Read only the references needed for the current task:

- Context taxonomy and collection states: [references/context-rules.md](references/context-rules.md)
- Render Properties, sampling, resolution, and Render Region: [references/render-settings.md](references/render-settings.md)
- Validation and reporting contract: [references/validation-and-reporting.md](references/validation-and-reporting.md)

## Workflow

### 1. Route Through the Available Host

- In POPAgent, call `renderset.inspect`, `renderset.prepare`, or
  `renderset.audit` directly.
- In Codex with Blender MCP, use one `mcp__blender.execute_blender_code` call
  to import the matching handler from
  `POPAgent.builtin_skills.renderset_tools` and return its JSON result:

```python
import json
from POPAgent.builtin_skills import renderset_tools

result = renderset_tools._handler_prepare(
    context=bpy.context,
    decisions={},
)
print("POPAGENT_RENDERSET_RESULT=" + json.dumps(result, ensure_ascii=False))
```

Use `_handler_inspect`, `_handler_prepare`, or `_handler_audit` to match the
requested operation. Pass user answers through `decisions`. Do not copy,
reimplement, or modify RenderSet business logic inside the MCP call.

If neither native RenderSet tools nor Blender MCP are available, report the
connection blocker. Do not fall back to improvised scene-editing code.

### 2. Choose One Native Operation

- Use `renderset.prepare` for normal render-preparation requests. It performs inspection, preparation, independent audit, restoration, and save in one call.
- Use `renderset.inspect` only when the user asks to preview the proposed plan or diagnose hierarchy ambiguity without changing the scene.
- Use `renderset.audit` only when the user asks to check an existing preparation without changing or saving settings.

Do not call `dev.run_python`, manually import helper scripts, or reconstruct RenderSet internals.

### 3. Handle Ambiguity

If a tool returns `status: needs_input`, ask one concise question containing all `blocking_ambiguities`. Call the same tool again with a `decisions` object containing the user's answers. Do not make partial scene changes while waiting.

Recognized decisions:

```json
{
  "project_prefix": "项目名称",
  "overall_camera": "整体场景相机",
  "region_cameras": {
    "区域一": "区域一相机"
  }
}
```

`project_prefix` must end with `岛`. Prefer the strongest unambiguous `XX岛`
clue found in collection names, then the saved project path or scene name, and
only then existing Context names. If no unambiguous clue exists, request it
from the user instead of inventing a prefix.

### 4. Report the Native Result

Report `created`, `updated`, `migrated`, `duplicate_contexts`,
`unmatched_contexts`, `skipped`, `failed`, `warnings`,
`validation_results`, `saved`, and stage timings. A successful
`renderset.prepare` has already restored the original Context and saved the
`.blend`; do not call another save tool. Treat `duplicate_contexts` as
delete-after-confirmation candidates, not permission to delete them.

If `status: failed`, report whether `rolled_back` is true. Never claim success after a failed audit or failed save.

## Expected User Requests

This skill should trigger for requests such as:

- “准备全部渲染 context”
- “把区域一和区域二未配置的建筑加进 RenderSet Pro”
- “检查所有 context 的分辨率倍率”
- “给单体建筑自动设置 Render Region”
- “检查 Shadow context 的采样值”
- “整理 Include in Render All 的勾选状态”
- “检查当前场景是否已经可以开始批量渲染”

## Completion Criteria

The task is complete only when:

- `renderset.prepare` returns `status: success`;
- every changed Context passes its native switch-and-read-back verification;
- the original Context is restored and `saved` is true;
- no long render was started;
- anomalies and uncertain collection ownership are explicitly reported.
