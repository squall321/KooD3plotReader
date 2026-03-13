# VTK-Free 단면 뷰 렌더러 구현 계획

## 개요

LS-DYNA d3plot 데이터를 읽어서 **사용자 정의 단면 평면** 기준으로 단면 뷰 이미지/영상을 생성하는 모듈.
기존 LSPrePost 기반 렌더링(`kood3plot_render`)을 대체하는 장기 목표.

### 핵심 방향

- **VTK 미사용** — libpng 단일 의존성, 크로스컴파일 용이
- **기존 코드 무수정** — `KOOD3PLOT_BUILD_SECTION_RENDER` 옵션으로 완전 분리
- `libkood3plot` (기존 정적 라이브러리) 링크하여 재활용
- 소프트웨어 래스터라이저 + 수퍼샘플링으로 LSPrePost 수준 컨투어 품질 달성

---

## 알고리즘 원리

### 컨투어 렌더링 파이프라인

```
d3plot solid_data (요소당 응력/변형률)
        │
        ▼
[Step 1] 노달 평균화 (Nodal Averaging)
         연결된 요소들의 값을 노드별로 평균
         → 노드마다 연속적인 스칼라 값
        │
        ▼
[Step 2] 단면 평면–요소 교차 계산
         각 요소의 노드 부호(signed distance) 확인
         → 교차 요소 목록 추출
        │
        ▼
[Step 3] 교차 폴리곤 생성 (Sutherland-Hodgman 클리핑)
         평면이 엣지를 자르는 교점 계산
         교점 위치에서 값 선형 보간
         → 각 꼭짓점에 스칼라 값 부착된 폴리곤
        │
        ▼
[Step 4] 직교 투영 (카메라 방향 → 2D)
         법선 벡터 방향으로 카메라 설정
         4×4 직교 투영 행렬 적용
        │
        ▼
[Step 5] 소프트웨어 Gouraud Shading
         폴리곤 삼각화 → 무게중심 보간
         스칼라 값 → 컬러맵 → RGB 픽셀
        │
        ▼
[Step 6] 수퍼샘플링 다운샘플 (2x → 1x)
         + libpng PNG 출력 / ffmpeg MP4 인코딩
```

### 핵심 수식

**노드-평면 부호 거리:**
```
d = (P - point_on_plane) · normal
```
d > 0이면 법선 방향, d < 0이면 반대, d = 0이면 평면 위.

**엣지 교점 및 값 보간:**
```
t = d_A / (d_A - d_B)
交点 = A.pos × (1-t) + B.pos × t
交点값 = value[A] × (1-t) + value[B] × t
```

**무게중심 Gouraud 보간 (삼각형 내 픽셀):**
```
λ = barycentric(P, V0, V1, V2)
pixel_value = v0 × λ0 + v1 × λ1 + v2 × λ2
pixel_color = colormap(normalize(pixel_value))
```

---

## 모듈 구조

```
src/section_render/              ← 신규 (기존 src/ 구조와 동일 패턴)
    SectionPlane.cpp
    NodalAverager.cpp
    SectionClipper.cpp           ← Sutherland-Hodgman
    SectionCamera.cpp
    PartMatcher.cpp
    ColorMap.cpp
    SoftwareRasterizer.cpp       ← Gouraud + 수퍼샘플링
    SectionViewRenderer.cpp      ← 메인 오케스트레이터
    SectionViewConfig.cpp        ← YAML 파서

include/kood3plot/section_render/
    SectionPlane.hpp
    NodalAverager.hpp
    SectionClipper.hpp
    SectionCamera.hpp
    PartMatcher.hpp
    ColorMap.hpp
    SoftwareRasterizer.hpp
    SectionViewRenderer.hpp
    SectionViewConfig.hpp
```

---

## 클래스 설계

### `SectionPlane`

단면 평면 정의 및 교차 판별.

