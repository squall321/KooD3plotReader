# KooD3plotReader 구현 로드맵

**작성일**: 2024-12-06
**최종 업데이트**: 2024-12-15
**상태**: Phase 1 완료, Phase 2 진행 중

---

## 1. 현재 상황 요약

### 1.1 완료된 작업 ✅

**KooD3plot 라이브러리 (V1)** - 완료:
- [x] D3plotReader: 바이너리 파싱 완료
- [x] StateDataParser: 타임스텝 데이터 읽기 (178배 고속화)
- [x] VectorMath: Vec3, StressTensor 유틸리티
- [x] Analysis 모듈: Von Mises, 주응력 계산
- [x] CLI 도구: 기본 query/info 모드
- [x] Windows 빌드 시스템: build.bat (static/shared lib)

**Phase 1: HDF5 양자화 시스템** - 완료 ✅:
- [x] HDF5Writer 클래스 구현 (`include/kood3plot/hdf5/`)
- [x] QuantizationEngine 구현 (`include/kood3plot/quantization/`)
- [x] Temporal delta compression 구현 (`include/kood3plot/compression/`)
- [x] CLI에 export 모드 추가
- [x] Profile 시스템 구현
- [x] 벤치마크 및 테스트

**Phase 2: .NET 시각화 앱** - 진행 중 (70% 완료):
- [x] UI 프레임워크 결정: **.NET 8 + Avalonia** 선택
- [x] 프로젝트 구조 (`vis-app-net/`)
- [x] KooD3plot.Data 라이브러리 (HDF5 로더)
- [x] KooD3plot.Rendering 라이브러리
- [x] GPU 렌더링 (Veldrid - Vulkan/D3D11)
- [x] 소프트웨어 렌더링 폴백
- [x] 비동기 메시 로딩
- [x] 기본 카메라 컨트롤 (회전, 줌, 패닝)
- [x] Jet colormap 렌더링
- [x] 디버그 로그 패널
- [ ] 클립 플레인
- [ ] 컬러맵 선택 UI
- [ ] 타임라인 재생
- [ ] gRPC 서버/클라이언트
- [ ] 원격 스트리밍

### 1.2 미완료 작업 ⏳

**Phase 2 남은 작업**:
- [ ] 클립 플레인 (X/Y/Z plane clipping)
- [ ] 컬러맵 선택 및 범위 조절
- [ ] 애니메이션 재생 컨트롤
- [ ] 노드/요소 선택 및 정보 표시
- [ ] gRPC 네트워킹 (원격 데이터 스트리밍)
- [ ] 성능 최적화 (LOD, 프러스텀 컬링)

---

## 2. 핵심 의사결정 사항

### 2.1 Phase 1 우선 vs Phase 2 우선?

**결정**: **Phase 1을 먼저 완료** ✅ **완료됨**

**이유**:
1. Phase 2는 Phase 1의 HDF5 양자화 데이터에 의존
2. HDF5 포맷이 확정되어야 렌더러 설계 가능
3. Phase 1은 독립적으로 유용 (데이터 압축 도구)
4. 테스트 데이터 생성 (Phase 2 개발 시 필요)

**실제 일정**:
```
Week 1-2:  Phase 1 구현 (HDF5 양자화) ✅ 완료
Week 3-4:  Phase 2 기반 구축 (.NET + Avalonia) ✅ 완료
Week 5-6:  GPU 렌더링 구현 (Veldrid) ✅ 완료
Week 7-8:  UI 기능 추가 (진행 중)
```

### 2.2 Qt/C++ vs .NET 중 어떤 것?

**최종 결정**: **.NET 8 + Avalonia** ✅

**선택 이유**:
1. **빠른 개발 속도**: async/await, LINQ, Hot Reload
2. **Veldrid 성공**: Vulkan/D3D11 백엔드 안정적 동작
3. **HDF5.NET 호환성**: HDF.PInvoke로 C++ HDF5 파일 직접 읽기 가능
4. **크로스플랫폼**: Windows/Linux/macOS 단일 코드베이스

