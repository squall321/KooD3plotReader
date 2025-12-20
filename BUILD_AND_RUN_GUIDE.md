# KooD3plotReader - 빌드 및 실행 가이드

> **크로스플랫폼 지원**: Windows, Linux, macOS

## 빠른 시작

### 1. .NET 시각화 앱 실행 (권장)

```powershell
cd c:\Users\squal\Documents\Projects\KooD3plotReader\vis-app-net\src\KooD3plotViewer
dotnet run
```

또는 빌드 후 실행:
```powershell
dotnet build
.\bin\Debug\net8.0\KooD3plotViewer.exe
```

### 2. C++ 라이브러리 빌드

```powershell
cd c:\Users\squal\Documents\Projects\KooD3plotReader
.\build.bat
```

---

## 상세 가이드

### 필수 요구사항

#### Windows

| 컴포넌트 | 버전 | 설치 방법 |
|---------|------|----------|
| .NET SDK | 8.0+ | https://dotnet.microsoft.com/download |
| Visual Studio | 2019+ | https://visualstudio.microsoft.com |
| vcpkg | latest | `git clone https://github.com/microsoft/vcpkg.git` |

#### Linux (Ubuntu/Debian)

| 컴포넌트 | 버전 | 설치 방법 |
|---------|------|----------|
| .NET SDK | 8.0+ | `sudo apt install dotnet-sdk-8.0` |
| HDF5 | 1.10+ | `sudo apt install libhdf5-dev` |
| Vulkan | latest | `sudo apt install libvulkan1 mesa-vulkan-drivers` |

```bash
# Ubuntu/Debian 전체 설치
sudo apt update
sudo apt install dotnet-sdk-8.0 libhdf5-dev libvulkan1 mesa-vulkan-drivers
```

#### macOS

| 컴포넌트 | 버전 | 설치 방법 |
|---------|------|----------|
| .NET SDK | 8.0+ | `brew install dotnet-sdk` |
| HDF5 | 1.10+ | `brew install hdf5` |

```bash
# Homebrew로 설치
brew install dotnet-sdk hdf5
```

### .NET 앱 의존성 (자동 복원)

```xml
<!-- NuGet 패키지 (자동 설치됨) -->
Avalonia 11.2.1
Veldrid 4.9.0
Veldrid.SPIRV 1.0.15
```

---

## 빌드 옵션

### Option A: .NET 시각화 앱 빌드 (Windows)

```powershell
# 프로젝트 폴더로 이동
cd c:\Users\squal\Documents\Projects\KooD3plotReader\vis-app-net\src\KooD3plotViewer

# 의존성 복원 + 빌드
dotnet restore
dotnet build

# 실행
dotnet run

# 또는 Release 빌드
dotnet build -c Release
.\bin\Release\net8.0\KooD3plotViewer.exe
```

### Option B: .NET 시각화 앱 빌드 (Linux)

```bash
# 프로젝트 폴더로 이동
cd ~/KooD3plotReader/vis-app-net/src/KooD3plotViewer

# 의존성 복원 + 빌드
dotnet restore
dotnet build

# 실행
dotnet run

# 또는 Release 빌드
dotnet build -c Release
./bin/Release/net8.0/KooD3plotViewer
```

### Option C: .NET 시각화 앱 빌드 (macOS)

```bash
# 프로젝트 폴더로 이동
cd ~/KooD3plotReader/vis-app-net/src/KooD3plotViewer

# 의존성 복원 + 빌드
dotnet restore
dotnet build

# 실행
dotnet run
```

### Option D: 전체 솔루션 빌드 (모든 플랫폼)

```bash
cd vis-app-net

# 전체 솔루션 빌드
dotnet build KooD3plotViewer.sln

# 실행
dotnet run --project src/KooD3plotViewer
```

### Option E: C++ 라이브러리 빌드 (Windows, vcpkg 필요)

