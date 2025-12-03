# KooD3plotReader

고성능 C++ LS-DYNA d3plot 파일 리더 라이브러리

[![C++17](https://img.shields.io/badge/C%2B%2B-17-blue.svg)](https://isocpp.org/)
[![CMake](https://img.shields.io/badge/CMake-3.15%2B-green.svg)](https://cmake.org/)
[![OpenMP](https://img.shields.io/badge/OpenMP-4.5-orange.svg)](https://www.openmp.org/)

## 주요 기능

- ✅ **자동 포맷 감지**: Single/Double precision, Little/Big endian 자동 인식
- ✅ **Multi-file 지원**: d3plot family 파일 자동 탐지 및 읽기 (d3plot01-99)
- ✅ **완전한 데이터 파싱**: Control data, Geometry, State data 전체 지원
- ✅ **고성능**: OpenMP 병렬 처리 지원
- ✅ **간단한 API**: 한 줄로 d3plot 파일 읽기
- ✅ **Modern C++17**: 최신 C++ 표준 사용
- ✅ **정적 라이브러리**: 다른 프로젝트에 쉽게 통합
- ✅ **V3 Query System**: Fluent API로 강력한 데이터 쿼리
- ✅ **CLI Tool**: 커맨드라인에서 바로 사용 가능
- ✅ **다중 출력 형식**: CSV, JSON, HDF5 지원

## 빠른 시작

### 설치 및 빌드

```bash
# 저장소 클론
git clone https://github.com/yourusername/KooD3plotReader.git
cd KooD3plotReader

# 빌드
mkdir build && cd build
cmake ..
make -j$(nproc)
```

### 간단한 사용 예제

```cpp
#include "kood3plot/D3plotReader.hpp"
#include <iostream>

int main() {
    // D3plot 파일 열기
    kood3plot::D3plotReader reader("path/to/d3plot");
    reader.open();

    // 파일 정보 확인
    auto format = reader.get_file_format();
    auto control = reader.get_control_data();

    std::cout << "Nodes: " << control.NUMNP << std::endl;
    std::cout << "Elements: " << control.NEL8 << std::endl;

    // 메쉬 읽기
    auto mesh = reader.read_mesh();
    std::cout << "Loaded " << mesh.get_num_nodes() << " nodes" << std::endl;

    // 모든 time states 읽기 (자동으로 family 파일들 읽음)
    auto states = reader.read_all_states();
    std::cout << "Loaded " << states.size() << " time states" << std::endl;

    // 첫 번째 state의 데이터 접근
    if (!states.empty()) {
        const auto& state0 = states[0];
        std::cout << "Time: " << state0.time << std::endl;
        std::cout << "Global vars: " << state0.global_vars.size() << std::endl;
        std::cout << "Solid data: " << state0.solid_data.size() << std::endl;
    }

    reader.close();
    return 0;
}
```

### CMake 통합

```cmake
# CMakeLists.txt
add_subdirectory(KooD3plotReader)

add_executable(your_program main.cpp)
target_link_libraries(your_program PRIVATE kood3plot)
```

## V3 Query System

V3 Query System은 Fluent API 패턴으로 직관적인 데이터 쿼리를 제공합니다.

### 기본 쿼리

```cpp
#include "kood3plot/D3plotReader.hpp"
#include "kood3plot/query/D3plotQuery.h"

using namespace kood3plot;
using namespace kood3plot::query;

// D3plot 열기
D3plotReader reader("path/to/d3plot");
reader.open();

// Fluent API로 쿼리 작성
D3plotQuery query(reader);
auto result = query
    .selectParts(PartSelector().byId(1, 2, 3))      // Part 선택
    .selectQuantities(QuantitySelector().vonMises()) // Von Mises 응력
    .selectTime(TimeSelector().lastState())         // 마지막 state
    .execute();

// 결과 출력
std::cout << "Data points: " << result.size() << std::endl;
```

### 다양한 Part 선택

```cpp
// ID로 선택
PartSelector().byId(1, 2, 3)

// 이름으로 선택
PartSelector().byName("Hood", "Bumper")

// 범위로 선택
PartSelector().byIdRange(1, 100)

// 모든 Part
PartSelector().all()
```

### 수량(Quantity) 선택

```cpp
// 응력
QuantitySelector()
    .vonMises()           // Von Mises equivalent stress
    .allStress()          // 전체 응력 텐서 (xx, yy, zz, xy, yz, xz)

// 변형률
QuantitySelector()
    .effectiveStrain()    // Effective plastic strain
    .allStrain()          // 전체 변형률 텐서

// 변위/속도/가속도
QuantitySelector()
    .displacement()       // 변위 (x, y, z, magnitude)
    .velocity()           // 속도
    .acceleration()       // 가속도
```

### 시간 선택

```cpp
// 특정 state
TimeSelector().addStep(0).addStep(10).addStep(-1)

// 범위
TimeSelector().addStateRange(0, 100)
TimeSelector().addStateRange(0, -1, 5)  // step=5

// 시간 범위
TimeSelector().addTimeRange(0.0, 0.01)

// 모든 state
TimeSelector().all()

// 첫/마지막
TimeSelector().firstState()
TimeSelector().lastState()
```

### 값 필터링

```cpp
// 값 범위
ValueFilter()
    .greaterThan(100.0)     // > 100
    .lessThan(1000.0)       // < 1000

// 범위 지정
ValueFilter().range(100.0, 1000.0)

// 절대값
ValueFilter().absoluteGreaterThan(50.0)
```

### 공간 선택 (Spatial)

```cpp
// Bounding Box
SpatialSelector().box(Point3D{0, 0, 0}, Point3D{100, 100, 100})

// 구 영역
SpatialSelector().sphere(Point3D{50, 50, 50}, 25.0)

// 원통 영역
SpatialSelector().cylinder(Point3D{0, 0, 0}, Point3D{0, 0, 100}, 10.0)

// 단면
SpatialSelector().sectionPlane(Point3D{0, 0, 50}, Point3D{0, 0, 1})
```

### 결과 출력

```cpp
// CSV 출력
#include "writers/CSVWriter.h"
writers::CSVWriter csv("output.csv");
csv.write(result);

// JSON 출력
#include "writers/JSONWriter.h"
writers::JSONWriter json("output.json");
json.write(result);

// HDF5 출력
#include "writers/HDF5Writer.h"
writers::HDF5Writer hdf5;
hdf5.write(result, "output.h5");
```

### 통계 정보

```cpp
// 자동 통계 계산
auto stats = result.getStatistics("von_mises");
std::cout << "Min: " << stats.min_value << std::endl;
std::cout << "Max: " << stats.max_value << std::endl;
std::cout << "Mean: " << stats.mean_value << std::endl;
std::cout << "Std Dev: " << stats.std_dev << std::endl;
```

## CLI Tool (kood3plot_cli)

커맨드라인에서 직접 d3plot 파일을 분석할 수 있습니다.

### 기본 사용법

```bash
# 파일 정보 확인
kood3plot_cli --info d3plot

# Part 목록
kood3plot_cli --list-parts d3plot

# 템플릿 목록
kood3plot_cli --list-templates
```

### 쿼리 실행

```bash
# Von Mises 응력 추출
kood3plot_cli -q von_mises d3plot -o stress.csv

# 특정 Part의 변위
kood3plot_cli -p Hood -q displacement d3plot -o disp.csv

# 값 필터링
kood3plot_cli -q von_mises --min 100 --max 500 d3plot

# State 범위 지정
kood3plot_cli -q von_mises --first 0 --last 10 --step 2 d3plot
```

### 출력 형식

```bash
# CSV (기본)
kood3plot_cli -q von_mises d3plot --format csv -o output.csv

# JSON
kood3plot_cli -q von_mises d3plot --format json -o output.json

# HDF5
kood3plot_cli -q von_mises d3plot --format hdf5 -o output.h5
```

### 설정 파일 사용

```bash
# YAML/JSON 설정 파일로 쿼리 실행
kood3plot_cli --config analysis.yaml
```

**analysis.yaml 예제:**
```yaml
d3plot: path/to/d3plot
output: results.csv
format: csv

parts:
  - Hood
  - Bumper

quantities:
  - von_mises
  - displacement

time:
  first: 0
  last: -1
  step: 1

filter:
  min: 0
  max: 1000
```

### 템플릿 사용

```bash
# 사전 정의된 쿼리 템플릿 사용
kood3plot_cli --template max_stress_history d3plot
```

**사용 가능한 템플릿:**
- `max_stress_history` - 시간에 따른 최대 응력
- `energy_balance` - 에너지 균형 분석
- `displacement_envelope` - 최대 변위 분포
- `strain_hotspots` - 고변형 영역 탐지
- `contact_forces` - 접촉력 분석

## 상세 사용법

### 1. 파일 열기 및 포맷 확인

```cpp
kood3plot::D3plotReader reader("path/to/d3plot");

auto err = reader.open();
if (err != kood3plot::ErrorCode::SUCCESS) {
    std::cerr << "Failed: " << kood3plot::error_to_string(err) << std::endl;
    return -1;
}

auto format = reader.get_file_format();
std::cout << "Precision: " << (format.precision == kood3plot::Precision::SINGLE ? "Single" : "Double") << std::endl;
std::cout << "Endian: " << (format.endian == kood3plot::Endian::LITTLE ? "Little" : "Big") << std::endl;
std::cout << "Version: " << format.version << std::endl;
```

### 2. Control Data 접근

```cpp
auto cd = reader.get_control_data();

// 모델 정보
std::cout << "Nodes: " << cd.NUMNP << std::endl;
std::cout << "Solids: " << cd.NEL8 << std::endl;
std::cout << "Shells: " << cd.NEL4 << std::endl;
std::cout << "Beams: " << cd.NEL2 << std::endl;
std::cout << "Thick shells: " << cd.NELT << std::endl;

// State 데이터 크기
std::cout << "Global vars per state: " << cd.NGLBV << std::endl;
std::cout << "Nodal data words: " << cd.NND << std::endl;
std::cout << "Element data words: " << cd.ENN << std::endl;
```

### 3. Mesh Geometry 읽기

```cpp
auto mesh = reader.read_mesh();

// 노드 데이터
for (const auto& node : mesh.nodes) {
    std::cout << "Node " << node.id << ": ("
              << node.x << ", " << node.y << ", " << node.z << ")" << std::endl;
}

// 요소 연결성
for (const auto& elem : mesh.solids) {
    std::cout << "Solid " << elem.id << " nodes: ";
    for (auto node_id : elem.node_ids) {
        std::cout << node_id << " ";
    }
    std::cout << std::endl;
}

// 재질 정보
for (size_t i = 0; i < mesh.num_solids; ++i) {
    std::cout << "Solid " << i << " material: " << mesh.solid_materials[i] << std::endl;
}
```

### 4. State Data 읽기

```cpp
// 모든 states 읽기 (자동으로 d3plot01, d3plot02, ... 처리)
auto states = reader.read_all_states();

for (size_t i = 0; i < states.size(); ++i) {
    const auto& state = states[i];

    // 시간 정보
    std::cout << "State " << i << " time: " << state.time << std::endl;

    // Global variables (KE, IE, TE 등)
    if (!state.global_vars.empty()) {
        std::cout << "  Kinetic Energy: " << state.global_vars[0] << std::endl;
        std::cout << "  Internal Energy: " << state.global_vars[1] << std::endl;
    }

    // 노드 변위 (IU=1인 경우)
    if (!state.node_displacements.empty()) {
        // NDIM=4이므로 각 노드당 4개 값
        int numnp = state.node_displacements.size() / 4;
        for (int n = 0; n < numnp; ++n) {
            double ux = state.node_displacements[n * 4 + 0];
            double uy = state.node_displacements[n * 4 + 1];
            double uz = state.node_displacements[n * 4 + 2];
            // w (4th component)
        }
    }

    // 요소 응력/변형률 데이터
    if (!state.solid_data.empty()) {
        // NV3D values per solid element
        int values_per_elem = cd.NV3D;
        // 각 요소 데이터 추출
    }
}
```

### 5. 특정 State만 읽기

```cpp
// 특정 인덱스의 state만 읽기
auto state = reader.read_state(10);  // 11번째 state

std::cout << "Time: " << state.time << std::endl;
```

## 지원 데이터

### Control Data
- 모델 크기: NUMNP, NEL8, NEL4, NEL2, NELT
- 변수 카운트: NGLBV, NND, ENN, NV3D, NV2D, NV1D, NV3DT
- 플래그: IT, IU, IV, IA, MDLOPT, ISTRN
- IOSHL/IOSOL 플래그 (999/1000 → 0/1 변환)

### Geometry Data
- **노드**: ID, X, Y, Z 좌표
- **Solid 요소** (8-node): 연결성, 재질 ID
- **Shell 요소** (4-node): 연결성, 재질 ID
- **Beam 요소** (2-node): 연결성, 재질 ID
- **Thick shell** (8-node): 연결성, 재질 ID

### State Data (시간 단계별)
- **Time**: 시뮬레이션 시간
- **Global variables**: KE, IE, TE, velocities 등
- **Nodal data**:
  - Temperatures (IT > 0)
  - Displacements (IU > 0)
  - Velocities (IV > 0)
  - Accelerations (IA > 0)
- **Element data**:
  - Solid stresses/strains
  - Shell stresses/strains
  - Beam forces/moments

## 기술 세부사항

### 아키텍처

```
kood3plot/
├── core/
│   ├── BinaryReader    - 저수준 바이너리 I/O
│   ├── FileFamily      - Multi-file 관리
│   └── Endian          - 엔디안 변환
├── parsers/
│   ├── ControlDataParser  - 제어 데이터
│   ├── GeometryParser     - 지오메트리
│   └── StateDataParser    - State 데이터
├── data/
│   ├── ControlData     - 제어 데이터 구조
│   ├── Mesh            - 메쉬 구조
│   └── StateData       - State 구조
├── query/              [V3 Query System]
│   ├── D3plotQuery     - Fluent API 진입점
│   ├── PartSelector    - Part 선택
│   ├── QuantitySelector - 수량 선택
│   ├── TimeSelector    - 시간 선택
│   ├── ValueFilter     - 값 필터링
│   ├── SpatialSelector - 공간 선택
│   ├── QueryResult     - 결과 및 통계
│   ├── ConfigParser    - YAML/JSON 설정
│   ├── TemplateManager - 쿼리 템플릿
│   └── writers/
│       ├── CSVWriter   - CSV 출력
│       ├── JSONWriter  - JSON 출력
│       └── HDF5Writer  - HDF5 출력
├── cli/
│   └── kood3plot_cli   - CLI 도구
└── D3plotReader        - Public API
```

### 성능 특징

- **자동 포맷 감지**: 4가지 조합 (precision × endian) 자동 시도
- **Lazy loading**: 필요한 데이터만 읽기
- **메모리 효율**: 벡터 reserve로 재할당 최소화
- **OpenMP 준비**: 병렬 처리 가능 구조

### 지원 플랫폼

- **OS**: Linux, macOS, Windows
- **컴파일러**: GCC 7+, Clang 6+, MSVC 2017+
- **CMake**: 3.15 이상
- **C++**: C++17 표준

## 예제 프로그램

프로젝트에 포함된 예제들:

### simple_read.cpp
기본적인 d3plot 파일 읽기 및 정보 출력
```bash
./build/examples/simple_read path/to/d3plot
```

### test_binary_reader.cpp
BinaryReader 기능 테스트
```bash
./build/examples/test_binary_reader path/to/d3plot
```

### test_control_data.cpp
Control data 파싱 테스트
```bash
./build/examples/test_control_data path/to/d3plot
```

### test_geometry.cpp
Geometry 파싱 테스트
```bash
./build/examples/test_geometry path/to/d3plot
```

### test_state_data.cpp
State data 파싱 테스트
```bash
./build/examples/test_state_data path/to/d3plot
```

## 테스트 결과

실제 d3plot 파일 (crash simulation) 테스트:
- ✅ 파일 크기: 2.2MB (base) + 4×69MB (family) = 278MB
- ✅ 노드: 29,624개
- ✅ Solid 요소: 44,657개
- ✅ Time states: 47개
- ✅ 데이터 포인트: 47 states × 936,197 words ≈ 44M values
- ✅ 처리 시간: ~3초 (single thread)

## 참고 문서

- [LS-DYNA Database Format](ls-dyna_database.txt) - 공식 포맷 문서
- [구현 계획](D3PLOT_IMPLEMENTATION_PLAN.md) - 전체 구현 계획
- [진행 상황](PROGRESS.md) - 상세 진행 기록

## 라이선스

이 프로젝트는 교육 및 연구 목적으로 개발되었습니다.

## 기여

이슈 및 Pull Request 환영합니다!

## 버전

- **v3.0.0** (2025-11-22) - V3 Query System
  - Fluent API 기반 쿼리 시스템
  - CLI 도구 (kood3plot_cli)
  - CSV, JSON, HDF5 출력 지원
  - 공간 선택 (BoundingBox, Sphere, Cylinder, SectionPlane)
  - YAML/JSON 설정 파일 지원
  - 쿼리 템플릿 시스템
  - 값 필터링 및 통계 자동 계산

- **v1.0.0** (2025-11-20) - 초기 릴리스
  - 완전한 d3plot 파일 읽기 지원
  - Multi-file family 지원
  - 자동 포맷 감지
  - Simple API

## 작성자

KooD3plotReader Development Team

---

**Note**: 이 라이브러리는 LS-DYNA d3plot 파일 형식을 읽는 기능만 제공합니다.
LS-DYNA는 Livermore Software Technology Corporation (LSTC)의 제품입니다.