```cpp
class SectionPlane {
public:
    // 생성: x/y/z 축 정렬 평면
    static SectionPlane fromAxis(char axis, const Vec3& point);
    // 생성: 임의 법선 벡터
    static SectionPlane fromNormal(const Vec3& normal, const Vec3& point);

    double signedDistance(const Vec3& p) const;

    // 엣지 교점 (t 값 반환, 0~1)
    // t가 [0,1] 범위일 때만 교점 존재
    bool edgeIntersection(const Vec3& a, const Vec3& b, double& t) const;

    Vec3 normal() const;
    Vec3 point() const;
};
```

### `NodalAverager`

요소 중심 데이터(응력/변형률) → 노드 평균 데이터 변환.

> **[수정]** `ControlData` 파라미터 필수 — `NV3D`(solid 스트라이드), `NV2D`(shell 스트라이드),
> `IU`(변위 플래그) 없이는 배열 인덱싱이 불가능.

```cpp
class NodalAverager {
public:
    // solid_data에서 지정 quantity의 노드별 평균 계산
    // quantity: "von_mises" | "eff_plastic_strain" | "sxx" | ...
    // ctrl.NV3D : solid 1개당 데이터 개수 (스트라이드)
    // ctrl.NEIPH: 추가 적분점 변수 수 (EPS 위치 = 6, 항상 고정)
    std::vector<double> compute(
        const kood3plot::data::Mesh& mesh,
        const kood3plot::data::StateData& state,
        const kood3plot::data::ControlData& ctrl,   // ← 필수 추가
        const std::string& quantity
    );

    // 노드 변위 (이미 nodal이므로 직접 반환)
    // ctrl.IU == 0이면 변위 데이터 없음 → 빈 벡터 반환
    std::vector<double> computeDisplacement(
        const kood3plot::data::StateData& state,
        const kood3plot::data::ControlData& ctrl,   // ← IU 플래그 확인용
        const std::string& component   // "x" | "y" | "z" | "magnitude"
    );
};
```

**solid_data 인덱싱 (NV3D 기반):**
```
element i의 σxx = solid_data[i * NV3D + 0]
element i의 σyy = solid_data[i * NV3D + 1]
element i의 σzz = solid_data[i * NV3D + 2]
element i의 σxy = solid_data[i * NV3D + 3]
element i의 σyz = solid_data[i * NV3D + 4]
element i의 σxz = solid_data[i * NV3D + 5]
element i의 EPS = solid_data[i * NV3D + 6]   ← NEIPH와 무관하게 위치 고정
```

### `SectionClipper`

단면 평면과 요소의 교차 폴리곤/선분 생성.

> **[수정]** Shell 요소는 평면과 만나면 **선분(2점)**이 나옴 — 채울 수 있는 폴리곤이 아님.
> `ClipPolygon`의 꼭짓점 수로 구분: `size() == 2` → 선분, `size() >= 3` → 채울 수 있는 폴리곤.

> **[수정]** Hex8 교점 정렬 알고리즘 명시: 12개 엣지에서 교점을 수집한 후,
> 절단 평면 위에 투영하여 **각도 정렬(Radial Sort)** 적용.

```cpp
struct ClipVertex {
    Vec3 position;    // 3D 교점 좌표
    double value;     // 보간된 스칼라 값
    int32_t part_id;  // 어느 파트 소속
};

// size() == 2  → Shell 교차 선분 (drawEdge로 렌더링)
// size() >= 3  → Solid 교차 폴리곤 (drawPolygon으로 렌더링)
using ClipPolygon = std::vector<ClipVertex>;

class SectionClipper {
public:
    // 전체 메시에서 단면 교차 형상 생성
    std::vector<ClipPolygon> clip(
        const kood3plot::data::Mesh& mesh,
        const std::vector<double>& node_values,   // NodalAverager 결과
        const std::vector<Vec3>& node_positions,  // 변형 후 좌표
        const SectionPlane& plane
    );
private:
    // Solid hex8: 12엣지 교점 수집 → Radial Sort
    // Radial Sort: 교점들을 절단 평면에 투영 → 중심 계산 → atan2로 각도 정렬
    ClipPolygon clipSolidElement(/* ... */);

    // Shell quad4: 4엣지 교점 수집 → 최대 2점 (선분)
    ClipPolygon clipShellElement(/* ... */);
};
```