**현재 아키텍처**:
```
vis-app-net/
├── KooD3plot.Data/        # HDF5 데이터 로더
├── KooD3plot.Rendering/   # 렌더링 추상화
└── KooD3plotViewer/       # Avalonia UI 앱
    └── Rendering/
        └── GpuMeshRenderer.cs  # Veldrid GPU 렌더러
```

**GPU 렌더링 상태**:
- Vulkan: 기본 백엔드 (Windows/Linux)
- D3D11: Windows 폴백
- 소프트웨어: 최종 폴백 (작동 확인됨)

---

## 3. Phase 1 구현 결과 (완료)

### 3.1 구현 완료 요약

#### Week 1-2: 핵심 인프라 ✅ 완료
**구현된 클래스**:

```cpp
// include/kood3plot/hdf5/HDF5Writer.hpp
class HDF5Writer {
    void create_file(const std::string& path);
    void write_mesh(const Mesh& mesh);
    void write_timestep(int t, const StateData& state);
    void close();
};

// include/kood3plot/quantization/QuantizationConfig.hpp
class QuantizationConfig {
    PhysicalType type;
    Unit unit;
    double precision;
    int compute_required_bits();
};
```

**산출물**:
- [x] `include/kood3plot/hdf5/HDF5Writer.hpp` ✅
- [x] `src/hdf5/HDF5Writer.cpp` ✅
- [x] `include/kood3plot/quantization/QuantizationConfig.hpp` ✅
- [x] 기본 테스트: mesh 저장/로드 ✅

**상태**: ✅ 완료

#### Week 2: 양자화 엔진 ✅ 완료

**구현된 클래스**:
- `include/kood3plot/quantization/Quantizers.hpp` ✅
- `src/quantization/DisplacementQuantizer.cpp` ✅
- `src/quantization/VonMisesQuantizer.cpp` ✅
- 정밀도 검증 테스트 ✅

**상태**: ✅ 완료

#### Week 3: Temporal Delta ✅ 완료

**구현된 클래스**:
- `include/kood3plot/compression/TemporalDelta.hpp` ✅
- `src/compression/TemporalDelta.cpp` ✅
- Delta overflow 처리 (escape code) ✅
- 압축률 측정 테스트 ✅

**상태**: ✅ 완료

#### Week 4: HDF5 메타데이터 시스템 ✅ 완료

**구현된 클래스**:
- 메타데이터 스키마 정의 ✅
- HDF5 attribute 자동 쓰기/읽기 ✅
- `KooHDF5Reader` 클래스 (자동 역양자화) ✅

**상태**: ✅ 완료

#### Week 5-6: Profile 시스템 + 최적화 ✅ 완료

**산출물**:
- YAML 파서 (yaml-cpp 사용) ✅
- Profile 로더 ✅
- CLI export 모드 구현 ✅
- 벤치마크 예제 (`examples/02_hdf5_benchmark.cpp`) ✅

**성능 결과**:
- Small (500MB): < 10초 ✅
- Medium (5GB): < 90초 ✅
- 압축률: 70-85% 달성 ✅

**상태**: ✅ 완료

### 3.2 문서화 및 예제 (부분 완료)

**예제 코드**:
- [x] `examples/01_basic_hdf5_export.cpp` ✅
- [x] `examples/02_hdf5_benchmark.cpp` ✅
- [ ] `examples/03_read_hdf5.cpp`
- [ ] `examples/04_python_hdf5.py`

**문서**:
- [x] `DEVELOPMENT_SETUP.md` ✅
- [x] `READY_TO_START.md` ✅
- [x] `vis-app-net/docs/DOTNET_VISUALIZATION_APP.md` ✅
- [ ] `USAGE_HDF5.md`: HDF5 변환 가이드
- [ ] `API_REFERENCE.md`: 라이브러리 API

---

## 4. Phase 2 구현 현황 (.NET 시각화 앱)

### 4.1 완료된 컴포넌트 ✅

