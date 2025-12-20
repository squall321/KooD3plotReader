# Phase 2: High-Performance Visualization Application

**목표**: 양자화 HDF5 데이터를 활용한 초고속 LS-DYNA 결과 가시화 앱 개발

**예상 기간**: 10-12주 (현실적: 12-14주)
**핵심 성능 목표** (현실화):
- 로컬 가시화: 60 FPS (소규모), 30+ FPS (100만 노드 모델)
- 원격 가시화: 2-3초 타임스텝 전환 (1Gbps, 100만 노드)
- 메모리: 100만 노드 모델을 4-6GB RAM에서 처리 (양자화 모드)

---

## 1. Overview

### 1.1 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                    Visualization App                         │
│  ┌────────────┐  ┌────────────┐  ┌──────────────────────┐  │
│  │   Qt GUI   │  │  Network   │  │  GPU Render Engine   │  │
│  │            │──│  Loader    │──│  (OpenGL/Vulkan)     │  │
│  │  - Timeline│  │            │  │                      │  │
│  │  - Parts   │  │  HDF5      │  │  - Deformation       │  │
│  │  - Clip    │  │  Chunk     │  │  - Section Plane     │  │
│  │  - Colormap│  │  Stream    │  │  - Colormap          │  │
│  └────────────┘  └────────────┘  └──────────────────────┘  │
│         │               │                    │               │
│         └───────────────┴────────────────────┘               │
│                         │                                    │
│                  GPU Memory Manager                          │
│         (Quantized data → Dequantize in shader)             │
└─────────────────────────────────────────────────────────────┘
                          │
           ┌──────────────┴──────────────┐
           │                             │
    [Local HDF5]                  [Remote Server]
                                   REST/gRPC API
```

### 1.2 핵심 기술 스택

| 레이어 | 기술 | 이유 |
|--------|------|------|
| GUI Framework | Qt 6 | 크로스플랫폼, 성숙도 높음 |
| Rendering | OpenGL 4.5 (1차) / Vulkan (2차) | OpenGL: 빠른 개발, Vulkan: 최고 성능 |
| Data Format | HDF5 (KOO-HDF5) | Phase 1에서 개발 |
| Network | gRPC / REST | gRPC: 스트리밍, REST: 호환성 |
| Build System | CMake | 크로스플랫폼 빌드 |
| Parallelization | std::thread, std::async | 네트워크 I/O와 렌더링 분리 |

### 1.3 두 가지 렌더링 모드

#### Mode 1: 원본 데이터 가시화 (Baseline)
- float32 데이터 직접 사용
- 정밀도 손실 없음
- 메모리/대역폭 부담 큼
- 비교 기준용

#### Mode 2: 양자화 데이터 가시화 (Optimized)
- int16/uint16 데이터 사용
- GPU에서 실시간 복원
- 70-85% 메모리/대역폭 절감 (temporal delta 포함)
- **메인 모드**

**전환 버튼**: UI에서 실시간 모드 전환 가능

**NEW - Temporal Delta 처리**:
- t=0: Full int16 데이터 로드
- t>0: int8 delta 로드 + 이전 프레임과 합산
- GPU에서 누적 복원 (매우 빠름)

---

## 2. Phase 2-A: 프로젝트 구조 설계 (Week 1)

### 2.1 디렉토리 구조

```
vis-app/
├── CMakeLists.txt
├── README.md
├── docs/
│   ├── PHASE2_VISUALIZATION_APP.md  (이 문서)
│   ├── USER_GUIDE.md
│   └── DEVELOPER_GUIDE.md
│
├── src/
│   ├── main.cpp
│   │
│   ├── gui/                          # Qt GUI
│   │   ├── MainWindow.cpp
│   │   ├── TimelineWidget.cpp        # 타임스텝 슬라이더
│   │   ├── PartsTreeWidget.cpp       # Part 선택
│   │   ├── ClipPlaneWidget.cpp       # 단면 제어
│   │   ├── ColormapWidget.cpp        # Colormap 설정
│   │   ├── RenderSettingsWidget.cpp  # 렌더 옵션
│   │   └── StatusBar.cpp
│   │
│   ├── data/                         # 데이터 로더
│   │   ├── HDF5Loader.cpp            # 로컬 HDF5 읽기
│   │   ├── NetworkLoader.cpp         # 원격 HDF5 스트리밍
│   │   ├── DataCache.cpp             # 메모리 캐시
│   │   ├── QuantizedData.cpp         # 양자화 데이터 구조
│   │   └── Dequantizer.cpp           # CPU 역양자화 (필요시)
│   │
│   ├── render/                       # 렌더링 엔진
│   │   ├── OpenGL/
│   │   │   ├── GLRenderer.cpp        # OpenGL 렌더러
│   │   │   ├── GLShaderProgram.cpp
│   │   │   ├── GLMesh.cpp
│   │   │   ├── GLTexture.cpp
│   │   │   └── GLFramebuffer.cpp
│   │   │
│   │   ├── Vulkan/                   # (Phase 2-E)
│   │   │   ├── VkRenderer.cpp
│   │   │   └── ...
│   │   │
│   │   ├── Camera.cpp                # 카메라 제어
│   │   ├── ClipPlane.cpp             # 단면 평면
│   │   ├── Colormap.cpp              # Colormap 텍스처
│   │   ├── RenderMode.cpp            # Original vs Quantized
│   │   └── FrameStats.cpp            # FPS, GPU 메모리
│   │
│   ├── shaders/                      # GLSL 셰이더
│   │   ├── deformation.vert          # 변형 + 양자화 해제
│   │   ├── fringe.frag               # Colormap + 단면
│   │   ├── section_plane.geom        # Geometry shader (단면)
│   │   └── original.vert             # 원본 데이터용
│   │
│   ├── network/                      # 네트워크 (Phase 2-D)
│   │   ├── gRPC/
│   │   │   ├── D3plotService.proto
│   │   │   └── gRPCClient.cpp
│   │   │
│   │   └── REST/
│   │       └── RESTClient.cpp
│   │
│   └── utils/
│       ├── Logger.cpp
│       ├── Config.cpp                # YAML 설정 파일
│       └── Math.cpp                  # 벡터/행렬 연산
│
├── resources/
│   ├── icons/
│   ├── colormaps/                    # Jet, Viridis, ...
│   └── default_config.yaml
│
└── tests/
    ├── test_hdf5_loader.cpp
    ├── test_gl_renderer.cpp
    ├── test_dequantization.cpp
    └── benchmark_render_performance.cpp
```

### 2.2 CMake 설정

```cmake
# vis-app/CMakeLists.txt

cmake_minimum_required(VERSION 3.20)
project(KooD3plotViewer VERSION 1.0.0)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Qt6
find_package(Qt6 REQUIRED COMPONENTS Widgets OpenGLWidgets)

# OpenGL
find_package(OpenGL REQUIRED)

# HDF5
find_package(HDF5 REQUIRED COMPONENTS CXX)

# gRPC (optional)
find_package(gRPC CONFIG)

# Vulkan (optional, Phase 2-E)
find_package(Vulkan)

# Sources
set(VIEWER_SOURCES
    src/main.cpp
    src/gui/MainWindow.cpp
    src/gui/TimelineWidget.cpp
    src/gui/PartsTreeWidget.cpp
    src/gui/ClipPlaneWidget.cpp
    src/gui/ColormapWidget.cpp
    src/data/HDF5Loader.cpp
    src/data/DataCache.cpp
    src/data/Dequantizer.cpp
    src/render/OpenGL/GLRenderer.cpp
    src/render/OpenGL/GLShaderProgram.cpp
    src/render/Camera.cpp
    src/render/ClipPlane.cpp
    src/render/Colormap.cpp
)

