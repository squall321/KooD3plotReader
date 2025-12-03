# KooD3plot 빌드 가이드

이 문서는 KooD3plot 라이브러리 (V1 Core + V3 Query System)를 빌드하는 방법을 설명합니다.

## 📋 요구사항

### 필수 요구사항
- **CMake**: 3.15 이상
- **C++ 컴파일러**: C++17 지원
  - GCC 7.0 이상
  - Clang 5.0 이상
  - MSVC 2017 이상

### 선택적 요구사항
- **OpenMP**: 병렬 처리 (권장)
- **Google Test**: 단위 테스트 (자동 다운로드 가능)

---

## 🚀 빠른 시작

### Linux/macOS
```bash
# 1. 저장소 클론
git clone <repository-url>
cd KooD3plotReader

# 2. 빌드 디렉토리 생성
mkdir build && cd build

# 3. CMake 설정
cmake ..

# 4. 빌드
make -j$(nproc)

# 5. 예제 실행
./examples/v3_basic_query /path/to/d3plot
```

### Windows
```cmd
# 1. 저장소 클론
git clone <repository-url>
cd KooD3plotReader

# 2. 빌드 디렉토리 생성
mkdir build
cd build

# 3. CMake 설정 (Visual Studio)
cmake .. -G "Visual Studio 16 2019"

# 4. 빌드
cmake --build . --config Release

# 5. 예제 실행
.\examples\Release\v3_basic_query.exe C:\path\to\d3plot
```

---

## ⚙️ 빌드 옵션

### CMake 옵션

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `KOOD3PLOT_BUILD_TESTS` | `ON` | 단위 테스트 빌드 |
| `KOOD3PLOT_BUILD_EXAMPLES` | `ON` | 예제 프로그램 빌드 |
| `KOOD3PLOT_BUILD_V3_QUERY` | `ON` | V3 Query System 빌드 |
| `KOOD3PLOT_ENABLE_OPENMP` | `ON` | OpenMP 병렬화 활성화 |
| `KOOD3PLOT_ENABLE_SIMD` | `ON` | SIMD 최적화 활성화 |

### 옵션 사용 예제

```bash
# V3 Query System 없이 Core만 빌드
cmake .. -DKOOD3PLOT_BUILD_V3_QUERY=OFF

# Release 빌드 + OpenMP + SIMD
cmake .. -DCMAKE_BUILD_TYPE=Release \
         -DKOOD3PLOT_ENABLE_OPENMP=ON \
         -DKOOD3PLOT_ENABLE_SIMD=ON

# 테스트 및 예제 없이 라이브러리만 빌드
cmake .. -DKOOD3PLOT_BUILD_TESTS=OFF \
         -DKOOD3PLOT_BUILD_EXAMPLES=OFF

# Debug 빌드
cmake .. -DCMAKE_BUILD_TYPE=Debug
```

---

## 📦 빌드 산출물

빌드 후 다음 파일들이 생성됩니다:

### 라이브러리
```
build/
├── libkood3plot.a              # Core library (V1)
└── libkood3plot_query.a        # Query System library (V3)
```

### 예제 프로그램
```
build/examples/
# V1 예제
├── simple_read
├── extract_stress
├── extract_displacement
├── show_stress_strain
├── show_narbs
└── ...

# V3 예제
└── v3_basic_query
```

### 테스트
```
build/tests/
└── (단위 테스트 실행 파일들)
```

---

## 🔧 고급 빌드 설정

### 1. 컴파일러 선택

```bash
# GCC 사용
cmake .. -DCMAKE_CXX_COMPILER=g++

# Clang 사용
cmake .. -DCMAKE_CXX_COMPILER=clang++

# 특정 버전 지정
cmake .. -DCMAKE_CXX_COMPILER=g++-11
```

### 2. 설치 위치 지정

```bash
# 사용자 정의 설치 경로
cmake .. -DCMAKE_INSTALL_PREFIX=/usr/local

# 빌드 후 설치
make install
```

설치 후 구조:
```
/usr/local/
├── lib/
│   ├── libkood3plot.a
│   └── libkood3plot_query.a
├── include/
│   └── kood3plot/
│       ├── D3plotReader.hpp
│       ├── Types.hpp
│       └── query/
│           ├── D3plotQuery.h
│           ├── PartSelector.h
│           └── ...
└── lib/cmake/KooD3plot/
    └── KooD3plotTargets.cmake
```

