# KooD3plotReader 사용 방법

이 라이브러리는 두 가지 방법으로 사용할 수 있습니다:

1. **설치된 라이브러리 사용** (권장)
2. **소스 코드 직접 포함**

---

## 방법 1: 설치된 라이브러리 사용 (권장)

### 1단계: 라이브러리 빌드 및 설치

```bash
cd KooD3plotReader
mkdir build && cd build
cmake ..
make -j4
sudo make install
```

설치 위치:
- 라이브러리: `/usr/local/lib/libkood3plot.a`
- 헤더: `/usr/local/include/kood3plot/`

### 2단계: 프로젝트에서 사용

**your_project/CMakeLists.txt:**
```cmake
cmake_minimum_required(VERSION 3.10)
project(MyD3plotApp)

set(CMAKE_CXX_STANDARD 17)

# kood3plot 라이브러리 찾기
find_package(KooD3plot REQUIRED)

add_executable(my_app main.cpp)
target_link_libraries(my_app PRIVATE KooD3plot::kood3plot)
```

**your_project/main.cpp:**
```cpp
#include <kood3plot/D3plotReader.hpp>
#include <iostream>

int main() {
    kood3plot::D3plotReader reader("path/to/d3plot");

    if (reader.open() != kood3plot::ErrorCode::SUCCESS) {
        std::cerr << "Failed to open file\n";
        return 1;
    }

    // 메쉬 읽기
    auto mesh = reader.read_mesh();
    std::cout << "Nodes: " << mesh.nodes.size() << "\n";
    std::cout << "Elements: " << mesh.solids.size() << "\n";

    // State 데이터 읽기
    auto states = reader.read_all_states();
    std::cout << "Time states: " << states.size() << "\n";

    // 노드 변위
    if (!states.empty() && !states[0].node_displacements.empty()) {
        std::cout << "First node displacement: "
                  << states[0].node_displacements[0] << "\n";
    }

    reader.close();
    return 0;
}
```

### 3단계: 빌드

```bash
cd your_project
mkdir build && cd build
cmake ..
make
./my_app
```

---

## 방법 2: 소스 코드 직접 포함

### 1단계: 필요한 파일 복사

KooD3plotReader 프로젝트에서 다음을 복사:

```
your_project/
  ├── main.cpp
  └── kood3plot/
      ├── include/      # 전체 include 폴더 복사
      └── src/          # 전체 src 폴더 복사
```

### 2단계: CMakeLists.txt 작성

**your_project/CMakeLists.txt:**
```cmake
cmake_minimum_required(VERSION 3.10)
project(MyD3plotApp)

set(CMAKE_CXX_STANDARD 17)

# kood3plot 소스 파일들
file(GLOB_RECURSE KOOD3PLOT_SOURCES
    kood3plot/src/*.cpp
)

# 실행 파일 생성
add_executable(my_app main.cpp ${KOOD3PLOT_SOURCES})

# Include 경로 설정
target_include_directories(my_app PRIVATE kood3plot/include)
```

### 3단계: 빌드

```bash
cd your_project
mkdir build && cd build
cmake ..
make
./my_app
```

---

## 방법 2-B: 직접 컴파일 (CMake 없이)

```bash
g++ -std=c++17 \
    -I kood3plot/include \
    main.cpp \
    kood3plot/src/D3plotReader.cpp \
    kood3plot/src/core/BinaryReader.cpp \
    kood3plot/src/core/FileFamily.cpp \
    kood3plot/src/data/ControlData.cpp \
    kood3plot/src/data/Mesh.cpp \
    kood3plot/src/data/StateData.cpp \
    kood3plot/src/parsers/ControlDataParser.cpp \
    kood3plot/src/parsers/GeometryParser.cpp \
    kood3plot/src/parsers/StateDataParser.cpp \
    kood3plot/src/parsers/NARBSParser.cpp \
    kood3plot/src/parsers/TitlesParser.cpp \
    -o my_app
```

---

## 간단한 사용 예제

### 예제 1: 기본 정보 읽기

```cpp
#include <kood3plot/D3plotReader.hpp>
#include <iostream>

int main() {
    kood3plot::D3plotReader reader("d3plot");
    reader.open();

    auto cd = reader.get_control_data();
    std::cout << "Nodes: " << cd.NUMNP << "\n";
    std::cout << "Solids: " << cd.NEL8 << "\n";

    reader.close();
    return 0;
}
```

### 예제 2: 변위 데이터 읽기

