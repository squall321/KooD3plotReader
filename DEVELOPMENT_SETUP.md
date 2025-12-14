# 크로스플랫폼 개발 환경 설정 가이드

Phase 1 HDF5 Quantization System 개발을 위한 크로스플랫폼 환경 설정 가이드입니다.

---

## 🚀 빠른 시작 (권장)

### 자동 설정 스크립트

**Windows:**
```powershell
# 모든 것을 자동으로 설정 (vcpkg 설치, 패키지 설치, 로컬 복사, 빌드)
.\scripts\setup_dev_env.bat
```

**Linux/macOS:**
```bash
# 실행 권한 부여 후 실행
chmod +x scripts/setup_dev_env.sh
./scripts/setup_dev_env.sh
```

이 스크립트는:
1. vcpkg 설치 (없는 경우)
2. 필요한 패키지 설치 (HDF5, yaml-cpp, blosc, gtest)
3. 로컬 `deps/` 폴더로 복사 (Python venv처럼 독립적!)
4. CMake 빌드 설정

---

## 📦 로컬 의존성 시스템 (like Python venv)

프로젝트를 다른 PC로 복사해도 바로 빌드할 수 있도록 의존성을 프로젝트 내에 포함합니다.

### 구조

```
KooD3plotReader/
├── deps/                    # 로컬 의존성 (git에 포함 가능)
│   ├── x64-windows/         # Windows 64-bit
│   │   ├── include/
│   │   ├── lib/
│   │   ├── bin/            # DLLs
│   │   └── share/          # CMake configs
│   ├── x64-linux/          # Linux 64-bit
│   └── arm64-osx/          # macOS ARM
└── scripts/
    ├── setup_dev_env.bat   # Windows 자동 설정
    ├── setup_dev_env.sh    # Linux/macOS 자동 설정
    ├── copy_dependencies.bat
    └── copy_dependencies.sh
```

### 장점

1. **이식성**: 프로젝트 폴더만 복사하면 어디서든 빌드 가능
2. **버전 고정**: 테스트된 버전의 의존성 사용
3. **디버깅 용이**: IDE에서 라이브러리 소스 참조 가능
4. **오프라인 빌드**: 인터넷 없이도 빌드 가능

### 수동 복사

```powershell
# Windows
.\scripts\copy_dependencies.bat C:\dev\vcpkg x64-windows

# Linux
./scripts/copy_dependencies.sh ~/dev/vcpkg x64-linux

# macOS (ARM)
./scripts/copy_dependencies.sh ~/dev/vcpkg arm64-osx
```

### CMake에서 사용

```bash
# 자동 감지 (deps/ 폴더가 있으면 자동으로 사용)
cmake ..

# 명시적으로 로컬 deps 사용
cmake .. -DKOOD3PLOT_USE_LOCAL_DEPS=ON

# 강제로 시스템 라이브러리 사용
cmake .. -DKOOD3PLOT_USE_LOCAL_DEPS=OFF
```

---

## 필수 요구사항

### 모든 플랫폼 공통
- **CMake**: 3.15 이상
- **C++ 컴파일러**: C++17 지원 필수
  - Windows: Visual Studio 2019 이상 (MSVC 19.20+)
  - Linux: GCC 9+ 또는 Clang 10+
  - macOS: Apple Clang 11+ (Xcode 11+)

### 필수 라이브러리
- **HDF5**: C++ bindings 포함
- **yaml-cpp**: (선택적이지만 권장)
- **blosc**: (선택적, 향상된 압축)

---

## Windows 설정 (vcpkg 권장)

### 1. vcpkg 설치

```powershell
# 1. vcpkg 클론
cd C:\dev
git clone https://github.com/microsoft/vcpkg.git
cd vcpkg

# 2. Bootstrap
.\bootstrap-vcpkg.bat

# 3. Visual Studio 통합 (관리자 권한 필요)
.\vcpkg integrate install
```

### 2. 의존성 설치

```powershell
# HDF5 with C++ bindings (필수)
.\vcpkg install hdf5[cpp]:x64-windows

# yaml-cpp (권장)
.\vcpkg install yaml-cpp:x64-windows

# blosc (선택적, 향상된 압축)
.\vcpkg install blosc:x64-windows

# OpenMP 지원 (Visual Studio에 기본 포함)
# 별도 설치 불필요
```

### 3. CMake 설정