**KooD3plot.Data 라이브러리**:
- [x] `Hdf5DataLoader.cs`: HDF5 파일 로딩
- [x] `MeshData.cs`: 메시 데이터 구조
- [x] `StateData.cs`: 타임스텝 상태 데이터

**KooD3plotViewer 앱**:
- [x] `MainWindow.axaml`: Avalonia UI 레이아웃
- [x] `MainWindowViewModel.cs`: MVVM 뷰모델
- [x] `VeldridView.axaml.cs`: GPU/소프트웨어 렌더링 뷰
- [x] `GpuMeshRenderer.cs`: Veldrid GPU 렌더러

**렌더링 기능**:
- [x] Vulkan/D3D11 GPU 렌더링 (Veldrid)
- [x] 소프트웨어 렌더링 폴백
- [x] 마우스 회전/줌/패닝
- [x] Jet colormap (Von Mises 스트레스)
- [x] 3축 기즈모 표시
- [x] 비동기 메시 로딩 (UI 블록 방지)
- [x] 디버그 로그 패널

### 4.2 진행 중 작업 🔄

**UI 기능**:
- [ ] 클립 플레인 (X/Y/Z 단면 절단)
- [ ] 컬러맵 선택 드롭다운
- [ ] 컬러 범위 수동 조절
- [ ] 타임라인 재생 컨트롤

### 4.3 향후 작업 ⏳

**Week 7-8 계획**:
- [ ] 타임스텝 애니메이션
- [ ] 노드/요소 피킹 (선택)
- [ ] 정보 패널 (선택된 노드 데이터)

**Week 9+ 계획**:
- [ ] gRPC 서버 (원격 데이터 스트리밍)
- [ ] LOD (Level of Detail)
- [ ] 프러스텀 컬링

---

## 5. 크로스플랫폼 전략

### 4.0 플랫폼 지원 요구사항

**필수 지원 플랫폼**:
- ✅ Windows (Visual Studio 2019+, MSVC)
- ✅ Linux (GCC 9+, Clang 10+)
- ✅ macOS (Apple Clang, arm64 + x86_64)

**크로스플랫폼 원칙**:
1. **표준 C++17만 사용** - 플랫폼별 확장 금지
2. **CMake 기반 빌드** - 모든 플랫폼 단일 빌드 시스템
3. **의존성 최소화** - vcpkg/conan으로 통일
4. **조건부 컴파일 최소화** - `#ifdef _WIN32` 사용 자제
5. **파일 경로 처리** - `std::filesystem` 사용 (C++17)

### 4.0.1 크로스플랫폼 빌드 시스템

**CMakeLists.txt 전략**:
```cmake
cmake_minimum_required(VERSION 3.15)
project(KooD3plotReader VERSION 1.0.0 LANGUAGES CXX)

# C++17 필수
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)  # GNU 확장 비활성화

# 크로스플랫폼 컴파일러 플래그
if(MSVC)
    add_compile_options(/W4 /utf-8)
    add_compile_definitions(_CRT_SECURE_NO_WARNINGS)
else()
    add_compile_options(-Wall -Wextra -pedantic)
endif()

# 의존성 (vcpkg 권장)
find_package(HDF5 REQUIRED COMPONENTS CXX)
find_package(yaml-cpp REQUIRED)

# 선택적 의존성
find_package(Blosc)
if(Blosc_FOUND)
    target_compile_definitions(kood3plot PRIVATE HAS_BLOSC)
endif()

# OpenMP (크로스플랫폼)
find_package(OpenMP)
if(OpenMP_CXX_FOUND)
    target_link_libraries(kood3plot PUBLIC OpenMP::OpenMP_CXX)
endif()
```

### 4.0.2 의존성 설치 가이드

**Windows (vcpkg)**:
```powershell
# vcpkg 설치
git clone https://github.com/microsoft/vcpkg.git
cd vcpkg
.\bootstrap-vcpkg.bat

# 의존성 설치
.\vcpkg install hdf5[cpp]:x64-windows
.\vcpkg install yaml-cpp:x64-windows
.\vcpkg install blosc:x64-windows  # 선택적

# CMake 통합
.\vcpkg integrate install
```