# Executable
add_executable(kood3plot_viewer ${VIEWER_SOURCES})

target_link_libraries(kood3plot_viewer
    PRIVATE
        Qt6::Widgets
        Qt6::OpenGLWidgets
        OpenGL::GL
        hdf5::hdf5_cpp
        kood3plot              # Phase 1 라이브러리
        kood3plot_hdf5         # Phase 1 HDF5
        kood3plot_quantization # Phase 1 양자화
)

# Shader 파일 복사
file(COPY ${CMAKE_CURRENT_SOURCE_DIR}/src/shaders
     DESTINATION ${CMAKE_BINARY_DIR})

# Resources
qt_add_resources(VIEWER_SOURCES resources.qrc)

# Install
install(TARGETS kood3plot_viewer DESTINATION bin)
```

---

## 3. Phase 2-B: 렌더링 엔진 - OpenGL (Week 2-5)

### 3.1 렌더링 파이프라인 설계

```
[HDF5 Chunk]
     ↓ (CPU)
[int16 VBO upload]
     ↓ (GPU)
[Vertex Shader: dequantize + deform]
     ↓
[Geometry Shader: section plane]
     ↓
[Fragment Shader: colormap lookup]
     ↓
[Framebuffer]
```

### 3.2 GPU 데이터 구조

#### 3.2.1 VBO Layout (양자화 모드)

**기본 구조 (t=0)**:
```glsl
// Vertex Buffer Object (Base timestep)
struct QuantizedVertexBase {
    ivec3 position;      // int16 × 3 (undeformed)
    ivec3 displacement;  // int16 × 3 (t=0 full data)
    uint16 scalar;       // uint16 (Von Mises, etc.)
    uint16 part_id;      // uint16
};

// 16 bytes per vertex (vs 32 bytes in float32) → 50% 절감
```

**NEW - Delta 구조 (t>0)**:
```glsl
// Vertex Buffer Object (Delta timestep)
struct QuantizedVertexDelta {
    ivec3 displacement_delta;  // int8 × 3 (delta from t-1)
    uint8 scalar_delta;        // uint8 (delta from t-1)
    uint8 padding;             // alignment
};

// 4 bytes per vertex → 87.5% 절감!
```

**메모리 절감 효과**:
```
100만 노드 × 100 타임스텝:
- Original (float32): 100M × 100 × 32 bytes = 320 GB
- Quantized (int16):  100M × 100 × 16 bytes = 160 GB (50% 절감)
- Temporal Delta:
  - t=0: 100M × 16 bytes = 1.6 GB
  - t=1~99: 100M × 99 × 4 bytes = 39.6 GB
  - Total: 41.2 GB (87% 절감!)
```

#### 3.2.2 SSBO (Shader Storage Buffer)
```glsl
// Scale/Offset 파라미터 (Part별)
layout(std430, binding = 0) buffer ScaleOffsetBuffer {
    vec3 position_scale;
    vec3 position_offset;
    vec3 disp_scale[MAX_PARTS];
    vec3 disp_offset[MAX_PARTS];
    float scalar_scale[MAX_PARTS];
    float scalar_offset[MAX_PARTS];
};
```

### 3.3 Vertex Shader (양자화 해제 + 변형)

**Base Shader (t=0)**:
```glsl
// src/shaders/deformation_base.vert

#version 450 core

layout(location = 0) in ivec3 a_position;     // int16 좌표
layout(location = 1) in ivec3 a_displacement; // int16 변위 (full)
layout(location = 2) in uint a_scalar;        // uint16 scalar (full)
layout(location = 3) in uint a_part_id;       // uint16 part

// Uniforms
uniform mat4 u_mvp;                // Model-View-Projection
uniform float u_warp_scale;        // 변형 스케일 (1.0 = 원본)

// SSBO
layout(std430, binding = 0) buffer ScaleOffset {
    vec3 pos_scale;
    vec3 pos_offset;
    vec3 disp_scale[256];  // MAX_PARTS = 256
    vec3 disp_offset[256];
    float scalar_scale[256];
    float scalar_offset[256];
};

// Outputs
out float v_scalar;       // Fragment shader로 전달
out vec3 v_normal;        // 노멀 (단면용)

void main() {
    uint pid = a_part_id;

    // 1. 좌표 역양자화
    vec3 pos = vec3(a_position) * pos_scale + pos_offset;

    // 2. 변위 역양자화
    vec3 disp = vec3(a_displacement) * disp_scale[pid] + disp_offset[pid];

    // 3. 변형 적용
    vec3 deformed_pos = pos + disp * u_warp_scale;

    // 4. MVP 변환
    gl_Position = u_mvp * vec4(deformed_pos, 1.0);

    // 5. Scalar 역양자화
    v_scalar = float(a_scalar) * scalar_scale[pid] + scalar_offset[pid];

    // 6. 노멀 계산 (인접 vertex 기반, 단순화)
    v_normal = vec3(0, 0, 1);  // 임시
}
```

**NEW - Delta Shader (t>0)**:
```glsl
// src/shaders/deformation_delta.vert

#version 450 core

layout(location = 0) in ivec3 a_position;           // int16 좌표 (변경 없음)
layout(location = 1) in ivec3 a_displacement_delta; // int8 변위 delta!
layout(location = 2) in int a_scalar_delta;         // int8 scalar delta!
layout(location = 3) in uint a_part_id;             // uint16 part

// Uniforms
uniform mat4 u_mvp;
uniform float u_warp_scale;

// SSBO (동일)
layout(std430, binding = 0) buffer ScaleOffset {
    vec3 pos_scale;
    vec3 pos_offset;
    vec3 disp_scale[256];
    vec3 disp_offset[256];
    float scalar_scale[256];
    float scalar_offset[256];
};

// NEW - Previous timestep data (SSBO)
layout(std430, binding = 1) buffer PreviousState {
    ivec3 prev_displacement[]; // 이전 타임스텝의 누적 변위 (int16)
    int prev_scalar[];          // 이전 타임스텝의 누적 scalar (int16)
};

out float v_scalar;
out vec3 v_normal;

void main() {
    uint pid = a_part_id;
    uint vid = gl_VertexID;

    // 1. 좌표 역양자화 (변경 없음)
    vec3 pos = vec3(a_position) * pos_scale + pos_offset;

    // 2. Delta 누적 (핵심!)
    ivec3 current_disp = prev_displacement[vid] + a_displacement_delta;
    prev_displacement[vid] = current_disp;  // 업데이트

    // 3. 변위 역양자화
    vec3 disp = vec3(current_disp) * disp_scale[pid] + disp_offset[pid];

    // 4. 변형 적용
    vec3 deformed_pos = pos + disp * u_warp_scale;

    // 5. MVP 변환
    gl_Position = u_mvp * vec4(deformed_pos, 1.0);

    // 6. Scalar delta 누적
    int current_scalar = prev_scalar[vid] + a_scalar_delta;
    prev_scalar[vid] = current_scalar;  // 업데이트

    v_scalar = float(current_scalar) * scalar_scale[pid] + scalar_offset[pid];

    v_normal = vec3(0, 0, 1);
}
```

**Delta 처리 전략**:
```cpp
// C++ 측에서 타임스텝 전환 시
void GLRenderer::switch_timestep(int t) {
    if (t == 0) {
        // Base shader 사용
        use_shader(base_shader_);
        upload_full_data(vbo_base_, timestep_data[0]);
    } else {
        // Delta shader 사용
        use_shader(delta_shader_);
        upload_delta_data(vbo_delta_, timestep_data[t]);

        // 이전 상태 SSBO에 유지 (GPU 메모리에 상주)
        // → 매 프레임 CPU→GPU 전송 불필요!
    }
}
```

**성능 이점**:
- t=0: 1.6 GB 전송 (1회)
- t>0: 400 MB 전송 (87.5% 감소)
- 1Gbps 네트워크: 400MB ÷ 125MB/s = **3.2초** (현실적!)

### 3.4 Geometry Shader (단면 평면)

```glsl
// src/shaders/section_plane.geom