```powershell
# 프로젝트 디렉토리로 이동
cd C:\Users\squal\Documents\Projects\KooD3plotReader

# vcpkg toolchain 파일 경로 설정
$env:VCPKG_ROOT = "C:\dev\vcpkg"

# 빌드 디렉토리 생성
mkdir build
cd build

# CMake 구성 (vcpkg toolchain 사용)
cmake .. -DCMAKE_TOOLCHAIN_FILE="C:\dev\vcpkg\scripts\buildsystems\vcpkg.cmake" `
         -DCMAKE_BUILD_TYPE=Release `
         -DKOOD3PLOT_BUILD_HDF5=ON

# 빌드
cmake --build . --config Release
```

### 4. Visual Studio에서 열기

```powershell
# CMake 프로젝트로 열기
# Visual Studio 2019/2022에서 "Open Folder" → KooD3plotReader 폴더 선택

# CMakeSettings.json에서 vcpkg 경로 설정
# {
#   "configurations": [{
#     "name": "x64-Release",
#     "generator": "Ninja",
#     "configurationType": "Release",
#     "cmakeToolchain": "C:/dev/vcpkg/scripts/buildsystems/vcpkg.cmake"
#   }]
# }
```

---

## Linux 설정 (Ubuntu/Debian)

### 방법 1: 시스템 패키지 관리자 (apt)

```bash
# 1. 기본 빌드 도구 설치
sudo apt update
sudo apt install build-essential cmake git

# 2. HDF5 with C++ bindings
sudo apt install libhdf5-dev libhdf5-cpp-103

# 3. yaml-cpp
sudo apt install libyaml-cpp-dev

# 4. OpenMP (GCC에 기본 포함)
# 별도 설치 불필요

# 5. 빌드
mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release -DKOOD3PLOT_BUILD_HDF5=ON
make -j$(nproc)
```

### 방법 2: vcpkg (권장 - 최신 버전)

```bash
# 1. vcpkg 설치
cd ~/dev
git clone https://github.com/microsoft/vcpkg.git
cd vcpkg
./bootstrap-vcpkg.sh

# 2. 의존성 설치
./vcpkg install hdf5[cpp]:x64-linux
./vcpkg install yaml-cpp:x64-linux
./vcpkg install blosc:x64-linux  # 선택적

# 3. 빌드
cd ~/Projects/KooD3plotReader
mkdir build && cd build
cmake .. -DCMAKE_TOOLCHAIN_FILE=~/dev/vcpkg/scripts/buildsystems/vcpkg.cmake \
         -DCMAKE_BUILD_TYPE=Release \
         -DKOOD3PLOT_BUILD_HDF5=ON
make -j$(nproc)
```

---

## macOS 설정

### 방법 1: Homebrew

```bash
# 1. Homebrew 설치 (이미 설치된 경우 생략)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 2. 의존성 설치
brew install cmake
brew install hdf5
brew install yaml-cpp

# 3. OpenMP (macOS는 별도 설치 필요)
brew install libomp

# 4. 빌드
mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release \
         -DKOOD3PLOT_BUILD_HDF5=ON \
         -DOpenMP_ROOT=$(brew --prefix libomp)
make -j$(sysctl -n hw.ncpu)
```

### 방법 2: vcpkg (ARM Mac 권장)

```bash
# 1. vcpkg 설치
cd ~/dev
git clone https://github.com/microsoft/vcpkg.git
cd vcpkg
./bootstrap-vcpkg.sh

# 2. ARM Mac용 의존성 설치
./vcpkg install hdf5[cpp]:arm64-osx
./vcpkg install yaml-cpp:arm64-osx
./vcpkg install blosc:arm64-osx  # 선택적

# 또는 Intel Mac용
# ./vcpkg install hdf5[cpp]:x64-osx
# ./vcpkg install yaml-cpp:x64-osx

# 3. 빌드
cd ~/Projects/KooD3plotReader
mkdir build && cd build
cmake .. -DCMAKE_TOOLCHAIN_FILE=~/dev/vcpkg/scripts/buildsystems/vcpkg.cmake \
         -DCMAKE_BUILD_TYPE=Release \
         -DKOOD3PLOT_BUILD_HDF5=ON
make -j$(sysctl -n hw.ncpu)
```

---

## 빌드 검증

### 빌드 성공 확인

```bash
# 1. 라이브러리 생성 확인
ls build/lib*kood3plot_hdf5*

# Windows (MSVC)
# build/Release/kood3plot_hdf5.lib

# Linux
# build/libkood3plot_hdf5.a (static)
# build/libkood3plot_hdf5.so (shared)

# macOS
# build/libkood3plot_hdf5.a (static)
# build/libkood3plot_hdf5.dylib (shared)
```

### CMake 출력 확인

빌드 시 다음 메시지가 표시되어야 합니다:

```
-- HDF5 found: 1.12.x
-- HDF5 include dirs: /path/to/hdf5/include
-- HDF5 libraries: /path/to/hdf5/lib/libhdf5_cpp.so;...
-- yaml-cpp found
-- Building Phase 1: HDF5 Quantization System
-- Phase 1 HDF5 Quantization System library configured
```