**Linux (Ubuntu/Debian)**:
```bash
# 필수 의존성
sudo apt update
sudo apt install build-essential cmake
sudo apt install libhdf5-dev
sudo apt install libyaml-cpp-dev

# 선택적
sudo apt install libblosc-dev

# 또는 vcpkg 사용 (권장)
git clone https://github.com/microsoft/vcpkg.git
cd vcpkg
./bootstrap-vcpkg.sh
./vcpkg install hdf5[cpp]:x64-linux yaml-cpp:x64-linux
```

**macOS (Homebrew)**:
```bash
# Homebrew로 의존성 설치
brew install cmake
brew install hdf5
brew install yaml-cpp
brew install c-blosc  # 선택적

# 또는 vcpkg (ARM Mac 지원 우수)
git clone https://github.com/microsoft/vcpkg.git
cd vcpkg
./bootstrap-vcpkg.sh
./vcpkg install hdf5[cpp]:arm64-osx yaml-cpp:arm64-osx
```

### 4.0.3 파일 시스템 처리 (크로스플랫폼)

**경로 처리**:
```cpp
#include <filesystem>  // C++17

namespace fs = std::filesystem;

// ✅ 크로스플랫폼 경로 처리
fs::path get_output_path(const std::string& input) {
    fs::path input_path(input);
    fs::path output_path = input_path.parent_path() /
                          (input_path.stem().string() + ".h5");
    return output_path;
}

// ✅ 디렉토리 생성
fs::path output_dir = "output/hdf5";
if (!fs::exists(output_dir)) {
    fs::create_directories(output_dir);  // 재귀적 생성
}

// ❌ 플랫폼별 구분자 사용 금지
// std::string path = "output\\data.h5";  // Windows only!

// ✅ 자동 변환
fs::path path = fs::path("output") / "data.h5";  // 모든 플랫폼
```

### 4.0.4 엔디안 처리

**D3plot은 빅엔디안 가능**:
```cpp
#include <bit>  // C++20
#include <cstdint>

// C++17 호환 엔디안 변환
inline uint32_t swap_endian_32(uint32_t val) {
    return ((val & 0x000000FF) << 24) |
           ((val & 0x0000FF00) << 8) |
           ((val & 0x00FF0000) >> 8) |
           ((val & 0xFF000000) >> 24);
}

inline float swap_endian_float(float val) {
    uint32_t tmp;
    std::memcpy(&tmp, &val, sizeof(float));
    tmp = swap_endian_32(tmp);
    std::memcpy(&val, &tmp, sizeof(float));
    return val;
}

// 사용
bool is_big_endian = (file_type == 5 || file_type == 6);
if (is_big_endian != std::endian::native == std::endian::big) {
    value = swap_endian_float(value);
}
```

### 4.0.5 크로스플랫폼 빌드 스크립트

**build.sh (Linux/macOS)**:
```bash
#!/bin/bash
set -e

echo "========================================="
echo " KooD3plotReader Cross-Platform Build"
echo "========================================="

# 플랫폼 감지
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    PLATFORM="Linux"
    GENERATOR="Unix Makefiles"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    PLATFORM="macOS"
    GENERATOR="Unix Makefiles"
else
    echo "Unsupported platform: $OSTYPE"
    exit 1
fi

echo "Platform: $PLATFORM"

# 의존성 확인
if ! command -v cmake &> /dev/null; then
    echo "[ERROR] CMake not found. Install: sudo apt install cmake"
    exit 1
fi

# 빌드
mkdir -p build
cd build

cmake -G "$GENERATOR" \
      -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_INSTALL_PREFIX=../installed \
      -DKOOD3PLOT_BUILD_TESTS=ON \
      -DKOOD3PLOT_BUILD_EXAMPLES=ON \
      ..

cmake --build . --config Release --parallel $(nproc 2>/dev/null || sysctl -n hw.ncpu)
cmake --install .

echo ""
echo "========================================="
echo " Build Complete!"
echo "========================================="
echo "Installed to: $(pwd)/../installed"
```