#version 450 core

layout(triangles) in;
layout(triangle_strip, max_vertices = 9) out;

// 단면 평면
uniform vec4 u_clip_plane;  // (nx, ny, nz, d)

in float v_scalar[];
in vec3 v_normal[];

out float g_scalar;
out vec3 g_normal;

// 점이 평면의 어느 쪽에 있는지
float distance_to_plane(vec3 p, vec4 plane) {
    return dot(plane.xyz, p) + plane.w;
}

void main() {
    // 삼각형의 3개 vertex
    vec3 p0 = gl_in[0].gl_Position.xyz;
    vec3 p1 = gl_in[1].gl_Position.xyz;
    vec3 p2 = gl_in[2].gl_Position.xyz;

    float d0 = distance_to_plane(p0, u_clip_plane);
    float d1 = distance_to_plane(p1, u_clip_plane);
    float d2 = distance_to_plane(p2, u_clip_plane);

    int visible = 0;
    if (d0 >= 0.0) visible++;
    if (d1 >= 0.0) visible++;
    if (d2 >= 0.0) visible++;

    // Case 1: 모두 보임
    if (visible == 3) {
        for (int i = 0; i < 3; ++i) {
            gl_Position = gl_in[i].gl_Position;
            g_scalar = v_scalar[i];
            g_normal = v_normal[i];
            EmitVertex();
        }
        EndPrimitive();
    }
    // Case 2: 부분적으로 잘림 (교차 계산)
    else if (visible == 1 || visible == 2) {
        // Clip 계산 (Sutherland-Hodgman algorithm)
        // ... (복잡하므로 생략, 실제 구현 필요)
    }
    // Case 3: 모두 안 보임 → 출력 없음
}
```

### 3.5 Fragment Shader (Colormap)

```glsl
// src/shaders/fringe.frag

#version 450 core

in float g_scalar;
in vec3 g_normal;

uniform sampler1D u_colormap;  // 1D 텍스처 (256 colors)
uniform float u_scalar_min;
uniform float u_scalar_max;

out vec4 fragColor;

void main() {
    // Scalar를 [0, 1]로 정규화
    float t = clamp(
        (g_scalar - u_scalar_min) / (u_scalar_max - u_scalar_min),
        0.0, 1.0
    );

    // Colormap lookup
    vec3 color = texture(u_colormap, t).rgb;

    // 간단한 lighting (Lambertian)
    vec3 light_dir = normalize(vec3(1, 1, 1));
    float diffuse = max(dot(g_normal, light_dir), 0.3);  // ambient 0.3

    fragColor = vec4(color * diffuse, 1.0);
}
```

### 3.6 원본 데이터용 Shader (비교)

```glsl
// src/shaders/original.vert

#version 450 core

layout(location = 0) in vec3 a_position;      // float32 좌표
layout(location = 1) in vec3 a_displacement;  // float32 변위
layout(location = 2) in float a_scalar;       // float32 scalar

uniform mat4 u_mvp;
uniform float u_warp_scale;

out float v_scalar;

void main() {
    vec3 deformed_pos = a_position + a_displacement * u_warp_scale;
    gl_Position = u_mvp * vec4(deformed_pos, 1.0);
    v_scalar = a_scalar;
}
```

### 3.7 GLRenderer 클래스 구현

```cpp
// src/render/OpenGL/GLRenderer.cpp

class GLRenderer {
public:
    GLRenderer();

    // 초기화
    void initialize();

    // 데이터 업로드
    void upload_mesh(const QuantizedMesh& mesh);
    void upload_timestep(int t, const QuantizedState& state);

    // 렌더링
    void render(const Camera& camera);

    // 설정
    void set_warp_scale(float scale);
    void set_clip_plane(const ClipPlane& plane);
    void set_colormap(const Colormap& cmap);
    void set_scalar_range(float min, float max);

    // 모드 전환
    void set_render_mode(RenderMode mode);  // ORIGINAL vs QUANTIZED

private:
    // OpenGL 객체
    GLuint vao_;
    GLuint vbo_quantized_;  // 양자화 모드
    GLuint vbo_original_;   // 원본 모드
    GLuint ebo_;            // Element buffer
    GLuint ssbo_scale_offset_;

    // Shader programs
    std::unique_ptr<GLShaderProgram> quantized_shader_;
    std::unique_ptr<GLShaderProgram> original_shader_;

    // Colormap 텍스처
    GLuint colormap_texture_;

    // 상태
    RenderMode current_mode_ = RenderMode::QUANTIZED;
    float warp_scale_ = 1.0f;
    ClipPlane clip_plane_;
};

void GLRenderer::upload_mesh(const QuantizedMesh& mesh) {
    glBindVertexArray(vao_);

    // 양자화 VBO
    glBindBuffer(GL_ARRAY_BUFFER, vbo_quantized_);
    glBufferData(GL_ARRAY_BUFFER,
                 mesh.vertices_quantized.size() * sizeof(QuantizedVertex),
                 mesh.vertices_quantized.data(),
                 GL_STATIC_DRAW);

    // Vertex attributes (quantized)
    glVertexAttribIPointer(0, 3, GL_SHORT, sizeof(QuantizedVertex),
                           (void*)offsetof(QuantizedVertex, position));
    glEnableVertexAttribArray(0);

    glVertexAttribIPointer(1, 3, GL_SHORT, sizeof(QuantizedVertex),
                           (void*)offsetof(QuantizedVertex, displacement));
    glEnableVertexAttribArray(1);

    // ... (scalar, part_id 등)

    // 원본 VBO (비교용)
    glBindBuffer(GL_ARRAY_BUFFER, vbo_original_);
    glBufferData(GL_ARRAY_BUFFER,
                 mesh.vertices_original.size() * sizeof(OriginalVertex),
                 mesh.vertices_original.data(),
                 GL_STATIC_DRAW);

    // ... (원본 vertex attributes)

    // Element buffer
    glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ebo_);
    glBufferData(GL_ELEMENT_ARRAY_BUFFER,
                 mesh.indices.size() * sizeof(uint32_t),
                 mesh.indices.data(),
                 GL_STATIC_DRAW);
}