**Radial Sort (Hex8 교점 정렬):**
```
1. 교점들의 중심 C = 평균 위치
2. 절단 평면의 두 직교 기저 벡터 (u, v) 계산
3. 각 교점 P에 대해: angle = atan2((P-C)·v, (P-C)·u)
4. angle 오름차순 정렬 → 올바른 폴리곤 순서
```

### `SectionCamera`

직교 카메라: 법선 방향에서 대상 파트 중심을 바라봄.

> **[수정]** 카메라는 **모든 상태에서 고정**되어야 함.
> 상태별로 재계산하면 프레임마다 뷰포트가 흔들려 MP4 영상이 불안정해짐.
> 반드시 **초기 상태(state 0) 또는 비변형 메시**에서 한 번만 계산하고 전 프레임에 재사용.

> **[수정]** ViewUp 선택 시 엣지 케이스 처리 명시.

```cpp
struct CameraParams {
    Vec3 position;
    Vec3 focal_point;
    Vec3 view_up;
    double parallel_scale;   // 뷰포트 크기 절반 (world 단위)
    Mat4 view_matrix;
    Mat4 proj_matrix;
    // 유효성 플래그: 단면이 대상 파트를 전혀 자르지 않을 경우 false
    bool valid = false;
};

class SectionCamera {
public:
    // 초기 상태에서 한 번만 호출 → 이후 모든 상태에 재사용
    CameraParams setup(
        const SectionPlane& plane,
        const std::vector<ClipPolygon>& target_polygons_state0,
        double view_scale
    );

    // 3D → 2D 픽셀 좌표 변환
    Vec2 project(const Vec3& world_pos, const CameraParams& cam,
                 int img_w, int img_h) const;
};
```

**ViewUp 자동 선택 (완전한 로직):**
```
if |normal · (0,0,1)| < 0.9:
    view_up = (0,0,1)         // 일반적인 경우
elif |normal · (0,1,0)| < 0.9:
    view_up = (0,1,0)         // 법선이 Z에 가까울 때
else:
    view_up = (1,0,0)         // 법선이 Z,Y 모두 가까울 때 (드묾)
```

**카메라 고정 호출 위치:**
```
SectionViewRenderer::render():
    1. reader.read_mesh()
    2. state_0 = reader.read_state(0)
    3. polys_0 = clipper.clip(mesh, averager.compute(...state_0), plane)
    4. cam = camera.setup(plane, polys_0, view_scale)  ← 한 번만
    5. for each state:
           renderState(mesh, state, cam, ...)           ← cam 고정 재사용
```

### `PartMatcher`

파트 ID/이름 패턴 매칭.

```cpp
class PartMatcher {
public:
    // YAML target_parts 리스트 파싱 결과로 초기화
    void addById(int32_t id);
    void addByPattern(const std::string& glob_pattern);  // "CELL*", "PKG*"
    void addByKeyword(const std::string& keyword);       // 이름에 포함

    // 기존 parsePartNamesFromKeyword() 결과 활용
    bool isTarget(int32_t part_id,
                  const std::map<int32_t, std::string>& part_names) const;

    std::set<int32_t> resolveTargetIds(
        const kood3plot::data::Mesh& mesh,
        const std::map<int32_t, std::string>& part_names
    ) const;
};
```

### `ColorMap`

스칼라 값 → RGB.

