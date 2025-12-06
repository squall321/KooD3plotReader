# KooD3plotReader Windows 크로스플랫폼 빌드 계획

## 1. 현재 상태 분석

### 1.1 프로젝트 구조
```
KooD3plotReader/
├── CMakeLists.txt          # 이미 MSVC 지원 포함
├── build.sh                # Linux 빌드 스크립트
├── src/                    # 소스 코드
│   ├── core/              # 핵심 라이브러리 (플랫폼 독립적)
│   ├── parsers/           # 파서 (플랫폼 독립적)
│   ├── data/              # 데이터 구조 (플랫폼 독립적)
│   ├── query/             # 쿼리 시스템 (플랫폼 독립적)
│   ├── render/            # 렌더러 (플랫폼 의존 코드 포함)
│   ├── analysis/          # 분석 시스템 (플랫폼 독립적)
│   ├── export/            # 내보내기 (플랫폼 독립적)
│   └── cli/               # CLI 도구 (플랫폼 독립적)
├── include/               # 헤더 파일
└── examples/              # 예제 프로그램
```

### 1.2 플랫폼 의존성 분석

| 파일 | 리눅스 전용 코드 | 현재 상태 |
|------|------------------|-----------|
| `src/render/LSPrePostRenderer.cpp` | `fork()`, `waitpid()`, `execl()`, `chdir()` | **이미 해결됨** - `#ifdef _WIN32`로 Windows API 사용 |
| 기타 모든 소스 파일 | 없음 | 플랫폼 독립적 |

### 1.3 CMakeLists.txt 현재 상태
- MSVC 컴파일러 옵션 이미 포함 (`/W4`, `/O2`, `/arch:AVX2`)
- OpenMP 지원
- Google Test FetchContent 지원 (Windows CRT 설정 포함)

---

## 2. Windows 빌드 구현 계획

### 2.1 build.bat 스크립트 생성

#### 주요 기능
1. Visual Studio 환경 자동 감지 및 설정
2. CMake 빌드 (Release 모드)
3. Static/Shared 라이브러리 빌드
4. 설치 패키지 생성
5. 예제 및 CLI 도구 포함

#### 스크립트 구조
```batch
@echo off
REM KooD3plotReader Windows Build Script

REM [1/7] Visual Studio 환경 설정
REM [2/7] 이전 빌드 정리
REM [3/7] 빌드 디렉토리 생성
REM [4/7] CMake 설정 (Static 라이브러리)
REM [5/7] Static 라이브러리 빌드
REM [5.5/7] CMake 재설정 (Shared 라이브러리)
REM [6/7] 패키지 구조 생성
REM [7/7] 문서 및 예제 복사
```

### 2.2 Visual Studio 버전 지원

| VS 버전 | vcvarsall.bat 경로 |
|---------|-------------------|
| VS 2022 | `C:\Program Files\Microsoft Visual Studio\2022\{Edition}\VC\Auxiliary\Build\vcvarsall.bat` |
| VS 2019 | `C:\Program Files (x86)\Microsoft Visual Studio\2019\{Edition}\VC\Auxiliary\Build\vcvarsall.bat` |

지원 에디션: Community, Professional, Enterprise

### 2.3 출력 구조 (build.sh와 동일)

```
installed/
├── README.md
├── USAGE.md
├── LICENSE
├── docs/
│   ├── README.md
│   ├── USAGE.md
│   └── KOOD3PLOT_CLI_사용법.md
├── bin/
│   └── kood3plot_cli.exe
├── library/
│   ├── lib/
│   │   ├── kood3plot.lib      (Static)
│   │   └── kood3plot.dll      (Shared)
│   ├── include/
│   │   └── kood3plot/
│   ├── examples/
│   ├── CMakeLists.txt.example
│   └── main.cpp.example
└── source/
    ├── kood3plot/
    │   ├── include/
    │   └── src/
    ├── examples/
    ├── CMakeLists.txt.example
    └── main.cpp.example
```

---

## 3. 필요한 소스 코드 변경 사항

### 3.1 변경 불필요 (이미 크로스플랫폼)
- `src/render/LSPrePostRenderer.cpp` - 이미 `#ifdef _WIN32` 분기 구현됨
- `CMakeLists.txt` - 이미 MSVC 옵션 포함

### 3.2 추가 고려 사항

#### 3.2.1 파일 경로 구분자
현재 코드에서 `std::filesystem`을 사용하므로 자동으로 처리됨.

#### 3.2.2 Windows 전용 설정 (선택적)
```cpp
// LSPrePostRenderer.cpp에 이미 포함됨
#ifdef _WIN32
#include <windows.h>
// CreateProcess() 사용
#else
#include <unistd.h>
#include <sys/wait.h>
// fork()/execl() 사용
#endif
```

---