### 3. 병렬 빌드

```bash
# Linux/macOS
make -j$(nproc)              # 모든 코어 사용
make -j4                     # 4개 코어 사용

# Windows
cmake --build . --parallel 8  # 8개 코어 사용
```

### 4. Verbose 빌드

```bash
# 상세 컴파일 명령 출력
make VERBOSE=1

# 또는
cmake --build . --verbose
```

---

## 🧪 테스트 실행

### CTest 사용
```bash
cd build
ctest --verbose
```

### 개별 테스트 실행
```bash
cd build/tests
./test_control_data
./test_geometry
./test_state_data
```

---

## 📚 프로젝트에 통합

### CMake 프로젝트에서 사용

```cmake
# 1. KooD3plot 찾기
find_package(KooD3plot REQUIRED)

# 2. 타겟에 링크
add_executable(my_app main.cpp)

# V1 Core만 사용
target_link_libraries(my_app PRIVATE KooD3plot::kood3plot)

# V3 Query System 사용
target_link_libraries(my_app PRIVATE KooD3plot::kood3plot_query)
```

### 수동 링크

```bash
# 컴파일
g++ -std=c++17 \
    my_app.cpp \
    -I/usr/local/include \
    -L/usr/local/lib \
    -lkood3plot_query \
    -lkood3plot \
    -o my_app
```

---

## 🐛 문제 해결

### CMake 설정 실패

**문제**: `CMake Error: CMake was unable to find a build program`

**해결**:
```bash
# Linux
sudo apt-get install build-essential cmake

# macOS
xcode-select --install
brew install cmake
```

### OpenMP 찾을 수 없음

**문제**: `Could NOT find OpenMP`

**해결**:
```bash
# Linux
sudo apt-get install libomp-dev

# macOS
brew install libomp
```

또는 OpenMP 비활성화:
```bash
cmake .. -DKOOD3PLOT_ENABLE_OPENMP=OFF
```

### C++17 컴파일 오류

**문제**: `error: 'std::optional' was not declared`

**해결**: 컴파일러 버전 확인
```bash
g++ --version   # 7.0 이상 필요
clang++ --version  # 5.0 이상 필요
```

업데이트:
```bash
# Ubuntu
sudo apt-get install g++-9

# Specify compiler
cmake .. -DCMAKE_CXX_COMPILER=g++-9
```

### 링크 오류

**문제**: `undefined reference to ...`

**해결**:
1. 라이브러리 순서 확인: `kood3plot_query`가 `kood3plot` 앞에
2. 재빌드: `make clean && make`
3. CMake 캐시 삭제: `rm -rf build && mkdir build && cd build && cmake ..`

---

## 📊 빌드 타임 최적화

### ccache 사용
```bash
# ccache 설치
sudo apt-get install ccache  # Linux
brew install ccache          # macOS

# CMake에서 ccache 사용
cmake .. -DCMAKE_CXX_COMPILER_LAUNCHER=ccache
```

### Unity Build (실험적)
```bash
cmake .. -DCMAKE_UNITY_BUILD=ON
```

---

## 🔍 빌드 설정 확인

빌드 설정 요약 보기:
```bash
cd build
cmake .. -L
```

상세 설정:
```bash
cmake .. -LAH
```

---

## 📝 빌드 로그 저장

```bash
# 빌드 로그 파일로 저장
cmake .. 2>&1 | tee cmake.log
make 2>&1 | tee build.log
```

---

## 🌐 크로스 컴파일

### ARM (예: Raspberry Pi)
```bash
# ARM 툴체인 파일 사용
cmake .. -DCMAKE_TOOLCHAIN_FILE=../cmake/arm-toolchain.cmake
```

### MinGW (Windows on Linux)
```bash
cmake .. -DCMAKE_TOOLCHAIN_FILE=../cmake/mingw-toolchain.cmake
```

---

## 📖 추가 리소스

- [CMake Documentation](https://cmake.org/documentation/)
- [C++17 Feature List](https://en.cppreference.com/w/cpp/17)
- [OpenMP Documentation](https://www.openmp.org/)

---

**마지막 업데이트**: 2025-11-21
**지원 플랫폼**: Linux, macOS, Windows
**C++ 표준**: C++17