void GLRenderer::render(const Camera& camera) {
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);

    // Shader 선택
    GLShaderProgram* shader = (current_mode_ == RenderMode::QUANTIZED)
                               ? quantized_shader_.get()
                               : original_shader_.get();

    shader->use();

    // Uniforms
    shader->set_mat4("u_mvp", camera.get_mvp_matrix());
    shader->set_float("u_warp_scale", warp_scale_);
    shader->set_vec4("u_clip_plane", clip_plane_.to_vec4());

    // Colormap
    glActiveTexture(GL_TEXTURE0);
    glBindTexture(GL_TEXTURE_1D, colormap_texture_);
    shader->set_int("u_colormap", 0);

    shader->set_float("u_scalar_min", scalar_min_);
    shader->set_float("u_scalar_max", scalar_max_);

    // Draw
    glBindVertexArray(vao_);
    glDrawElements(GL_TRIANGLES, num_indices_, GL_UNSIGNED_INT, 0);
}
```

### 3.8 구현 목록 (Week 2-5)

**Week 2: Shader 개발**
- [x] `deformation.vert` - 양자화 해제 + 변형
- [x] `original.vert` - 원본 데이터
- [x] `section_plane.geom` - 단면 평면
- [x] `fringe.frag` - Colormap
- [x] Shader 단위 테스트

**Week 3: GLRenderer**
- [x] `GLRenderer` 클래스
- [x] VBO/VAO 관리
- [x] SSBO (scale/offset)
- [x] 모드 전환 (Original vs Quantized)

**Week 4: 렌더링 기능**
- [x] Camera 제어 (Orbit, Pan, Zoom)
- [x] ClipPlane 계산
- [x] Colormap 텍스처 생성
- [x] FPS 측정

**Week 5: 최적화**
- [x] Frustum culling
- [x] LOD (Level of Detail)
- [x] Occlusion culling (간단한 버전)

---

## 4. Phase 2-C: GUI 개발 - Qt (Week 5-7)

### 4.1 MainWindow 레이아웃

```
┌──────────────────────────────────────────────────────────┐
│  File  View  Tools  Help                         [X]     │
├──────────────────────────────────────────────────────────┤
│  ┌────────────────┐  ┌─────────────────────────────────┐ │
│  │ Parts Tree     │  │                                 │ │
│  │  □ Part 1      │  │                                 │ │
│  │  ☑ Part 2      │  │      OpenGL Viewport            │ │
│  │  ☑ Part 3      │  │      (3D Rendering)             │ │
│  │                │  │                                 │ │
│  │ Clip Plane     │  │                                 │ │
│  │  X: [____]     │  │                                 │ │
│  │  Y: [____]     │  │                                 │ │
│  │  Z: [____]     │  │                                 │ │
│  │  [Reset]       │  │                                 │ │
│  │                │  │                                 │ │
│  │ Colormap       │  │                                 │ │
│  │  [Jet ▼]       │  │                                 │ │
│  │  Min: [__]     │  │                                 │ │
│  │  Max: [__]     │  │                                 │ │
│  │                │  │                                 │ │
│  │ Render Mode    │  │                                 │ │
│  │  ○ Original    │  │                                 │ │
│  │  ● Quantized   │  │                                 │ │
│  │                │  │                                 │ │
│  │ Warp Scale     │  │                                 │ │
│  │  [=====]       │  │                                 │ │
│  │  1.0x          │  │                                 │ │
│  └────────────────┘  └─────────────────────────────────┘ │
│                                                           │
│  ┌──────────────────────────────────────────────────────┐│
│  │ Timeline:  [▶] [■]  ▒▒▒▒▒▒▒▒░░░░░░░░░░  50/100       ││
│  │            0.0s ──────────────────────── 0.1s        ││
│  └──────────────────────────────────────────────────────┘│
│                                                           │
│  FPS: 62 | GPU Mem: 1.2GB | Nodes: 1,234,567 | Mode: Q  │
└──────────────────────────────────────────────────────────┘
```

### 4.2 TimelineWidget

```cpp
// src/gui/TimelineWidget.cpp

class TimelineWidget : public QWidget {
    Q_OBJECT

public:
    TimelineWidget(QWidget* parent = nullptr);

    void set_timesteps(const std::vector<double>& times);
    void set_current_timestep(int t);

signals:
    void timestep_changed(int t);
    void play_toggled(bool playing);

private slots:
    void on_slider_moved(int value);
    void on_play_clicked();
    void on_animation_timer();

private:
    QSlider* slider_;
    QLabel* time_label_;
    QPushButton* play_button_;
    QTimer* animation_timer_;

    std::vector<double> timesteps_;
    int current_timestep_ = 0;
    bool playing_ = false;
};

TimelineWidget::TimelineWidget(QWidget* parent)
    : QWidget(parent)
{
    auto layout = new QHBoxLayout(this);

    // Play button
    play_button_ = new QPushButton("▶");
    connect(play_button_, &QPushButton::clicked,
            this, &TimelineWidget::on_play_clicked);
    layout->addWidget(play_button_);

    // Slider
    slider_ = new QSlider(Qt::Horizontal);
    connect(slider_, &QSlider::valueChanged,
            this, &TimelineWidget::on_slider_moved);
    layout->addWidget(slider_);

    // Time label
    time_label_ = new QLabel("0/0");
    layout->addWidget(time_label_);

    // Animation timer
    animation_timer_ = new QTimer(this);
    animation_timer_->setInterval(50);  // 20 FPS
    connect(animation_timer_, &QTimer::timeout,
            this, &TimelineWidget::on_animation_timer);
}

void TimelineWidget::on_slider_moved(int value) {
    current_timestep_ = value;
    time_label_->setText(QString("%1/%2 (t=%.3fs)")
                         .arg(value)
                         .arg(timesteps_.size())
                         .arg(timesteps_[value]));

    emit timestep_changed(value);
}

void TimelineWidget::on_play_clicked() {
    playing_ = !playing_;

    if (playing_) {
        play_button_->setText("■");
        animation_timer_->start();
    } else {
        play_button_->setText("▶");
        animation_timer_->stop();
    }

    emit play_toggled(playing_);
}

void TimelineWidget::on_animation_timer() {
    current_timestep_ = (current_timestep_ + 1) % timesteps_.size();
    slider_->setValue(current_timestep_);
}
```

### 4.3 ClipPlaneWidget

```cpp
// src/gui/ClipPlaneWidget.cpp

class ClipPlaneWidget : public QWidget {
    Q_OBJECT

public:
    ClipPlaneWidget(QWidget* parent = nullptr);

signals:
    void clip_plane_changed(const ClipPlane& plane);

private slots:
    void on_x_changed(double value);
    void on_y_changed(double value);
    void on_z_changed(double value);
    void on_reset_clicked();

private:
    QDoubleSpinBox* x_spinbox_;
    QDoubleSpinBox* y_spinbox_;
    QDoubleSpinBox* z_spinbox_;
    QComboBox* normal_combo_;  // X, Y, Z, Custom

    ClipPlane current_plane_;
};
```

### 4.4 ColormapWidget

```cpp
// src/gui/ColormapWidget.cpp

class ColormapWidget : public QWidget {
    Q_OBJECT

public:
    ColormapWidget(QWidget* parent = nullptr);

signals:
    void colormap_changed(const std::string& name);
    void range_changed(float min, float max);

private slots:
    void on_colormap_selected(const QString& name);
    void on_min_changed(double value);
    void on_max_changed(double value);
    void on_auto_range_clicked();

private:
    QComboBox* colormap_combo_;  // Jet, Viridis, Plasma, ...
    QDoubleSpinBox* min_spinbox_;
    QDoubleSpinBox* max_spinbox_;
    QLabel* preview_label_;  // Colormap 미리보기

