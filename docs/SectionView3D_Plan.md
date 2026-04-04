# Section View 3D Half-Model Plan

## Overview

기존 2D 단면뷰(section) 모드에 추가하여, **3D 반절단 뷰(section_3d)** 모드를 구현한다.
- 단면 평면으로 모델을 반으로 자르고
- 잘린 단면(cut face)에는 **응력/변형률 컨투어** 표시
- 나머지 반쪽 3D 외표면은 **파트 고유색 + diffuse 조명** 으로 입체감 있게 표시
- 카메라는 isometric 각도 (45도씩 회전)로 3D가 잘 보이게 배치

## Rendering Pipeline (per frame)

```
1. clear(color + zbuffer)
2. 3D Camera setup (isometric: 45° azimuth, 35° elevation from cut plane)
3. Half-model exterior faces (pre-computed at state 0, updated per-state for deformation):
   a. SurfaceExtractor → all exterior faces
   b. Filter: keep faces where centroid is on "kept" side of cut plane
   c. For each face:
      - Compute deformed node positions from state
      - Compute face normal → diffuse shading (N·L)
      - **Target parts**: per-vertex stress contour (Gouraud) × shading
      - **Background parts**: flat part color × shading
      - drawTriangle3D / drawTriangle3DContour() with Z-buffer
4. Cut face (section plane intersection — the sliced interior):
   a. SectionClipper::clip() → target + background polygons
   b. **Target polygons**: drawTriangle3DContour() with stress colormap + Z-buffer
   c. **Background polygons**: drawTriangle3D() with part color + Z-buffer
5. Edge lines (optional): drawLine3D() for mesh wireframe on visible surfaces
6. savePng → frame
7. assembleMp4
```

## Camera Geometry

For axis-aligned cuts, camera rotates 45° from the cut plane normal:
- **X-axis cut**: camera looks from Y+Z direction (45° Y-rot, 45° Z-rot)
- **Y-axis cut**: camera looks from X+Z direction (45° X-rot, 45° Z-rot)
- **Z-axis cut**: camera looks from X+Y direction (45° X-rot, 45° Y-rot)

General formula (isometric orthographic):
```
eye_dir = normalize(plane_normal + basis_u * tan(45°) + basis_v * tan(35°))
up = basis_v (adjusted for camera rotation)
```

## Lighting Model

Simple Lambertian diffuse:
```
intensity = ambient + diffuse * max(0, dot(face_normal, light_dir))
```
- ambient = 0.3
- diffuse = 0.7
- light_dir = camera direction (headlight)
- Back-face: flip normal if facing away from camera

## Files to Modify

### Modified (existing)
| File | Change |
|------|--------|
| `SoftwareRasterizer.hpp/cpp` | Add Z-buffer, drawTriangle3D, drawLine3D |
| `SectionCamera.hpp/cpp` | Add setupIsometric(), project3D() returning (x, y, depth) |
| `SectionViewConfig.hpp` | Add `view_mode` enum (Section2D / Section3D) |
| `SectionViewRenderer.cpp` | Add render3D() pipeline alongside existing render() |

### Unchanged
| File | Reason |
|------|--------|
| `SectionClipper.hpp/cpp` | Reused as-is for cut face polygons |
| `NodalAverager.hpp/cpp` | Reused for nodal stress values |
| `ColorMap.hpp/cpp` | Reused for contour color mapping |
| `SectionPlane.hpp/cpp` | Reused for plane definition |

## Config YAML

```yaml
section_views:
  - axis: x
    view_mode: section_3d    # NEW: "section" (default, 2D) or "section_3d" (3D half-model)
    target_ids: [4, 5, 6]
    auto_center: true
    auto_slab: true
    field: von_mises
    colormap: fringe
    global_range: true
    output_dir: section_view_x_3d
```

## Visual Result

```
+----------------------------------+
|                                  |
|   /‾‾‾‾‾‾‾‾‾\                   |
|  / contour    \  target part     |
| /  (stress     \ 3D exterior     |
| |  fringe on   | = contour       |
| |  ALL faces)  |                 |
| |##############|                 |
| |## cut face ##| interior cross  |
| |## contour  ##| section =       |
| |##############| contour too     |
|  \ bg parts   /                  |
|   \ (part    /   bg exterior     |
|    \ color) /    = shaded color  |
|     \_____/                      |
|                                  |
+----------------------------------+

Target parts: stress contour on BOTH 3D exterior AND cut face
Background parts: part color + diffuse shading on exterior only
```

## Implementation Order

1. Z-buffer → SoftwareRasterizer (drawTriangle3D, drawLine3D)
2. 3D camera → SectionCamera (setupIsometric, project3D)
3. Half-model face extraction → SectionViewRenderer (reuse SurfaceExtractor)
4. Diffuse lighting → inline in render loop
5. Config → SectionViewConfig (view_mode field + YAML parse)
6. Render pipeline → SectionViewRenderer::render3D()
7. Build + test