```powershell
cd c:\Users\squal\Documents\Projects\KooD3plotReader

# vcpkg 의존성 설치 (최초 1회)
.\devvcpkg\vcpkg install hdf5[cpp]:x64-windows
.\devvcpkg\vcpkg install yaml-cpp:x64-windows

# 빌드
.\build.bat
```

### Option F: C++ 라이브러리 빌드 (Linux)

```bash
# 의존성 설치
sudo apt install cmake g++ libhdf5-dev libyaml-cpp-dev

# 빌드
mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j$(nproc)
```

---

## 실행 방법

### GUI 앱 실행

```powershell
# 방법 1: dotnet run
cd vis-app-net\src\KooD3plotViewer
dotnet run

# 방법 2: 직접 실행
.\vis-app-net\src\KooD3plotViewer\bin\Debug\net8.0\KooD3plotViewer.exe
```

### 앱 사용법

1. **파일 열기**: `File > Open` 또는 `Ctrl+O`
2. **HDF5 파일 선택**: `.h5` 파일 선택
3. **3D 뷰 조작**:
   - 좌클릭 드래그: 회전
   - 우클릭 드래그: 패닝
   - 스크롤: 줌

---

## 문제 해결

### 공통 에러

**"SDK not found"**
```bash
# .NET SDK 설치 확인
dotnet --version
# 8.0 이상이어야 함
```

**"Veldrid 초기화 실패"**
- GPU 드라이버 업데이트 필요
- 앱이 자동으로 소프트웨어 렌더링으로 폴백함

**"HDF5 파일 로드 실패"**
- HDF5 파일 형식 확인 (KooD3plot 형식이어야 함)
- 로그 패널에서 에러 메시지 확인

### Windows 관련

**"HDF5 DLL not found"**
- NuGet 패키지가 자동으로 HDF5 DLL을 포함함
- `dotnet restore` 재실행

### Linux 관련

**"libhdf5.so not found"**
```bash
# HDF5 라이브러리 설치
sudo apt install libhdf5-dev

# 라이브러리 경로 확인
ldconfig -p | grep hdf5
```

**"Vulkan not available"**
```bash
# Vulkan 드라이버 설치
sudo apt install libvulkan1 mesa-vulkan-drivers

# NVIDIA의 경우
sudo apt install nvidia-driver-xxx  # xxx = 버전 번호
```

**"DISPLAY not set" (SSH 환경)**
```bash
# X11 포워딩 사용
ssh -X user@host

# 또는 DISPLAY 설정
export DISPLAY=:0
```

### macOS 관련

**"libhdf5.dylib not found"**
```bash
# Homebrew로 HDF5 설치
brew install hdf5

# 라이브러리 경로 확인
brew --prefix hdf5
```

### 성능 문제

**느린 렌더링**
- GPU 렌더링이 활성화되었는지 로그 확인
- "GPU: Vulkan initialized" 또는 "GPU: D3D11 initialized" 메시지 확인

**Linux에서 GPU 백엔드 확인**
```bash
# Vulkan 지원 확인
vulkaninfo | head -20
```

---

## 프로젝트 구조

```
KooD3plotReader/
├── build.bat                 # C++ 빌드 스크립트
├── CMakeLists.txt           # C++ CMake 설정
├── include/                  # C++ 헤더
├── src/                      # C++ 소스
├── vis-app-net/             # .NET 시각화 앱
│   └── src/
│       ├── KooD3plot.Data/      # HDF5 데이터 로더
│       ├── KooD3plot.Rendering/ # 렌더링 라이브러리
│       └── KooD3plotViewer/     # Avalonia UI 앱
│           ├── Views/           # UI 뷰
│           ├── ViewModels/      # MVVM 뷰모델
│           └── Rendering/       # GPU 렌더러
└── examples/                 # C++ 예제
```

---

## 테스트 데이터

HDF5 테스트 파일 생성:
```powershell
# C++ 예제 실행 (빌드 후)
.\build\Release\examples\01_basic_hdf5_export.exe input.d3plot output.h5
```

또는 기존 HDF5 파일이 있다면:
```
c:\Users\squal\Documents\Projects\KooD3plotReader\build\*.h5
```