**build.bat (Windows)** - 기존 유지:
```batch
@echo off
REM 기존 build.bat 그대로 사용
REM Visual Studio 2019/2022 지원
```

### 4.0.6 크로스플랫폼 테스트 전략

**CI/CD (GitHub Actions)**:
```yaml
# .github/workflows/build.yml
name: Cross-Platform Build

on: [push, pull_request]

jobs:
  build:
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]
        include:
          - os: ubuntu-latest
            triplet: x64-linux
          - os: windows-latest
            triplet: x64-windows
          - os: macos-latest
            triplet: arm64-osx

    runs-on: ${{ matrix.os }}

    steps:
    - uses: actions/checkout@v3

    - name: Install vcpkg
      run: |
        git clone https://github.com/microsoft/vcpkg.git
        ./vcpkg/bootstrap-vcpkg.sh  # Linux/Mac
        # ./vcpkg/bootstrap-vcpkg.bat  # Windows

    - name: Install dependencies
      run: |
        ./vcpkg/vcpkg install hdf5[cpp]:${{ matrix.triplet }}
        ./vcpkg/vcpkg install yaml-cpp:${{ matrix.triplet }}

    - name: Build
      run: |
        cmake -B build -S . \
          -DCMAKE_TOOLCHAIN_FILE=./vcpkg/scripts/buildsystems/vcpkg.cmake
        cmake --build build --config Release

    - name: Test
      run: |
        cd build
        ctest -C Release --output-on-failure
```

### 4.0.7 플랫폼별 주의사항

**Windows 특이사항**:
```cpp
// ❌ MSVC에서 M_PI 미정의
// #include <cmath>
// double pi = M_PI;  // 컴파일 에러!

// ✅ 대안
#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

// 또는 constexpr 사용
constexpr double PI = 3.14159265358979323846;
```

**macOS 특이사항**:
```cpp
// OpenMP 기본 비활성화
// Homebrew libomp 설치 필요
// brew install libomp

// CMakeLists.txt
if(APPLE)
    set(OpenMP_CXX_FLAGS "-Xpreprocessor -fopenmp")
    set(OpenMP_CXX_LIB_NAMES "omp")
    set(OpenMP_omp_LIBRARY omp)
endif()
```

**Linux 특이사항**:
```bash
# HDF5 버전 확인 (1.10+ 필요)
dpkg -l | grep libhdf5

# 구버전인 경우 수동 빌드
wget https://support.hdfgroup.org/ftp/HDF5/releases/hdf5-1.14/...
tar -xzf hdf5-1.14.x.tar.gz
cd hdf5-1.14.x
./configure --prefix=/usr/local --enable-cxx
make -j$(nproc)
sudo make install
```

---

## 4.1 기술적 결정 사항

### 4.1.1 HDF5 압축 전략

**Phase 1 (초기)**:
- gzip level 6 (기본 내장)
- 크로스플랫폼 100% 호환
- 60% 추가 압축

**Phase 2 (최적화)**:
- blosc + zstd (플러그인)
- 70% 압축, 2배 빠름
- Fallback to gzip if unavailable

**구현**:
```cpp
CompressionType select_compression() {
    if (H5Zfilter_avail(H5Z_FILTER_BLOSC)) {
        return BLOSC_ZSTD;
    }
    return GZIP;  // Always available
}
```

### 4.2 메모리 관리 전략

**스트리밍 방식** (필수):
```cpp
// ❌ 전체 로드 (메모리 부족)
auto states = reader.read_all_states();  // 수십 GB!

// ✅ 스트리밍
for (int t = 0; t < num_timesteps; ++t) {
    auto state = reader.read_state(t);
    quantize_and_write(state);
    // auto delete
}
```

**메모리 제한**:
- 최대 사용량: 4GB (대부분 시스템)
- Timestep 버퍼: 2개 (current + previous for delta)
- VBO 업로드 버퍼: 500MB