```cpp
#include <kood3plot/D3plotReader.hpp>
#include <iostream>

int main() {
    kood3plot::D3plotReader reader("d3plot");
    reader.open();

    auto cd = reader.get_control_data();
    auto states = reader.read_all_states();

    // 마지막 state의 변위
    if (!states.empty()) {
        const auto& last_state = states.back();
        std::cout << "Time: " << last_state.time << "\n";

        // 첫 10개 노드의 변위
        for (int i = 0; i < 10; ++i) {
            int idx = i * cd.NDIM;
            double ux = last_state.node_displacements[idx + 0];
            double uy = last_state.node_displacements[idx + 1];
            double uz = last_state.node_displacements[idx + 2];

            std::cout << "Node " << (i+1) << ": "
                      << "Ux=" << ux << ", "
                      << "Uy=" << uy << ", "
                      << "Uz=" << uz << "\n";
        }
    }

    reader.close();
    return 0;
}
```

### 예제 3: 응력 데이터 읽기

```cpp
#include <kood3plot/D3plotReader.hpp>
#include <iostream>
#include <cmath>

int main() {
    kood3plot::D3plotReader reader("d3plot");
    reader.open();

    auto cd = reader.get_control_data();
    auto states = reader.read_all_states();

    if (!states.empty()) {
        const auto& state = states.back();

        // 첫 번째 요소의 응력
        int offset = 0;  // Element 0
        double sx = state.solid_data[offset + 0];
        double sy = state.solid_data[offset + 1];
        double sz = state.solid_data[offset + 2];
        double txy = state.solid_data[offset + 3];
        double tyz = state.solid_data[offset + 4];
        double tzx = state.solid_data[offset + 5];

        // Von Mises 응력
        double s_vm = std::sqrt(0.5 * (
            (sx-sy)*(sx-sy) + (sy-sz)*(sy-sz) + (sz-sx)*(sz-sx)
        ) + 3.0 * (txy*txy + tyz*tyz + tzx*tzx));

        std::cout << "Element 1 stress:\n";
        std::cout << "  σx = " << sx << "\n";
        std::cout << "  σy = " << sy << "\n";
        std::cout << "  σz = " << sz << "\n";
        std::cout << "  Von Mises = " << s_vm << "\n";
    }

    reader.close();
    return 0;
}
```

### 예제 4: 실제 노드/요소 ID 사용 (NARBS)

```cpp
#include <kood3plot/D3plotReader.hpp>
#include <iostream>

int main() {
    kood3plot::D3plotReader reader("d3plot");
    reader.open();

    auto mesh = reader.read_mesh();

    // 실제 ID가 파싱되어 있음
    if (!mesh.real_node_ids.empty()) {
        std::cout << "Real node IDs:\n";
        for (int i = 0; i < 10; ++i) {
            std::cout << "  Internal index " << i
                      << " → Real ID " << mesh.real_node_ids[i] << "\n";
        }
    }

    if (!mesh.real_solid_ids.empty()) {
        std::cout << "\nReal element IDs:\n";
        for (int i = 0; i < 10; ++i) {
            std::cout << "  Internal index " << i
                      << " → Real ID " << mesh.real_solid_ids[i] << "\n";
        }
    }

    reader.close();
    return 0;
}
```

---

## 주의사항

1. **C++17 필수**: `-std=c++17` 플래그 필요
2. **파일 경로**: d3plot 파일은 절대 경로나 실행 파일 기준 상대 경로
3. **다중 파일**: d3plot, d3plot01, d3plot02... 파일들이 같은 폴더에 있어야 함
4. **메모리**: 큰 파일의 경우 수 GB 메모리 필요

---

## 문제 해결

### 링크 에러
```
undefined reference to `kood3plot::D3plotReader::open()'
```
→ 라이브러리가 제대로 링크되지 않음. `target_link_libraries` 확인

### 컴파일 에러
```
fatal error: kood3plot/D3plotReader.hpp: No such file or directory
```
→ Include 경로 설정 확인. `target_include_directories` 또는 `-I` 플래그

### 실행 에러
```
파일 열기 실패!
```
→ d3plot 파일 경로 확인. 파일이 존재하고 읽기 권한이 있는지 확인

---

## 더 많은 예제

프로젝트의 `examples/` 폴더에 10개의 예제 프로그램이 있습니다:

1. `simple_read.cpp` - 기본 사용법
2. `check_results.cpp` - 변위/응력 검증
3. `extract_stress.cpp` - 응력 추출
4. `extract_displacement.cpp` - 변위 추출
5. `extract_all_data.cpp` - 전체 데이터 CSV 저장
6. `show_stress_strain.cpp` - 응력/변형률 상세 출력
7. `show_narbs.cpp` - NARBS 데이터 확인

빌드 후 실행:
```bash
./build/examples/simple_read results/d3plot
```