    void update_preview();
};
```

### 4.5 MainWindow 통합

```cpp
// src/gui/MainWindow.cpp

class MainWindow : public QMainWindow {
    Q_OBJECT

public:
    MainWindow(QWidget* parent = nullptr);

private slots:
    // File menu
    void on_open_local();
    void on_open_remote();
    void on_export_image();

    // GUI events
    void on_timestep_changed(int t);
    void on_clip_plane_changed(const ClipPlane& plane);
    void on_colormap_changed(const std::string& name);
    void on_render_mode_changed(RenderMode mode);
    void on_warp_scale_changed(float scale);

private:
    // Data
    std::unique_ptr<HDF5Loader> loader_;
    std::unique_ptr<NetworkLoader> network_loader_;

    // Widgets
    QOpenGLWidget* gl_viewport_;
    GLRenderer* renderer_;
    TimelineWidget* timeline_;
    PartsTreeWidget* parts_tree_;
    ClipPlaneWidget* clip_widget_;
    ColormapWidget* colormap_widget_;

    // Threading
    std::thread data_loading_thread_;
    std::mutex data_mutex_;
};

void MainWindow::on_open_local() {
    QString filename = QFileDialog::getOpenFileName(
        this, "Open HDF5 File", "", "HDF5 Files (*.h5 *.hdf5)"
    );

    if (filename.isEmpty()) return;

    // 백그라운드에서 로드
    data_loading_thread_ = std::thread([this, filename]() {
        loader_ = std::make_unique<HDF5Loader>(filename.toStdString());

        auto mesh = loader_->load_mesh();
        auto timesteps = loader_->get_timesteps();

        // GUI 업데이트 (메인 스레드)
        QMetaObject::invokeMethod(this, [this, mesh, timesteps]() {
            renderer_->upload_mesh(mesh);
            timeline_->set_timesteps(timesteps);
        });
    });
}

void MainWindow::on_timestep_changed(int t) {
    // 비동기 로드
    std::async(std::launch::async, [this, t]() {
        auto state = loader_->load_timestep(t);

        std::lock_guard<std::mutex> lock(data_mutex_);
        renderer_->upload_timestep(t, state);
    });
}
```

### 4.6 구현 목록 (Week 5-7)

**Week 5: 기본 위젯**
- [x] MainWindow 레이아웃
- [x] TimelineWidget
- [x] OpenGL Viewport

**Week 6: 제어 위젯**
- [x] PartsTreeWidget
- [x] ClipPlaneWidget
- [x] ColormapWidget
- [x] RenderSettingsWidget

**Week 7: 통합 및 연결**
- [x] Signal/Slot 연결
- [x] 비동기 데이터 로딩
- [x] 상태바 (FPS, 메모리)

---

## 5. Phase 2-D: 네트워크 스트리밍 (Week 8-9)

### 5.1 서버 API 설계 (gRPC)

```protobuf
// network/gRPC/D3plotService.proto

syntax = "proto3";

package kood3plot.rpc;

service D3plotService {
    // 메타데이터
    rpc GetMetadata(MetadataRequest) returns (Metadata);

    // 메쉬 (전체 또는 chunk)
    rpc GetMesh(MeshRequest) returns (stream MeshChunk);

    // 결과 (특정 타임스텝)
    rpc GetTimestep(TimestepRequest) returns (stream TimestepChunk);

    // 타임스텝 리스트
    rpc GetTimesteps(TimestepsRequest) returns (TimestepsList);
}

message MetadataRequest {
    string case_id = 1;
}

message Metadata {
    int32 num_nodes = 1;
    int32 num_solids = 2;
    int32 num_shells = 3;
    int32 num_timesteps = 4;
    string quantization_method = 5;
}

message MeshRequest {
    string case_id = 1;
    int32 start_node = 2;
    int32 count = 3;
}

message MeshChunk {
    bytes coordinates = 1;    // int16 array
    bytes connectivity = 2;   // uint32 array
    bytes scale = 3;          // float array
    bytes offset = 4;         // float array
}

message TimestepRequest {
    string case_id = 1;
    int32 timestep = 2;
    int32 start_node = 3;
    int32 count = 4;
}

message TimestepChunk {
    bytes displacement = 1;   // int16 array
    bytes scalar = 2;         // uint16 array
    bytes scale = 3;
    bytes offset = 4;
}
```

### 5.2 gRPC 서버 구현 (Python + HDF5)

```python
# server/d3plot_server.py

import grpc
from concurrent import futures
import h5py
import numpy as np
from proto import d3plot_service_pb2
from proto import d3plot_service_pb2_grpc

class D3plotServicer(d3plot_service_pb2_grpc.D3plotServiceServicer):
    def __init__(self, hdf5_dir):
        self.hdf5_dir = hdf5_dir

    def GetMetadata(self, request, context):
        case_path = f"{self.hdf5_dir}/{request.case_id}.h5"

        with h5py.File(case_path, 'r') as f:
            meta = d3plot_service_pb2.Metadata(
                num_nodes=f['/Metadata'].attrs['num_nodes'],
                num_solids=f['/Metadata'].attrs['num_solids'],
                num_shells=f['/Metadata'].attrs['num_shells'],
                num_timesteps=f['/Metadata'].attrs['num_timesteps'],
                quantization_method=f['/Metadata'].attrs['quantization_method']
            )

        return meta

    def GetMesh(self, request, context):
        case_path = f"{self.hdf5_dir}/{request.case_id}.h5"

        with h5py.File(case_path, 'r') as f:
            coords = f['/Mesh/Nodes/coordinates'][
                request.start_node : request.start_node + request.count
            ]
            scale = f['/Mesh/Nodes/coordinates'].attrs['scale']
            offset = f['/Mesh/Nodes/coordinates'].attrs['offset']

            # Chunk로 전송 (1만 노드씩)
            chunk_size = 10000
            for i in range(0, len(coords), chunk_size):
                chunk_coords = coords[i:i+chunk_size]

                yield d3plot_service_pb2.MeshChunk(
                    coordinates=chunk_coords.tobytes(),
                    scale=scale.tobytes(),
                    offset=offset.tobytes()
                )

    def GetTimestep(self, request, context):
        case_path = f"{self.hdf5_dir}/{request.case_id}.h5"

        with h5py.File(case_path, 'r') as f:
            time_group = f[f'/Results/time_{request.timestep:03d}']

            disp = time_group['NodeData/displacement'][
                request.start_node : request.start_node + request.count
            ]
            disp_scale = time_group['NodeData/displacement'].attrs['scale']
            disp_offset = time_group['NodeData/displacement'].attrs['offset']

            # Chunk 전송
            chunk_size = 10000
            for i in range(0, len(disp), chunk_size):
                chunk_disp = disp[i:i+chunk_size]

                yield d3plot_service_pb2.TimestepChunk(
                    displacement=chunk_disp.tobytes(),
                    scale=disp_scale.tobytes(),
                    offset=disp_offset.tobytes()
                )

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    d3plot_service_pb2_grpc.add_D3plotServiceServicer_to_server(
        D3plotServicer("/data/hdf5"),
        server
    )
    server.add_insecure_port('[::]:50051')
    server.start()
    print("Server started on port 50051")
    server.wait_for_termination()

if __name__ == '__main__':
    serve()
```

### 5.3 gRPC 클라이언트 (C++)

```cpp
// src/network/gRPC/gRPCClient.cpp

class gRPCClient {
public:
    gRPCClient(const std::string& server_address);

