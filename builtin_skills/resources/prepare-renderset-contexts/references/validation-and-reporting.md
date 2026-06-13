# Validation and Reporting

## Read-Back Checklist

Switch to each created or updated context and verify:

- context name and index;
- camera belongs to the correct region;
- camera type is `ORTHO`;
- base resolution is `1920 × 1920`;
- percentage equals `round(ortho_scale × 2)`;
- target region and target building subtree are enabled;
- unrelated buildings and regions are excluded;
- collection render visibility is correct;
- Holdout and Indirect Only match the context type on every required descendant collection, not only the parent;
- single-building and front-layer contexts set both Holdout and Indirect Only on the complete water subtree, including a top-level `水面`;
- particles match the context type;
- Include in Render All is correct;
- normal sampling is `600 / 0.0`;
- Shadow sampling is `100 / 0.005`;
- adaptive sampling remains enabled;
- material override is empty;
- Render Region is stored where required;
- Crop to Render Region is off.

Restore the original context after validation. `renderset.prepare` saves only
after every read-back check succeeds.

## Render Region Anomalies

Calculate:

```text
width = border_max_x - border_min_x
height = border_max_y - border_min_y
```

Flag:

- width or height `>= 0.90`: suspicious;
- width or height `>= 0.98`: high priority;
- any border equals `0.0` or `1.0`: touches frame edge;
- no renderable geometry;
- geometry behind the camera;
- isolated objects far from the main cluster;
- instances expanding the border unexpectedly.

A nearly full-frame border can indicate that small unrelated objects were grouped under the target building. Report object names/paths and measured bounds. Do not move or delete them.

Known example:

```text
农场岛区域一_新向日葵田
```

Its almost full-width border was caused by unrelated small objects inside the collection.

## Failure Policy

- If MCP disconnects, stop modifications and report the last verified step.
- If context switching fails, do not continue writing settings to an unknown context.
- If a camera or collection match is ambiguous, skip that context and request human confirmation.
- If a setting cannot be persisted through RenderSet Pro, report the property and do not claim success.
- If any critical write, audit, restore, or save step fails, the whole preparation transaction rolls back.
- Do not start a test render as validation.

## Report Template

```markdown
## 工作流结果

- 新建 context：0
- 更新 context：0
- 跳过 context：0
- 验证失败：0
- 当前 Render All 已勾选：0
- 未执行渲染

## 关键状态

- Material Override：None
- 正常采样：600 / 0.0
- Shadow 采样：100 / 0.005
- Crop to Render Region：关闭
- 原 context：已恢复
- Blend 文件：审计通过后已保存

## 异常情况

### 高优先级

- context 名称
  - 现象：
  - 测量：
  - 疑似原因：
  - 处理：仅报告，等待人工确认

### 一般提醒

- context 名称
  - 现象：
  - 建议：
```