```cpp
enum class ColorMapType { RAINBOW, JET, COOL_WARM, GRAYSCALE };

class ColorMap {
public:
    explicit ColorMap(ColorMapType type = ColorMapType::RAINBOW);

    // 값 범위 설정 (auto = 데이터 min/max)
    void setRange(double vmin, double vmax);

    // [수정] MP4 출력 시 전체 상태에서 글로벌 범위 계산 필요
    // 상태별로 재계산하면 프레임마다 색상 기준이 변해 비교 불가
    // → SectionViewRenderer가 모든 상태 클리핑 후 글로벌 min/max를 먼저 계산,
    //   setRange()로 고정한 뒤 렌더링 시작
    void setAutoRange(const std::vector<ClipPolygon>& target_polys);   // PNG 단일 프레임용
    void setGlobalRange(double global_min, double global_max);         // MP4용 (전 프레임 고정)

    // 정규화된 값 [0,1] → RGB
    std::array<uint8_t, 3> map(double value) const;
    std::array<uint8_t, 3> mapRaw(double value) const;  // 범위 적용

    // 배경 파트 카테고리컬 색상 (파트 ID → 고정 색)
    // hash(part_id) % palette_size 방식으로 결정론적 색상 보장
    static std::array<uint8_t, 3> partColor(int32_t part_id);
};
```

### `SoftwareRasterizer`

2D 소프트웨어 렌더러.

```cpp
class SoftwareRasterizer {
public:
    SoftwareRasterizer(int width, int height, int supersample = 2);

    void clear(std::array<uint8_t, 3> bg_color = {40, 40, 40});

    // 대상 파트 폴리곤: Gouraud shading (컨투어)
    void drawPolygonContour(
        const std::vector<Vec2>& screen_verts,
        const std::vector<double>& values,
        const ColorMap& cmap
    );

    // 배경 파트 폴리곤: 단색
    void drawPolygonFlat(
        const std::vector<Vec2>& screen_verts,
        std::array<uint8_t, 3> color
    );

    // 파트 경계선 (선택적)
    void drawEdge(Vec2 a, Vec2 b, std::array<uint8_t, 3> color);

    // 컬러바 오버레이
    void drawColorBar(const ColorMap& cmap, double vmin, double vmax,
                      const std::string& label);

    // 시간/상태 텍스트 (8×8 비트맵 폰트 내장 — 외부 폰트 라이브러리 불필요)
    void drawText(int x, int y, const std::string& text);

    // 수퍼샘플링 다운샘플 후 PNG 저장
    bool savePNG(const std::string& filepath);

    // 원시 픽셀 버퍼 반환 (ffmpeg 파이프용)
    const std::vector<uint8_t>& pixels() const;

private:
    int width_, height_, ss_;  // ss_ = supersample factor
    std::vector<uint8_t> buffer_;  // ss*width × ss*height × 3

    void rasterizeTriangle(Vec2 v0, Vec2 v1, Vec2 v2,
                           double val0, double val1, double val2,
                           const ColorMap& cmap);
};
```

### `SectionViewRenderer`

메인 오케스트레이터.

```cpp
class SectionViewRenderer {
public:
    void render(const SectionViewConfig& config,
                UnifiedProgressCallback callback = nullptr);

private:
    // 단일 상태 렌더링
    void renderState(
        const kood3plot::data::Mesh& mesh,
        const kood3plot::data::StateData& state,
        const SectionViewConfig& config,
        const std::set<int32_t>& target_ids,
        const std::map<int32_t, std::string>& part_names,
        int state_idx,
        const std::string& output_dir
    );

    // 변형 후 노드 좌표 계산 (변위 적용)
    std::vector<Vec3> deformedPositions(
        const kood3plot::data::Mesh& mesh,
        const kood3plot::data::StateData& state,
        bool apply_deformation
    );
};
```

---

## YAML 설정 구조

기존 `UnifiedConfig` 구조체에 `section_views` 필드 추가:

```yaml
version: "2.0"
d3plot_path: "/data/case01/d3plot"
output_directory: "./output"

# 기존 analysis_jobs, render_jobs 그대로 유지 ...

# 신규: VTK-Free 단면 뷰
section_views:
  - name: "z_center_cell_stress"
    enabled: true

    # 단면 평면 (두 방식 중 택1)
    section_plane:
      axis: z                   # x | y | z (축 정렬 평면)
      point: [0.0, 0.0, 50.0]   # 평면 위의 한 점

      # 임의 법선 벡터 방식:
      # normal: [0.707, 0.0, 0.707]
      # point:  [10.0, 0.0, 50.0]

    # 대상 파트 (컨투어 표시)
    target_parts:
      - id: 5                   # 파트 ID 직접 지정
      - pattern: "CELL*"        # glob 와일드카드
      - keyword: "BATTERY"      # 이름에 포함된 문자열

    # 뷰포트: 대상 파트 bounding box × view_scale
    view_scale: 1.5

    # 변형 후 형상 사용 여부 (true = 변위 적용 좌표)
    use_deformed: true

    # 컨투어 옵션 (대상 파트에만 적용)
    contour:
      quantity: von_mises        # von_mises | eff_plastic_strain |
                                 # displacement | sxx | syy | szz
      component: magnitude       # magnitude | x | y | z  (displacement만 해당)
      range: auto                # auto | [0.0, 500.0]
      colormap: rainbow          # rainbow | jet | cool_warm | grayscale

    # 배경 파트 스타일
    background:
      style: per_part_color      # per_part_color | hidden | wireframe
      opacity: 0.6               # 0.0~1.0 (향후 확장용)

    # 시간 상태 선택
    time_states: all             # all | last | [0, 10, 20]
                                 # {start: 0, end: 100, step: 5}

    # 출력
    output:
      format: mp4                # png | mp4
      resolution: [1920, 1080]
      fps: 10                    # mp4 전용
      supersample: 2             # 안티앨리어싱 (2 = 2x 수퍼샘플링)
      show_colorbar: true
      show_time: true
      show_part_names: false
```

---

## 파일 출력 구조

```
output_directory/
└── section_views/
    └── z_center_cell_stress/
        ├── frame_0000.png   (time_states: all, format: png)
        ├── frame_0001.png
        ├── ...
        └── z_center_cell_stress.mp4   (format: mp4)
```

---

## 구현 단계 (Phase)

### Phase 0 — CMake 빌드 셋업 (의존성 없음)

- `CMakeLists.txt`에 옵션 추가:
  ```cmake
  option(KOOD3PLOT_BUILD_SECTION_RENDER "Build VTK-Free Section View Renderer" OFF)
  ```
- `find_package(PNG REQUIRED)` (libpng, vcpkg에 이미 존재)
- `libkood3plot_section_render` 정적 라이브러리 타겟 추가
- 기존 빌드에 영향 없음 확인

**완료 기준**: 빈 라이브러리가 기존 빌드 깨지 않고 컴파일됨

---

### Phase 1 — 핵심 데이터 구조 (C++ only, 의존 없음)

구현 파일:
- `SectionPlane.cpp` — 평면 정의, 부호 거리, 엣지 교점
- `PartMatcher.cpp` — ID/glob/keyword 매칭
- `ColorMap.cpp` — rainbow/jet/cool_warm 컬러맵 룩업 테이블

단위 테스트:
- 평면 부호 거리 정확도
- glob 패턴 매칭 (`CELL*`, `*PKG*`)
- 컬러맵 boundary 값 (0.0, 1.0)

**완료 기준**: `ctest` 통과

---

### Phase 2 — 노달 평균화 + 단면 클리핑

구현 파일:
- `NodalAverager.cpp`
  - von Mises: `sqrt(0.5 * ((σxx-σyy)² + (σyy-σzz)² + (σzz-σxx)² + 6(σxy²+σyz²+σxz²)))`
  - EPS: solid_data[i * NV3D + 6] (ctrl.NV3D 기반 인덱싱)
  - Thick shell: thick_shell_data[i * NV3DT + ...] (ctrl.NV3DT)
  - 변위: node_displacements[node*3 + {0,1,2}]
  - **삭제된 요소 스킵**: `deleted_solids`, `deleted_shells`, `deleted_thick_shells` 체크
    → 삭제 요소의 값은 노달 평균에 포함시키지 않음