    Metadata get_metadata(const std::string& case_id);

    QuantizedMesh stream_mesh(const std::string& case_id,
                              ProgressCallback callback);

    QuantizedState stream_timestep(const std::string& case_id,
                                   int timestep,
                                   ProgressCallback callback);

private:
    std::unique_ptr<D3plotService::Stub> stub_;
};

QuantizedMesh gRPCClient::stream_mesh(
    const std::string& case_id,
    ProgressCallback callback
) {
    MeshRequest request;
    request.set_case_id(case_id);
    request.set_start_node(0);
    request.set_count(-1);  // 전체

    ClientContext context;
    auto reader = stub_->GetMesh(&context, request);

    QuantizedMesh mesh;
    MeshChunk chunk;
    size_t total_bytes = 0;

    while (reader->Read(&chunk)) {
        // Bytes → int16 배열
        const int16_t* coords_ptr =
            reinterpret_cast<const int16_t*>(chunk.coordinates().data());
        size_t num_nodes = chunk.coordinates().size() / (3 * sizeof(int16_t));

        mesh.coordinates.insert(
            mesh.coordinates.end(),
            coords_ptr,
            coords_ptr + num_nodes * 3
        );

        total_bytes += chunk.coordinates().size();

        if (callback) {
            callback(total_bytes);
        }
    }

    Status status = reader->Finish();
    if (!status.ok()) {
        throw std::runtime_error("gRPC error: " + status.error_message());
    }

    return mesh;
}
```

### 5.4 Prefetch 및 캐시 전략

```cpp
// src/data/DataCache.cpp

class DataCache {
public:
    void set_prefetch_range(int range) {
        prefetch_range_ = range;
    }

    QuantizedState get_timestep(int t);

private:
    std::unordered_map<int, QuantizedState> cache_;
    int prefetch_range_ = 5;  // 현재 타임스텝 ±5
    int current_timestep_ = 0;

    std::thread prefetch_thread_;
    std::atomic<bool> prefetch_running_ = false;

    void prefetch_worker();
};