## 4. 구현 작업 목록

### Phase 1: build.bat 생성
- [ ] Visual Studio 환경 자동 감지
- [ ] CMake 빌드 명령 구성
- [ ] Static/Shared 라이브러리 빌드
- [ ] CLI 도구 빌드
- [ ] 설치 패키지 구조 생성

### Phase 2: 테스트
- [ ] VS 2022 빌드 테스트
- [ ] VS 2019 빌드 테스트
- [ ] 생성된 라이브러리 링크 테스트
- [ ] CLI 도구 실행 테스트

### Phase 3: 문서화
- [ ] Windows 빌드 가이드 추가
- [ ] README.md에 Windows 지원 명시
- [ ] 트러블슈팅 가이드

---

## 5. build.bat 상세 설계

### 5.1 환경 변수 설정
```batch
set PROJECT_ROOT=%~dp0
set BUILD_DIR=%PROJECT_ROOT%build
set INSTALL_DIR=%PROJECT_ROOT%installed
set ARCH=x64
```

### 5.2 Visual Studio 감지 로직
```batch
REM VS 2022 확인
if exist "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvarsall.bat" (
    call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvarsall.bat" %ARCH%
    goto :vs_found
)
REM VS 2019 확인...
```

### 5.3 CMake 빌드 명령
```batch
REM Static 라이브러리
cmake -G "NMake Makefiles" ^
      -DCMAKE_BUILD_TYPE=Release ^
      -DBUILD_SHARED_LIBS=OFF ^
      -DCMAKE_INSTALL_PREFIX="%INSTALL_DIR%\library" ^
      ..
nmake
nmake install

REM Shared 라이브러리
cmake -G "NMake Makefiles" ^
      -DCMAKE_BUILD_TYPE=Release ^
      -DBUILD_SHARED_LIBS=ON ^
      -DCMAKE_INSTALL_PREFIX="%INSTALL_DIR%\library" ^
      ..
nmake
nmake install
```

### 5.4 대안: Ninja 또는 MSBuild
```batch
REM Ninja 사용 (더 빠름)
cmake -G "Ninja" -DCMAKE_BUILD_TYPE=Release ..
ninja

REM MSBuild 사용 (Visual Studio 솔루션)
cmake -G "Visual Studio 17 2022" -A x64 ..
msbuild KooD3plotReader.sln /p:Configuration=Release
```

---

## 6. 잠재적 이슈 및 해결책

### 6.1 OpenMP
- **이슈**: MSVC의 OpenMP 지원은 2.0 수준
- **해결**: CMakeLists.txt에서 이미 처리됨 (OpenMP 옵션)

### 6.2 C++17 filesystem
- **이슈**: 구 버전 MSVC는 `std::filesystem` 지원 제한적
- **해결**: VS 2017 15.7 이상 필요 (권장: VS 2019/2022)

### 6.3 문자 인코딩
- **이슈**: 한글 파일명 처리
- **해결**: UTF-8 소스 파일 인코딩 유지

### 6.4 라이브러리 확장자
| 플랫폼 | Static | Shared |
|--------|--------|--------|
| Linux  | `.a`   | `.so`  |
| Windows| `.lib` | `.dll` + `.lib` (import lib) |

---

## 7. 테스트 체크리스트

### 7.1 빌드 테스트
- [ ] `build.bat` 실행 성공
- [ ] `kood3plot.lib` 생성 확인
- [ ] `kood3plot.dll` 생성 확인
- [ ] `kood3plot_cli.exe` 생성 확인

### 7.2 기능 테스트
- [ ] CLI 도구로 d3plot 파일 읽기
- [ ] 예제 프로그램 빌드 및 실행
- [ ] Static 라이브러리 링크 테스트
- [ ] Shared 라이브러리 링크 테스트

### 7.3 호환성 테스트
- [ ] Windows 10 x64
- [ ] Windows 11 x64
- [ ] VS 2019
- [ ] VS 2022

---

## 8. 결론

현재 KooD3plotReader 프로젝트는 **이미 크로스플랫폼을 위한 코드 준비가 완료**되어 있습니다:

1. `LSPrePostRenderer.cpp`에 Windows/Linux 분기 처리 완료
2. `CMakeLists.txt`에 MSVC 컴파일러 옵션 포함
3. `std::filesystem` 사용으로 경로 처리 자동화

**필요한 작업**:
1. `build.bat` 스크립트 생성 (build.sh의 Windows 버전)
2. Windows 환경 감지 및 설정 자동화
3. 패키지 구조 생성 로직 구현

소스 코드 변경은 **불필요**합니다.

---

## 다음 단계

이 계획이 승인되면:
1. `build.bat` 파일 생성
2. Windows 환경에서 테스트
3. README.md 업데이트 (Windows 빌드 가이드 추가)