- `SectionClipper.cpp`
  - Solid (hex8): 12개 엣지 순회, 교점 수집, Radial Sort
  - **Thick shell (8-node)**: Solid와 동일한 로직 (clipSolidElement 재사용 가능)
  - Shell (quad4): 4개 엣지 순회 → 선분(2점)
  - **삭제된 요소 스킵**: 단면 폴리곤 생성 대상에서 제외

단위 테스트:
- 단순 정육면체 요소에서 z=0 평면 클리핑 → 예상 폴리곤 확인
- 노달 평균화: 공유 노드에서 평균 계산 정확도
- 삭제 요소 포함 시나리오: 삭제 요소가 평균/클리핑에서 제외되는지 확인

**완료 기준**: 실제 d3plot 파일에서 클리핑 결과 JSON 덤프하여 육안 검증

---

### Phase 3 — 소프트웨어 래스터라이저

구현 파일:
- `SoftwareRasterizer.cpp`
  - 삼각형 래스터라이저 (무게중심 보간)
  - 수퍼샘플링 버퍼 (ss_width × ss_height)
  - 다운샘플: 2×2 박스 필터 평균
  - libpng 저장

- `SectionCamera.cpp`
  - 직교 카메라 행렬 생성
  - 대상 파트 2D bbox 계산 → ParallelScale 결정
  - ViewUp 자동 선택 (법선이 Z에 가까우면 Y 사용)

단위 테스트:
- 단순 삼각형 Gouraud 결과 픽셀 샘플링 검증
- 카메라 투영: 알려진 3D 점 → 예상 2D 좌표

**완료 기준**: 더미 폴리곤으로 컨투어 PNG 생성 확인

---

### Phase 4 — 통합 렌더러 + 출력

구현 파일:
- `SectionViewRenderer.cpp` — 전체 파이프라인 오케스트레이션
- `SectionViewConfig.cpp` — YAML 파서 (기존 `UnifiedConfigParser` 패턴 동일)
- `examples/section_view.cpp` — CLI 예제

**렌더러 처리 순서 (수정 반영):**
```
1. read_mesh() + ControlData 확보
2. PartMatcher로 target_ids 확정
3. read_state(0) → 카메라 파라미터 계산 (한 번만)
4. format == mp4 (두 번 순회):
       [1차 패스] 모든 상태 클리핑 → 글로벌 min/max 누적 → colormap.setGlobalRange()
       [2차 패스] 렌더링  ← 1차 패스에서 클리핑을 가볍게 처리해도 min/max는 정확함
   format == png:
       상태별 auto range 사용 (두 번 순회 불필요)
5. for each selected state:
       - deformedPositions()
       - NodalAverager::compute() (ctrl 포함)
       - SectionClipper::clip() → ClipPolygon[]
       - SoftwareRasterizer:
           * 배경 파트: size()>=3 → drawPolygonFlat, size()==2 → drawEdge(회색)
           * 대상 파트: size()>=3 → drawPolygonContour, size()==2 → drawEdge(컬러)
       - savePNG() / ffmpeg 파이프에 픽셀 전송
```

출력:
- PNG: `frame_XXXX.png` 시퀀스
- MP4: ffmpeg 파이프 (`popen("ffmpeg -f rawvideo ...")`)

**완료 기준**: 실제 d3plot + YAML로 MP4 생성, 컨투어 품질 확인

---

### Phase 5 — UnifiedAnalyzer 통합

- `AnalysisTypes.hpp`: `UnifiedConfig`에 `section_views` 필드 추가
- `UnifiedAnalyzer.cpp`: `processVtkSectionViews()` 호출 추가
  (`#ifdef KOOD3PLOT_BUILD_SECTION_RENDER` 가드)
- `python/single_analyzer`: `--section-view` 옵션 추가

**완료 기준**: 기존 unified_analyzer 바이너리에서 section_views YAML 섹션으로 단면 뷰 생성

---

### Phase 6 — 품질 개선 (선택)