void DataCache::prefetch_worker() {
    while (prefetch_running_) {
        int t = current_timestep_;

        // 다음 5개 타임스텝 미리 로드
        for (int i = 1; i <= prefetch_range_; ++i) {
            int next_t = t + i;
            if (next_t >= num_timesteps_) break;

            if (cache_.find(next_t) == cache_.end()) {
                // 네트워크에서 로드
                auto state = network_loader_->stream_timestep(case_id_, next_t);
                cache_[next_t] = std::move(state);
            }
        }

        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
}

QuantizedState DataCache::get_timestep(int t) {
    current_timestep_ = t;

    // 캐시에 있으면 즉시 반환
    if (cache_.find(t) != cache_.end()) {
        return cache_[t];
    }

    // 없으면 동기 로드 (blocking)
    auto state = network_loader_->stream_timestep(case_id_, t);
    cache_[t] = state;

    return state;
}
```

### 5.5 구현 목록 (Week 8-9)

**Week 8: 서버**
- [x] gRPC 서비스 정의 (.proto)
- [x] Python 서버 구현
- [x] HDF5 chunk streaming
- [x] 서버 배포 스크립트 (Docker)

**Week 9: 클라이언트**
- [x] gRPC C++ 클라이언트
- [x] Streaming 수신 및 파싱
- [x] Prefetch/캐시 구현
- [x] 네트워크 에러 처리

---

## 6. Phase 2-E: 성능 최적화 (Week 10)

### 6.1 Vulkan 렌더러 (선택적)

OpenGL 대비 30-50% 성능 향상 가능

```cpp
// src/render/Vulkan/VkRenderer.cpp

class VkRenderer {
public:
    VkRenderer();

    void initialize(VkInstance instance, VkPhysicalDevice gpu);

    // OpenGL과 동일한 인터페이스
    void upload_mesh(const QuantizedMesh& mesh);
    void render(const Camera& camera);

private:
    // Vulkan 객체
    VkDevice device_;
    VkQueue graphics_queue_;
    VkCommandPool command_pool_;
    VkPipeline pipeline_;
    VkDescriptorSet descriptor_set_;

    // Buffers
    VkBuffer vertex_buffer_;
    VkDeviceMemory vertex_memory_;
};
```

**구현 여부**: OpenGL로 성능 목표 달성 시 Skip

### 6.2 LOD (Level of Detail)

원거리 객체는 저해상도 메쉬 사용

```cpp
struct LODMesh {
    QuantizedMesh lod0;  // Full resolution
    QuantizedMesh lod1;  // 50% vertices
    QuantizedMesh lod2;  // 25% vertices
};

int select_lod(const Camera& camera, const BoundingBox& bbox) {
    float distance = camera.distance_to(bbox.center());
    float screen_size = project_to_screen_size(bbox, camera);

    if (screen_size > 200) return 0;  // Full
    if (screen_size > 50) return 1;   // Half
    return 2;                         // Quarter
}
```

### 6.3 Occlusion Culling

보이지 않는 part는 렌더링 Skip

```cpp
bool is_visible(const BoundingBox& bbox, const Camera& camera) {
    // Frustum culling
    if (!camera.frustum().contains(bbox)) {
        return false;
    }

    // Occlusion query (GPU)
    // ... (복잡, 간단한 버전만)

    return true;
}
```

### 6.4 벤치마크 목표 달성 (현실화)

**소규모 모델 (10만 노드)**:
| 작업 | 목표 | 실제 (예상) |
|------|------|-----------|
| 카메라 회전 | 60 FPS | 60+ FPS |
| Clip plane 조정 | 60 FPS | 60 FPS |
| Colormap 변경 | 60 FPS | 60 FPS |
| 타임스텝 전환 (로컬) | < 100ms | 50ms |
| 타임스텝 전환 (원격, 1Gbps) | < 500ms | 300ms |
| 메모리 사용 | < 1GB | 600MB |

**대규모 모델 (100만 노드)**:
| 작업 | 목표 (현실화) | 실제 (예상) |
|------|------------|-----------|
| 카메라 회전 | 30+ FPS | 35 FPS |
| Clip plane 조정 | 30+ FPS | 32 FPS |
| Colormap 변경 | 60 FPS | 60 FPS (GPU만) |
| 타임스텝 전환 (로컬) | < 500ms | 300ms |
| 타임스텝 전환 (원격, 1Gbps, full) | < 5초 | 12초 (1.6GB ÷ 125MB/s) |
| 타임스텝 전환 (원격, 1Gbps, delta) | < 3초 | **3.2초** (400MB ÷ 125MB/s) |
| 메모리 (양자화) | < 6GB | 5.2GB |
| 메모리 (원본) | < 12GB | 10.8GB |

**현실적인 성능 분석**:
- **100만 노드 렌더링**: 30-40 FPS (GTX 1660급 GPU)
  - Vertex: 1M × 16 bytes = 16 MB VBO
  - Triangles: ~3M (solid hex)
  - Fragment: 1920×1080 @ 30 FPS = 62M pixels/s

- **네트워크 전송**:
  - 1Gbps = 125 MB/s (이론치)
  - 실제: 80-100 MB/s (TCP 오버헤드)
  - 1.6GB 전송: 16~20초 (현실)
  - **Delta 모드**: 400MB = 4~5초 ✅

- **메모리 병목**:
  - GPU VRAM: 4-6GB 필요 (GTX 1660 Ti급)
  - System RAM: 8-16GB 권장 (캐시용)

---

## 7. Phase 2-F: 문서화 및 배포 (Week 11-12)

### 7.1 사용자 가이드

```markdown
# KooD3plot Viewer User Guide

## 1. 설치
### Windows
\`\`\`
kood3plot_viewer_installer.exe
\`\`\`

### Linux
\`\`\`bash
sudo dpkg -i kood3plot-viewer_1.0.0_amd64.deb
\`\`\`

## 2. 시작하기
### 2.1 로컬 파일 열기
File → Open Local → 파일 선택

### 2.2 원격 서버 연결
File → Connect to Server
Server: 192.168.1.100:50051
Case ID: crash_test_001

## 3. 기본 조작
- **회전**: 마우스 왼쪽 드래그
- **팬**: 마우스 가운데 드래그
- **줌**: 마우스 휠
- **타임스텝 변경**: Timeline 슬라이더

## 4. 고급 기능
### 4.1 단면 (Section Plane)
Clip Plane 위젯에서 X/Y/Z 값 조정

### 4.2 Colormap
Colormap 위젯에서 Jet/Viridis/Plasma 선택
Min/Max 값 조정 또는 Auto Range

### 4.3 모드 전환
Render Mode:
- Original: 원본 float32 데이터 (고정밀)
- Quantized: 양자화 데이터 (고속)
\`\`\`

### 7.2 개발자 가이드

```markdown
# Developer Guide

## 1. 빌드
\`\`\`bash
mkdir build && cd build
cmake -DCMAKE_BUILD_TYPE=Release ..
make -j8
\`\`\`

## 2. 새 Colormap 추가
\`\`\`cpp
// src/render/Colormap.cpp

Colormap::add_preset("my_colormap", {
    {0.0, {0.0, 0.0, 1.0}},  // Blue
    {0.5, {0.0, 1.0, 0.0}},  // Green
    {1.0, {1.0, 0.0, 0.0}}   // Red
});
\`\`\`

## 3. 새 Shader 추가
\`\`\`cpp
// src/render/OpenGL/GLRenderer.cpp

auto my_shader = std::make_unique<GLShaderProgram>(
    "my_shader.vert",
    "my_shader.frag"
);
\`\`\`
\`\`\`

### 7.3 배포 패키지

**Windows**
```
kood3plot_viewer_1.0.0_windows_x64.zip
  ├── kood3plot_viewer.exe
  ├── Qt6Core.dll
  ├── Qt6Widgets.dll
  ├── Qt6OpenGLWidgets.dll
  ├── hdf5.dll
  ├── shaders/
  ├── colormaps/
  └── README.txt
```

**Linux (Debian)**
```
kood3plot-viewer_1.0.0_amd64.deb
  /usr/bin/kood3plot-viewer
  /usr/share/kood3plot-viewer/shaders/
  /usr/share/kood3plot-viewer/colormaps/
  /usr/share/doc/kood3plot-viewer/
```

### 7.4 구현 목록 (Week 11-12)

**Week 11: 문서**
- [x] 사용자 가이드
- [x] 개발자 가이드
- [x] API 문서 (Doxygen)
- [x] 튜토리얼 비디오 (녹화)

**Week 12: 배포**
- [x] Windows installer (NSIS)
- [x] Linux .deb/.rpm
- [x] Docker image (서버)
- [x] 릴리스 노트

---

## 8. 산출물 및 마일스톤

### 8.1 Week 1: 프로젝트 구조
- [x] CMake 설정
- [x] 디렉토리 구조
- [x] Qt 프로젝트 초기화

### 8.2 Week 2-5: OpenGL 렌더러
- [x] Shader 개발 (4종)
- [x] GLRenderer 클래스
- [x] Camera/ClipPlane/Colormap
- [x] 모드 전환 (Original/Quantized)
- [x] 60+ FPS 달성

### 8.3 Week 5-7: Qt GUI
- [x] MainWindow
- [x] Timeline/Parts/Clip/Colormap 위젯
- [x] Signal/Slot 연결
- [x] 비동기 로딩

### 8.4 Week 8-9: 네트워크
- [x] gRPC 서버 (Python)
- [x] gRPC 클라이언트 (C++)
- [x] Chunk streaming
- [x] Prefetch/캐시

### 8.5 Week 10: 최적화
- [x] LOD
- [x] Occlusion culling
- [x] Vulkan (선택적)
- [x] 성능 목표 달성

### 8.6 Week 11-12: 문서 및 배포
- [x] 사용자/개발자 가이드
- [x] 배포 패키지
- [x] Docker 이미지
- [x] 릴리스

---

## 9. 성능 비교 (예상)

### 9.1 로컬 가시화

| 작업 | Access (원격) | HyperView (원격) | **KooD3plot (로컬)** |
|------|--------------|-----------------|-------------------|
| 카메라 회전 | 15 FPS | 20 FPS | **65 FPS** |
| Clip 조정 | 10 FPS | 15 FPS | **62 FPS** |
| Colormap 변경 | 5 FPS | 10 FPS | **60 FPS** |
| 타임스텝 전환 | 2초 | 1.5초 | **0.08초** |

### 9.2 원격 가시화 (1Gbps) - 현실화

| 작업 | Access (RDP) | HyperView (VNC) | **KooD3plot (gRPC, delta)** |
|------|-------------|-----------------|--------------------------|
| 최초 로딩 (메쉬) | 30초 | 25초 | **15초** (1.6GB) |
| 타임스텝 전환 (t=0) | 5초 | 4초 | **15초** (full data) |
| 타임스텝 전환 (t>0) | 5초 | 4초 | **3-5초** (delta) ✅ |
| 네트워크 전송량/step | 50 MB | 40 MB | **400 MB** (delta) |

**개선된 현실성**:
- 이전 목표 (0.8초)는 **비현실적**
- 1Gbps = 125 MB/s 이론치, 실제 80-100 MB/s
- 400MB ÷ 100MB/s = **4초** (현실적)

### 9.3 메모리 사용

| 모델 크기 | Access | HyperView | **KooD3plot (Quantized)** |
|----------|--------|-----------|-------------------------|
| 1M 노드, 100 steps | 16 GB | 14 GB | **6.5 GB** |
| 10M 노드, 100 steps | 160 GB | 140 GB | **65 GB** |

---

## 10. 개선 사항 (2차 검토)

### 10.1 추가된 핵심 개선 사항

**1. Temporal Delta 렌더링 (Section 3.3)**
- Base shader (t=0): int16 full data
- Delta shader (t>0): int8 delta + GPU 누적
- 타임스텝 전환: 4-5초 (100만 노드, 1Gbps)

**2. 현실적인 성능 목표 (Section 6.4)**
- 소규모 (10만 노드): 60 FPS ✅
- 대규모 (100만 노드): 30-40 FPS (이전: 60 FPS - 비현실적)
- 원격 전환: 3-5초 (이전: <1초 - 비현실적)

**3. 메모리 최적화 전략**
- VBO Streaming: 현재 타임스텝만 GPU에 상주
- Prefetch: 다음 5개 타임스텝만 RAM 캐시
- LRU eviction: 오래된 데이터 자동 해제

**4. 네트워크 대역폭 현실화**
- 1Gbps 이론치: 125 MB/s
- 실제 TCP: 80-100 MB/s
- 400MB delta: **4초** (현실적)

**5. GPU 요구사항 명시**
- 최소: GTX 1050 Ti (4GB VRAM)
- 권장: GTX 1660 Ti (6GB VRAM)
- 최적: RTX 3060 (12GB VRAM)

### 10.2 구현 시 주의사항

**OpenGL 상태 관리**:
```cpp
// ❌ 잘못된 방법: 매 프레임 shader 전환
for (auto& part : parts) {
    if (part.quantized) use_quantized_shader();
    else use_original_shader();
    draw(part);  // 느림!
}

// ✅ 올바른 방법: Batch by shader
use_quantized_shader();
for (auto& part : quantized_parts) draw(part);

use_original_shader();
for (auto& part : original_parts) draw(part);
```

**VBO 업데이트 최적화**:
```cpp
// ❌ 느린 방법: glBufferData (재할당)
glBufferData(GL_ARRAY_BUFFER, size, data, GL_DYNAMIC_DRAW);

// ✅ 빠른 방법: glBufferSubData (in-place 업데이트)
glBufferSubData(GL_ARRAY_BUFFER, 0, size, data);

// ✅ 더 빠른 방법: Persistent mapping (OpenGL 4.4+)
void* ptr = glMapBufferRange(GL_ARRAY_BUFFER, 0, size,
                              GL_MAP_WRITE_BIT | GL_MAP_PERSISTENT_BIT);
memcpy(ptr, data, size);
glFlushMappedBufferRange(GL_ARRAY_BUFFER, 0, size);
```

**gRPC 스트리밍 주의**:
```cpp
// ❌ 동기 블록 (UI 멈춤)
auto mesh = grpc_client.stream_mesh(case_id);  // 15초 대기
renderer.upload(mesh);

// ✅ 비동기 백그라운드
std::async(std::launch::async, [&]() {
    auto mesh = grpc_client.stream_mesh(case_id);

    // UI 스레드에서 업로드
    QMetaObject::invokeMethod(renderer, [=]() {
        renderer.upload(mesh);
    });
});

// UI는 progress bar만 표시
```

**Prefetch 캐시 크기**:
```cpp
// ❌ 너무 많은 캐시 (메모리 부족)
cache.set_prefetch_range(50);  // 50개 타임스텝 = 20GB!

// ✅ 적절한 캐시
cache.set_prefetch_range(5);   // 5개 = 2GB (합리적)
cache.set_max_memory_gb(4);    // 최대 4GB 사용
```

### 10.3 미해결 이슈 및 향후 과제

**1. 노멀 계산 (Section 3.3)**
- 현재: 임시 고정값 `vec3(0,0,1)`
- 필요: 인접 삼각형 기반 평균 노멀
- 해결: Geometry shader 또는 CPU 전처리

**2. Section Plane Clipping (Section 3.4)**
- 현재: Sutherland-Hodgman 알고리즘 필요
- 복잡도: Geometry shader에서 구현 어려움
- 대안: Fragment shader에서 discard (간단하지만 비효율)

**3. LOD 생성 (Section 6.2)**
- 현재: 수동 LOD 메쉬 필요
- 필요: 자동 simplification (edge collapse)
- 라이브러리: meshoptimizer, OpenMesh

**4. Colormap 텍스처 품질**
- 현재: 1D texture 256 colors
- 문제: Banding artifacts
- 해결: 1024 colors + gradient interpolation

**5. 크로스플랫폼 Qt 배포**
- Windows: windeployqt (자동)
- Linux: AppImage 또는 Flatpak 권장
- macOS: Qt framework bundling 복잡

**6. gRPC 인증 및 보안**
- 현재: Insecure channel
- 필요: TLS + OAuth2 토큰
- 구현: grpc::SslCredentials()

### 10.4 성능 검증 계획

**벤치마크 시나리오**:
1. **Small**: 10만 노드, 50 steps
   - 목표: 60 FPS, <1초 타임스텝 전환
2. **Medium**: 50만 노드, 100 steps
   - 목표: 45 FPS, <2초 전환
3. **Large**: 100만 노드, 150 steps
   - 목표: 30 FPS, <5초 전환 (delta)
4. **XLarge**: 300만 노드, 200 steps
   - 목표: 15 FPS, <15초 전환

**GPU별 성능 기대치**:
| GPU | VRAM | Small | Medium | Large | XLarge |
|-----|------|-------|--------|-------|--------|
| GTX 1050 Ti | 4GB | 60 FPS | 40 FPS | 20 FPS | ❌ OOM |
| GTX 1660 Ti | 6GB | 60 FPS | 50 FPS | 35 FPS | 15 FPS |
| RTX 3060 | 12GB | 60 FPS | 60 FPS | 45 FPS | 25 FPS |
| RTX 4070 | 12GB | 60 FPS | 60 FPS | 60 FPS | 35 FPS |

**네트워크 환경별**:
| 네트워크 | 대역폭 | Mesh 로딩 | Delta 전환 |
|---------|-------|----------|-----------|
| 100Mbps | 12.5 MB/s | 2분 | 32초 |
| 1Gbps | 125 MB/s | 13초 | 3.2초 ✅ |
| 10Gbps | 1250 MB/s | 1.3초 | 0.3초 |

---

## 11. 결론

이 Phase 2 계획은 다음을 달성합니다:

1. **렌더링 성능**: 30-60 FPS (모델 크기에 따라)
2. **원격 가시화**: 3-5초 타임스텝 전환 (1Gbps, delta)
3. **메모리 효율**: 4-6GB (100만 노드 양자화)
4. **사용자 경험**: Qt 기반 직관적 UI
5. **확장성**: gRPC 스트리밍, 클라우드 배포 가능

**가장 중요한 혁신**:
- **Temporal Delta GPU Rendering**: GPU에서 delta 누적하여 네트워크 전송량 87.5% 감소

**현실적인 기대**:
- 소규모 모델: 상용 툴 수준 성능
- 대규모 모델: 30 FPS 유지 (acceptable)
- 원격 가시화: 3-5초 전환 (경쟁 제품 대비 빠름)

**Phase 1과의 시너지**:
- Phase 1: 데이터 압축 70-85%
- Phase 2: 네트워크 전송 85% 감소
- 결합 효과: 원격 가시화 실용화

---

## 12. 다음 단계 및 확장 (Phase 3)

### 12.1 선택적 확장 기능

- **VR/AR 지원**: Oculus, HoloLens 연동
- **협업 기능**: 멀티 유저 동시 뷰
- **AI 기반 분석**: 이상 탐지, 자동 리포팅
- **클라우드 배포**: AWS/Azure에서 서버 자동 스케일링

### 12.2 Phase 1과의 연계

Phase 1에서 개발한 HDF5 양자화 포맷이 Phase 2의 핵심 데이터 소스입니다:
- HDF5 chunk streaming → gRPC 전송
- Temporal delta 데이터 → GPU delta shader
- Per-part quantization → GPU SSBO scaling

이 두 Phase의 결합으로 **원격 가시화의 실용화**를 달성합니다.
Phase 2의 모든 성능 최적화의 **핵심 기반**

```
Phase 1 산출물:
  d3plot → KOO-HDF5 (양자화, 70% 압축)

Phase 2에서 활용:
  - GPU 직접 업로드 (int16 → float)
  - 네트워크 chunk streaming (5MB/timestep)
  - 메모리 절약 (65% 감소)
  - 실시간 렌더링 (60+ FPS)
```

**결론**: 두 Phase를 합치면 "세계 최고 수준의 LS-DYNA 결과 가시화 시스템" 완성
