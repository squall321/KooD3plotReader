#!/bin/bash

# KooD3plotReader 빌드 스크립트
# 두 가지 사용 방법을 모두 지원하는 설치 패키지 생성

set -e  # 에러 발생시 중단

echo "========================================="
echo " KooD3plotReader 빌드 및 패키징"
echo "========================================="
echo ""

# 색상 정의
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 프로젝트 루트 디렉토리
PROJECT_ROOT="/home/koopark/claude/KooD3plotReader/KooD3plotReader"
BUILD_DIR="${PROJECT_ROOT}/build"
INSTALL_DIR="${PROJECT_ROOT}/installed"

echo -e "${BLUE}[1/6]${NC} 이전 빌드 정리..."
rm -rf "${BUILD_DIR}"
rm -rf "${INSTALL_DIR}"

echo -e "${BLUE}[2/6]${NC} 빌드 디렉토리 생성..."
mkdir -p "${BUILD_DIR}"
cd "${BUILD_DIR}"

echo -e "${BLUE}[3/6]${NC} CMake 설정 (Static 라이브러리)..."
cmake -DCMAKE_BUILD_TYPE=Release \
      -DBUILD_SHARED_LIBS=OFF \
      -DCMAKE_INSTALL_PREFIX="${INSTALL_DIR}/library" \
      ..

echo -e "${BLUE}[4/6]${NC} Static 라이브러리 빌드..."
make -j$(nproc)

echo -e "${BLUE}[5/6]${NC} Static 라이브러리 설치..."
make install

# Shared 라이브러리도 빌드
echo -e "${BLUE}[5.5/6]${NC} CMake 재설정 (Shared 라이브러리)..."
cmake -DCMAKE_BUILD_TYPE=Release \
      -DBUILD_SHARED_LIBS=ON \
      -DCMAKE_INSTALL_PREFIX="${INSTALL_DIR}/library" \
      ..

echo "Shared 라이브러리 빌드..."
make -j$(nproc)
make install

# CLI 도구 복사
echo "CLI 도구 복사 중..."
mkdir -p "${INSTALL_DIR}/bin"
if [ -f "${BUILD_DIR}/kood3plot_cli" ]; then
    cp "${BUILD_DIR}/kood3plot_cli" "${INSTALL_DIR}/bin/"
    chmod +x "${INSTALL_DIR}/bin/kood3plot_cli"
    echo "  ✓ kood3plot_cli 복사 완료"
else
    echo "  ⚠ kood3plot_cli 빌드되지 않음"
fi

echo -e "${BLUE}[6/6]${NC} 소스 코드 패키지 생성..."
cd "${PROJECT_ROOT}"

# 소스 코드 사용 방식을 위한 디렉토리 구조
mkdir -p "${INSTALL_DIR}/source/kood3plot"

# include 폴더 복사
cp -r include "${INSTALL_DIR}/source/kood3plot/"

# src 폴더 복사
cp -r src "${INSTALL_DIR}/source/kood3plot/"

# examples 폴더 복사
echo "예제 파일 복사 중..."
cp -r examples "${INSTALL_DIR}/source/"
cp -r examples "${INSTALL_DIR}/library/"

# 문서 파일들 복사
echo "문서 파일 복사 중..."

# docs 폴더 먼저 생성
mkdir -p "${INSTALL_DIR}/docs"

# 루트에 복사
[ -f README.md ] && cp README.md "${INSTALL_DIR}/"
[ -f USAGE.md ] && cp USAGE.md "${INSTALL_DIR}/"
[ -f LICENSE ] && cp LICENSE "${INSTALL_DIR}/"
[ -f PROGRESS.md ] && cp PROGRESS.md "${INSTALL_DIR}/"

# docs 폴더에 복사
[ -f USAGE.md ] && cp USAGE.md "${INSTALL_DIR}/docs/"
[ -f README.md ] && cp README.md "${INSTALL_DIR}/docs/"
[ -f KOOD3PLOT_CLI_사용법.md ] && cp KOOD3PLOT_CLI_사용법.md "${INSTALL_DIR}/docs/"
[ -f D3PLOT_IMPLEMENTATION_PLAN.md ] && cp D3PLOT_IMPLEMENTATION_PLAN.md "${INSTALL_DIR}/docs/" || true

# CMakeLists.txt 템플릿 생성
cat > "${INSTALL_DIR}/source/CMakeLists.txt.example" << 'EOF'
# KooD3plotReader를 소스 코드로 포함하는 예제
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
EOF

# 사용 예제 생성
cat > "${INSTALL_DIR}/source/main.cpp.example" << 'EOF'
#include <kood3plot/D3plotReader.hpp>
#include <iostream>