### 4.3 병렬화 전략

**양자화 병렬화** (OpenMP):
```cpp
#pragma omp parallel for
for (int i = 0; i < num_nodes; ++i) {
    quantized[i] = quantizer.quantize(data[i]);
}
```

**HDF5 쓰기는 순차** (파일 I/O 경합 방지):
```cpp
// ✅ 양자화만 병렬
#pragma omp parallel for
for (int t = 0; t < N; ++t) {
    quantized[t] = quantize(states[t]);
}

// HDF5 쓰기는 순차
for (int t = 0; t < N; ++t) {
    writer.write(quantized[t]);
}
```

### 4.4 의존성 관리

**필수 의존성**:
- HDF5 (>= 1.10): `apt install libhdf5-dev` / vcpkg
- yaml-cpp: Profile 파싱
- (선택) blosc: 고급 압축

**빌드 시스템**:
```cmake
find_package(HDF5 REQUIRED COMPONENTS CXX)
find_package(yaml-cpp REQUIRED)

# Optional
find_package(Blosc)
if(Blosc_FOUND)
    target_compile_definitions(kood3plot PRIVATE USE_BLOSC)
endif()
```

---

## 5. 테스트 전략

### 5.1 단위 테스트

**양자화 정밀도**:
```cpp
TEST(DisplacementQuantizer, Precision) {
    std::vector<Vec3> data = generate_test_data();

    DisplacementQuantizer q;
    q.set_precision(0.01);  // 0.01mm
    q.calibrate(data);

    for (const auto& original : data) {
        auto quantized = q.quantize(original);
        auto restored = q.dequantize(quantized);

        double error = (restored - original).magnitude();
        EXPECT_LT(error, 0.01);  // 정밀도 보장
    }
}
```

**Temporal Delta**:
```cpp
TEST(TemporalDelta, Lossless) {
    auto base = generate_timestep(0);
    auto next = generate_timestep(1);

    auto delta = compressor.compute_delta(next, base);
    auto restored = compressor.apply_delta(base, delta);

    EXPECT_EQ(next, restored);  // 무손실 복원
}
```

### 5.2 통합 테스트

**End-to-End**:
```cpp
TEST(HDF5Export, FullWorkflow) {
    // 1. Read D3plot
    D3plotReader reader("test.d3plot");
    reader.open();

    // 2. Export to HDF5
    HDF5Writer writer("test.h5", "default");
    for (int t = 0; t < 10; ++t) {
        auto state = reader.read_state(t);
        writer.write_timestep(t, state);
    }
    writer.close();

    // 3. Read back and verify
    HDF5Reader reader2("test.h5");
    auto disp = reader2.read_displacement(5);

    // 4. Check precision
    auto original = reader.read_state(5).node_displacement;
    check_precision(original, disp, 0.01);
}
```

### 5.3 성능 벤치마크

**실제 데이터셋**:
- Small: 10만 노드 × 50 steps (500MB)
- Medium: 50만 노드 × 100 steps (5GB)
- Large: 100만 노드 × 150 steps (15GB)

**측정 항목**:
```cpp
struct BenchmarkResult {
    double read_time_sec;
    double quantize_time_sec;
    double write_time_sec;
    double total_time_sec;

    size_t original_size_bytes;
    size_t compressed_size_bytes;
    double compression_ratio;

    double max_displacement_error_mm;
    double max_stress_relative_error;
};
```

---

## 6. 위험 요소 및 대응책

### 6.1 기술적 위험

**위험 1**: HDF5 압축 성능 부족
- 증상: 10GB 변환에 10분 이상 소요
- 대응: blosc 압축 필수, chunking 튜닝
- 최악: 압축 비활성화 옵션 제공

**위험 2**: Temporal delta overflow 빈번
- 증상: int8 범위 초과 빈번 (>10%)
- 대응: Keyframe 간격 단축 (10 → 5)
- 최악: int16 delta로 변경 (압축률 감소)

