# Render Settings

## Fixed Render Properties

| Category | Property | Value |
|---|---|---|
| Engine | Render Engine | Cycles |
| Sampling | Render Denoise | On |
| Sampling | Adaptive Sampling | On |
| Sampling | Adaptive Min Samples | `0` |
| Light Paths | Max Bounces | `12` |
| Light Paths | Diffuse | `4` |
| Light Paths | Glossy | `4` |
| Light Paths | Transmission | `12` |
| Light Paths | Volume | `0` |
| Light Paths | Transparent | `8` |
| Light Paths | Light Tree | On |
| Film | Transparent | On |
| Resolution | Base X/Y | `1920 × 1920` |
| Resolution | Pixel Aspect | `1:1` |
| Output | Format | PNG |
| Output | Color | RGBA |
| Output | Depth | 8 bit |
| Output | Compression | `15%` |

RenderSet Pro manages output paths. Do not treat the current temporary `scene.render.filepath` as a project standard.

Color Management always follows the current project. Never change View Transform, Look, Exposure, Gamma, curves, or related settings in this workflow.

`ViewLayer.material_override` must remain empty.

## Context Sampling

Normal context:

```python
scene.cycles.use_adaptive_sampling = True
scene.cycles.samples = 600
scene.cycles.adaptive_threshold = 0.0
```

Shadow context, recognized only by a name ending in `_shadow`:

```python
scene.cycles.use_adaptive_sampling = True
scene.cycles.samples = 100
scene.cycles.adaptive_threshold = 0.005
```

Ensure `bpy.context.scene.cycles.adaptive_threshold` is included in every RenderSet context's override list. Verify by switching contexts and reading the value back.

## Orthographic Resolution

All formal render cameras are orthographic.

```text
Base resolution = 1920 × 1920
Resolution Percentage = round(Orthographic Scale × 2)
```

Examples:

| Ortho Scale | Percentage | Full-frame pixels |
|---:|---:|---:|
| 50 | 100% | 1920 × 1920 |
| 100 | 200% | 3840 × 3840 |
| 105 | 210% | 4032 × 4032 |
| 225 | 450% | 8640 × 8640 |

Report:

- wrong regional camera;
- non-orthographic camera;
- non-1920 base resolution;
- percentage mismatch;
- rounded percentage when Scale does not produce an integer.

## Render Region

Use only for single-building and front-layer contexts.

Procedure:

1. Apply the target context.
2. Collect renderable objects in the target collection and all descendants.
3. Use dependency-graph evaluated objects and visible instances.
4. Project world-space bounding-box corners through the active context camera.
5. Calculate normalized min/max bounds.
6. Expand each dimension by 10% of its calculated size.
7. Clamp to `0.0..1.0`.
8. Store:

```python
scene.render.use_border = True
scene.render.use_crop_to_border = False
scene.render.border_min_x = min_x
scene.render.border_max_x = max_x
scene.render.border_min_y = min_y
scene.render.border_max_y = max_y
```

Use full frame for overall, preview, terrain, and Shadow contexts:

```python
scene.render.use_border = False
scene.render.use_crop_to_border = False
```

Keeping Crop to Render Region off preserves identical canvas dimensions for 2D compositing.
