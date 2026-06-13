# Context Rules

## Collection Switch Names

| Workflow term | Blender property | Enabled/participating state |
|---|---|---|
| 启用 / Exclude | `LayerCollection.exclude` | `False` |
| 渲染显示 | `Collection.hide_render` | `False` |
| Holdout | `LayerCollection.holdout` | As specified |
| Indirect Only | `LayerCollection.indirect_only` | As specified |

Use View Layer `Exclude` as the primary content-isolation switch. Do not rely on the Outliner eye icon.

## Scene Hierarchy Assumptions

Expected top-level intent:

```text
场景
  整体场景相机
  区域一相机
  区域二相机
  ...
  太阳光

区域
  区域一
    建筑
      前层
  区域二
  ...

地形
  区域一地形
  区域二地形
  整体地形
  水面

Cutters
  保留插件结构

粒子
  BagaPie系列
  植被散布
  石头散布

杂项
```

Do not require perfect compliance. Analyze ambiguous Chinese collections and report uncertainty. Put no object into `杂项` automatically.

## Context Matrix

### Overall Complete Preview

Example: `农场岛整体场景_完整体`

- Camera: overall scene camera.
- Buildings, terrain, particles, and water: normal.
- Render Region: off.
- Include in Render All: off.

### Overall Terrain

Example: `农场岛整体场景_地形`

- Camera: overall scene camera.
- All buildings: excluded.
- Terrain and required particles: normal.
- Water: follow the established project state.
- Render Region: off.
- Include in Render All: on.

### Overall Terrain Shadow

Example: `农场岛整体场景_地形_shadow`

- Camera: overall scene camera.
- All buildings: excluded.
- Entire terrain subtree: indirect only, recursively including every child collection.
- Render Region: off.
- Include in Render All: on.
- Sampling profile: Shadow.

### Region Complete Preview

Example: `农场岛区域一_完整预览`

- Camera: matching region camera.
- Target region buildings: normal.
- Other regions: excluded.
- Render Region: off.
- Include in Render All: off.

### Region Shadow

Example: `农场岛区域一_shadow`

- Camera: matching region camera.
- Target region collection and its entire subtree: enabled and indirect only recursively.
- Other regions: excluded.
- Terrain: normal shadow receiver.
- Particles: excluded unless explicitly required.
- One combined context per region.
- Render Region: off.
- Include in Render All: on.
- Sampling profile: Shadow.

### Single Building

Example: `农场岛区域一_码头`

- Camera: matching region camera.
- Target building subtree: enabled.
- Other buildings in target region: excluded.
- Other regions: excluded.
- Entire terrain subtree: holdout and indirect only recursively.
- Entire water subtree: holdout and indirect only recursively, whether `水面` is under `地形` or is a top-level collection.
- Particles: excluded.
- Render Region: calculated from target building subtree.
- Include in Render All: on.
- Sampling profile: Normal.

### Front Layer

Example: `农场岛区域一_码头_前层`

- Create only for an explicit `前层` or user-approved equivalent collection.
- Isolate the front-layer subtree.
- Use the matching region camera.
- Entire terrain subtree: holdout and indirect only recursively.
- Entire water subtree: holdout and indirect only recursively, whether `水面` is under `地形` or is a top-level collection.
- Particles: excluded.
- Render Region: calculated from the front-layer subtree.
- Include in Render All: on.
- Sampling profile: Normal.

## Naming and Update Policy

- Preserve the project's existing prefix and Chinese naming style.
- Use `_shadow` as the exact Shadow suffix.
- Update a same-name context before considering creation.
- Do not delete duplicate or legacy contexts automatically; report them.
- Do not create a front-layer context from an uncertain child collection.