int main(int argc, char* argv[]) {
    if (argc < 2) {
        std::cerr << "Usage: " << argv[0] << " <d3plot_file>\n";
        return 1;
    }

    kood3plot::D3plotReader reader(argv[1]);

    if (reader.open() != kood3plot::ErrorCode::SUCCESS) {
        std::cerr << "Failed to open file: " << argv[1] << "\n";
        return 1;
    }

    std::cout << "File opened successfully!\n";

    // Control data
    auto cd = reader.get_control_data();
    std::cout << "\n[Model Info]\n";
    std::cout << "  Nodes: " << cd.NUMNP << "\n";
    std::cout << "  Solid elements: " << std::abs(cd.NEL8) << "\n";

    // Mesh
    auto mesh = reader.read_mesh();
    std::cout << "\n[Mesh]\n";
    std::cout << "  Actual nodes loaded: " << mesh.nodes.size() << "\n";
    std::cout << "  Actual elements loaded: " << mesh.solids.size() << "\n";

    // States
    auto states = reader.read_all_states();
    std::cout << "\n[Time States]\n";
    std::cout << "  Total states: " << states.size() << "\n";

    if (!states.empty()) {
        std::cout << "  First time: " << states.front().time << "\n";
        std::cout << "  Last time: " << states.back().time << "\n";
    }

    reader.close();
    std::cout << "\n✓ Success!\n";

    return 0;
}
EOF

# 라이브러리 사용 방식을 위한 CMakeLists.txt 예제
cat > "${INSTALL_DIR}/library/CMakeLists.txt.example" << EOF
# KooD3plotReader를 설치된 라이브러리로 사용하는 예제
cmake_minimum_required(VERSION 3.10)
project(MyD3plotApp)

set(CMAKE_CXX_STANDARD 17)

# kood3plot 설치 경로 지정
set(KooD3plot_DIR "\${CMAKE_CURRENT_SOURCE_DIR}")

# Static 라이브러리 사용
add_executable(my_app_static main.cpp)
target_include_directories(my_app_static PRIVATE include)
target_link_libraries(my_app_static PRIVATE
    \${CMAKE_CURRENT_SOURCE_DIR}/lib/libkood3plot.a
)

# Shared 라이브러리 사용
add_executable(my_app_shared main.cpp)
target_include_directories(my_app_shared PRIVATE include)
target_link_libraries(my_app_shared PRIVATE
    \${CMAKE_CURRENT_SOURCE_DIR}/lib/libkood3plot.so
)
EOF

# 라이브러리용 예제도 복사
cp "${INSTALL_DIR}/source/main.cpp.example" "${INSTALL_DIR}/library/"

# README 파일 생성
cat > "${INSTALL_DIR}/README.md" << 'EOF'
# KooD3plotReader 설치 패키지

이 패키지는 두 가지 방법으로 사용할 수 있습니다:

## 방법 1: 컴파일된 라이브러리 사용 (library/)

`library/` 폴더에는 빌드된 라이브러리가 포함되어 있습니다:

```
library/
  ├── lib/
  │   ├── libkood3plot.a      (Static library)
  │   └── libkood3plot.so     (Shared library)
  ├── include/
  │   └── kood3plot/          (Header files)
  ├── examples/               (10개 예제 프로그램)
  ├── CMakeLists.txt.example
  └── main.cpp.example
```

### 사용 방법:

```bash
cd library/
cp main.cpp.example main.cpp
cp CMakeLists.txt.example CMakeLists.txt
mkdir build && cd build
cmake ..
make
./my_app_static ../path/to/d3plot
# 또는
./my_app_shared ../path/to/d3plot
```

## 방법 2: 소스 코드 직접 포함 (source/)

`source/` 폴더에는 전체 소스 코드가 포함되어 있습니다:

```
source/
  ├── kood3plot/
  │   ├── include/           (Header files)
  │   └── src/               (Source files)
  ├── examples/              (10개 예제 프로그램)
  ├── CMakeLists.txt.example
  └── main.cpp.example
```

### 사용 방법:

```bash
cd source/
cp main.cpp.example main.cpp
cp CMakeLists.txt.example CMakeLists.txt
mkdir build && cd build
cmake ..
make
./my_app ../path/to/d3plot
```

또는 프로젝트에 `kood3plot/` 폴더를 통째로 복사하여 사용할 수 있습니다.

## 직접 컴파일 (CMake 없이)

```bash
g++ -std=c++17 -O3 \
    -I library/include \
    main.cpp \
    -L library/lib \
    -lkood3plot \
    -o my_app
```

또는

```bash
g++ -std=c++17 -O3 \
    -I source/kood3plot/include \
    main.cpp \
    source/kood3plot/src/**/*.cpp \
    -o my_app
```

## 예제 프로그램 (examples/)

두 패키지 모두 10개의 예제 프로그램이 포함되어 있습니다:

1. **test_binary_reader.cpp** - BinaryReader 테스트
2. **test_control_data.cpp** - Control data 파싱 테스트
3. **test_geometry.cpp** - Geometry 파싱 테스트
4. **test_state_data.cpp** - State data 파싱 테스트
5. **simple_read.cpp** - 기본 사용 예제
6. **check_results.cpp** - 변위/응력 검증
7. **extract_stress.cpp** - 응력 데이터 추출 (5가지 예제)
8. **extract_displacement.cpp** - 변위 데이터 추출 (6가지 예제)
9. **extract_all_data.cpp** - 모든 데이터 CSV 저장
10. **show_stress_strain.cpp** - 응력/변형률 상세 출력
11. **show_narbs.cpp** - NARBS(실제 ID) 데이터 확인