- 컬러바 렌더링 (스케일 + 레이블)
- 파트 경계선 표시 (엣지 하이라이트)
- 시간/파트 정보 텍스트 오버레이
- 쉘 요소 표면층/평균층 선택 옵션
- EGL offscreen OpenGL으로 교체 (성능, MSAA)

---

## 의존성 요약

| 라이브러리 | 용도 | 기존 여부 | 비고 |
|-----------|------|----------|------|
| libpng | PNG 출력 | 신규 추가 | vcpkg `libpng` |
| ffmpeg | MP4 인코딩 | 기존 (`popen` 방식) | 시스템 설치 가정 |
| yaml-cpp | YAML 파싱 | 기존 | 그대로 재활용 |
| OpenMP | 병렬 래스터라이징 | 기존 | Phase 6 선택적 |

---

## 크로스 플랫폼 지원

| 플랫폼 | 지원 | 비고 |
|--------|------|------|
| Linux x64 | 완전 지원 | libpng apt 또는 vcpkg |
| Windows x64 | 완전 지원 | vcpkg `libpng:x64-windows` |
| Linux → Windows 크로스 | 지원 | MinGW + libpng 정적 |
| macOS | 지원 | brew install libpng |

---

## 기존 기능과의 관계

```
기존 (유지):
    libkood3plot_render  ← LSPrePost 기반 렌더링
    unified_analyzer     ← render_jobs 처리

신규 (추가):
    libkood3plot_section_render  ← 소프트웨어 단면 뷰
    unified_analyzer              ← section_views 처리 (옵션 ON시)

장기 목표:
    render_jobs의 section_view 타입 → section_render로 처리
    LSPrePost 의존성 점진적 축소
```

---

## 구현 우선순위

```
[필수] Phase 0 → 1 → 2 → 3 → 4  (핵심 기능)
[권장] Phase 5                    (기존 워크플로우 통합)
[선택] Phase 6                    (품질/성능 개선)
```

Phase 4 완료 시점에서 LSPrePost 단면 뷰와 품질 비교 후 Phase 5 진행 여부 결정.

---

## 검토에서 발견된 수정 사항 (2026-03-12)

| # | 위치 | 문제 | 수정 내용 |
|---|------|------|----------|
| 1 | `NodalAverager` | `ControlData` 없으면 `solid_data` 스트라이드(`NV3D`) 알 수 없음 | `ctrl` 파라미터 추가, `IU` 플래그 체크 추가 |
| 2 | `SectionClipper` | Shell(quad4)는 평면과 만나면 선분(2점)이지 채울 수 있는 폴리곤이 아님 | `ClipPolygon` size로 구분: 2→선분, ≥3→폴리곤 |
| 3 | `SectionClipper` | Hex8 교점 정렬 알고리즘 미명시 | Radial Sort (절단 평면에 투영 후 atan2 각도 정렬) 명시 |
| 4 | `SectionCamera` | 상태별로 카메라 재계산 시 MP4 프레임마다 뷰포트 흔들림 | 초기 상태에서 한 번만 계산, 전 프레임 고정 재사용 |
| 5 | `ColorMap` | MP4 출력 시 상태별 auto range → 프레임마다 색상 기준 변함 | 글로벌 min/max 사전 계산 후 `setGlobalRange()`로 고정 |
| 6 | `NodalAverager` / `SectionClipper` | 요소 삭제(erosion) 시 `deleted_solids` 등 미처리 → 잘못된 값 참조 | Phase 2에서 삭제 요소 스킵 로직 추가 |
| 7 | `SectionClipper` | Thick shell(8-node) 미처리 — solid_data도 thick_shell_data도 아님 | `clipSolidElement` 재활용 + `thick_shell_data` 인덱싱(`NV3DT`) 추가 |
| 8 | `SectionViewRenderer` | MP4 colormap 범위 계산 위해 전 상태 순회 2회 필요한데 미명시 | 1차 패스(min/max 수집) + 2차 패스(렌더링) 명시 |