---

## 문제 해결

### Windows: HDF5 not found

```powershell
# vcpkg가 올바르게 통합되었는지 확인
.\vcpkg integrate install

# HDF5 설치 확인
.\vcpkg list | Select-String "hdf5"

# CMake toolchain 경로 확인
cmake .. -DCMAKE_TOOLCHAIN_FILE="C:\dev\vcpkg\scripts\buildsystems\vcpkg.cmake"
```

### Linux: undefined reference to H5::H5File

```bash
# HDF5 C++ bindings이 설치되었는지 확인
dpkg -l | grep libhdf5-cpp

# 없으면 설치
sudo apt install libhdf5-cpp-103

# 또는 vcpkg 사용
./vcpkg install hdf5[cpp]:x64-linux
```

### macOS: OpenMP not found

```bash
# libomp 설치
brew install libomp

# CMake에서 경로 지정
cmake .. -DOpenMP_ROOT=$(brew --prefix libomp)

# 또는 환경변수 설정
export OpenMP_ROOT=$(brew --prefix libomp)
```

### vcpkg: triplet 에러

```bash
# 기본 triplet 확인
./vcpkg help triplet

# 명시적으로 triplet 지정
# Windows 64-bit
.\vcpkg install hdf5[cpp]:x64-windows

# Linux 64-bit
./vcpkg install hdf5[cpp]:x64-linux

# macOS ARM (M1/M2)
./vcpkg install hdf5[cpp]:arm64-osx

# macOS Intel
./vcpkg install hdf5[cpp]:x64-osx
```

---

## IDE 설정

### Visual Studio Code

1. **C/C++ Extension** 설치
2. **CMake Tools Extension** 설치
3. `.vscode/settings.json` 생성:

```json
{
  "cmake.configureArgs": [
    "-DCMAKE_TOOLCHAIN_FILE=C:/dev/vcpkg/scripts/buildsystems/vcpkg.cmake",
    "-DKOOD3PLOT_BUILD_HDF5=ON"
  ],
  "cmake.buildDirectory": "${workspaceFolder}/build"
}
```

### Visual Studio 2019/2022

1. "Open Folder" → KooD3plotReader 폴더 선택
2. `CMakeSettings.json` 생성 (자동 생성됨)
3. vcpkg toolchain 경로 추가:

```json
{
  "configurations": [
    {
      "name": "x64-Release",
      "generator": "Ninja",
      "configurationType": "Release",
      "buildRoot": "${projectDir}\\out\\build\\${name}",
      "installRoot": "${projectDir}\\out\\install\\${name}",
      "cmakeCommandArgs": "",
      "buildCommandArgs": "",
      "ctestCommandArgs": "",
      "cmakeToolchain": "C:/dev/vcpkg/scripts/buildsystems/vcpkg.cmake"
    }
  ]
}
```

### CLion

1. File → Settings → Build, Execution, Deployment → CMake
2. CMake options 추가:
   ```
   -DCMAKE_TOOLCHAIN_FILE=/path/to/vcpkg/scripts/buildsystems/vcpkg.cmake
   -DKOOD3PLOT_BUILD_HDF5=ON
   ```

---

## 환경 변수 (선택적)

### Windows (PowerShell Profile)

```powershell
# $PROFILE 파일 열기
notepad $PROFILE

# 추가
$env:VCPKG_ROOT = "C:\dev\vcpkg"
$env:CMAKE_TOOLCHAIN_FILE = "$env:VCPKG_ROOT\scripts\buildsystems\vcpkg.cmake"
```

### Linux/macOS (.bashrc 또는 .zshrc)

```bash
# ~/.bashrc 또는 ~/.zshrc에 추가
export VCPKG_ROOT="$HOME/dev/vcpkg"
export CMAKE_TOOLCHAIN_FILE="$VCPKG_ROOT/scripts/buildsystems/vcpkg.cmake"
```

---

## 다음 단계

개발 환경 설정이 완료되면:

1. **Week 1 구현 시작** - HDF5Writer.cpp 작성
2. **첫 번째 테스트** - test_hdf5_writer.cpp
3. **벤치마크** - 100k 노드 mesh 저장/로드

자세한 구현 계획은 [READY_TO_START.md](READY_TO_START.md)를 참조하세요.

---

**크로스플랫폼 원칙 준수**:
- ✅ 표준 C++17만 사용
- ✅ CMake 단일 빌드 시스템
- ✅ vcpkg 의존성 관리
- ✅ std::filesystem 경로 처리
- ✅ 플랫폼별 #ifdef 최소화