**위험 3**: 메모리 부족 (대형 모델)
- 증상: 300만 노드 모델에서 OOM
- 대응: 스트리밍 강화, chunk 처리
- 최악: 64-bit only, 16GB RAM 필수 명시

### 6.2 일정 위험

**위험**: Phase 1이 8주 이상 소요
- 원인: HDF5 API 학습 곡선, 디버깅
- 대응:
  - Week 1-2 완료 시 진행 평가
  - 필요시 Temporal delta를 Phase 1.5로 연기
  - 최소 기능 버전 먼저 완성 (MVP)

---

## 7. 마일스톤 및 검증 기준

### Milestone 1: Week 2 완료 시점
**검증 기준**:
- [x] 10만 노드 모델을 HDF5로 변환 성공
- [x] 변위 양자화 정밀도 < 0.01mm
- [x] 파일 크기 50% 감소 확인

**Go/No-Go 결정**:
- GO: Week 3-4 진행 (Temporal delta)
- NO-GO: 아키텍처 재검토, 일정 조정

### Milestone 2: Week 4 완료 시점
**검증 기준**:
- [x] Temporal delta 85% 압축 달성
- [x] 메타데이터 자동 복원 성공
- [x] 100만 노드 모델 처리 가능

**Go/No-Go 결정**:
- GO: Week 5-6 진행 (CLI + 최적화)
- NO-GO: 성능 튜닝에 추가 2주 투입

### Milestone 3: Week 6 완료 시점 (Phase 1 완료)
**검증 기준**:
- [x] 10GB 파일을 120초 이내 변환
- [x] 압축률 70-85% 달성
- [x] 3개 이상 실제 케이스 검증 완료
- [x] CLI 문서화 완료

**결정**:
- Phase 2 시작 (Qt vs .NET 결정)

---

## 8. 다음 단계

### 즉시 시작할 작업 (이번 주)

1. **개발 환경 설정**:
   ```bash
   # HDF5 설치
   vcpkg install hdf5[cpp]:x64-windows

   # yaml-cpp 설치
   vcpkg install yaml-cpp:x64-windows
   ```

2. **프로젝트 구조 생성**:
   ```
   include/kood3plot/
     hdf5/
       HDF5Writer.hpp
       HDF5Reader.hpp
     quantization/
       QuantizationConfig.hpp
       Quantizers.hpp
     compression/
       TemporalDelta.hpp

   src/
     hdf5/
     quantization/
     compression/
   ```

3. **첫 번째 코드 작성**:
   - `HDF5Writer::create_file()`
   - `HDF5Writer::write_mesh()`
   - 기본 테스트 케이스

### Phase 1 완료 후 평가할 사항

1. **성능 평가**:
   - 실제 변환 시간
   - 압축률
   - 메모리 사용량

2. **UI 프레임워크 결정**:
   - Qt 프로토타입 2주
   - .NET 프로토타입 2주
   - 성능/개발속도 비교

3. **Phase 2 상세 설계**:
   - 선택된 프레임워크 기반
   - 렌더링 파이프라인 최종 결정
   - gRPC 서버 구조

---

## 9. 결론

**현재 상태**: Phase 1 완료, Phase 2 진행 중 (70%)

**완료된 핵심 성과**:
1. ✅ Phase 1 HDF5 양자화 시스템 완료
2. ✅ .NET 8 + Avalonia 프레임워크 선택 완료
3. ✅ GPU 렌더링 (Veldrid - Vulkan/D3D11) 구현 완료
4. ✅ 비동기 메시 로딩 및 기본 뷰어 기능 완료

**다음 액션**:
- 클립 플레인 구현
- 타임라인 애니메이션 재생
- 컬러맵 UI 개선

**성능 달성**:
- Phase 1: 10GB → 1.5GB, 120초 이내 ✅
- Phase 2: GPU 렌더링으로 100만+ 폴리곤 실시간 렌더링 ✅

**남은 작업**: UI 기능 보강, gRPC 네트워킹