### 예제 빌드 및 실행:

```bash
# library/ 패키지 사용시
cd library/examples
mkdir build && cd build
cmake ..
make
./simple_read /path/to/d3plot

# source/ 패키지 사용시
cd source/examples
mkdir build && cd build
cmake ..
make
./simple_read /path/to/d3plot
```

## 문서 (docs/)

- **README.md** - 이 파일
- **USAGE.md** - 상세 사용 가이드 및 API 문서
- **examples/** - 실행 가능한 예제 코드

더 자세한 사용법과 API 설명은 `docs/USAGE.md`를 참조하세요.

## 파일 구조

```
installed/
  ├── README.md              (이 파일)
  ├── USAGE.md               (사용 가이드)
  ├── docs/                  (문서)
  ├── library/               (컴파일된 라이브러리)
  │   ├── lib/
  │   │   ├── libkood3plot.a
  │   │   └── libkood3plot.so
  │   ├── include/kood3plot/
  │   ├── examples/          (10개 예제)
  │   ├── CMakeLists.txt.example
  │   └── main.cpp.example
  └── source/                (소스 코드)
      ├── kood3plot/
      │   ├── include/
      │   └── src/
      ├── examples/          (10개 예제)
      ├── CMakeLists.txt.example
      └── main.cpp.example
```
EOF

# ============================================================
# Step 9: LSPrePost 렌더링 엔진 복사 (V4 Render 시스템용)
# ============================================================

echo ""
echo -e "${YELLOW}[7/7] LSPrePost 렌더링 엔진 복사 중...${NC}"

# LSPrePost 소스 경로
LSPREPOST_SOURCE="references/external/lsprepost4.12_common"

if [ -d "${LSPREPOST_SOURCE}" ]; then
    # 설치 디렉토리 생성
    mkdir -p "${INSTALL_DIR}/lsprepost"

    # 전체 LSPrePost 디렉토리 복사
    echo "  - LSPrePost 파일 복사 중..."
    cp -r "${LSPREPOST_SOURCE}"/* "${INSTALL_DIR}/lsprepost/"

    # 실행 권한 설정
    echo "  - 실행 권한 설정 중..."
    chmod +x "${INSTALL_DIR}/lsprepost/lsprepost" 2>/dev/null || true
    chmod +x "${INSTALL_DIR}/lsprepost/lspp412_mesa" 2>/dev/null || true
    chmod +x "${INSTALL_DIR}/lsprepost/lspp412" 2>/dev/null || true
    chmod +x "${INSTALL_DIR}/lsprepost/lspp412_centos7" 2>/dev/null || true
    chmod +x "${INSTALL_DIR}/lsprepost/lspp412_centos7_mesa" 2>/dev/null || true

    # 라이브러리 디렉토리 권한 설정
    chmod -R 755 "${INSTALL_DIR}/lsprepost/lib" 2>/dev/null || true

    echo -e "${GREEN}  ✓ LSPrePost 복사 완료${NC}"
    echo "    경로: ${INSTALL_DIR}/lsprepost/"
    echo "    메인 실행 파일: lspp412_mesa (추천)"
else
    echo -e "${YELLOW}  ⚠ LSPrePost 소스를 찾을 수 없습니다: ${LSPREPOST_SOURCE}${NC}"
    echo "    V4 렌더링 기능을 사용하려면 LSPrePost를 수동으로 설치해야 합니다."
fi

echo ""
echo -e "${GREEN}========================================="
echo " 빌드 및 패키징 완료!"
echo "=========================================${NC}"
echo ""
echo "설치 위치: ${INSTALL_DIR}"
echo ""
echo "사용 가능한 패키지:"
echo "  1. ${INSTALL_DIR}/library/  - 컴파일된 라이브러리"
echo "     • libkood3plot.a (static)"
echo "     • libkood3plot.so (shared)"
echo ""
echo "  2. ${INSTALL_DIR}/source/   - 소스 코드"
echo ""
echo "  3. ${INSTALL_DIR}/lsprepost/ - LSPrePost 렌더링 엔진 (V4 Render)"
echo "     • lspp412_mesa (메인 실행 파일)"
echo "     • lib/ (라이브러리)"
echo ""
echo "통합 CLI 도구:"
echo "  ${INSTALL_DIR}/bin/kood3plot_cli"
echo "  사용법: kood3plot_cli --mode <query|render|batch|autosection|multirun> ..."
echo ""
echo "자세한 사용법:"
echo "  cat ${INSTALL_DIR}/README.md"
echo "  cat ${INSTALL_DIR}/docs/KOOD3PLOT_CLI_사용법.md"
echo ""
