@echo off
REM ============================================================
REM KooD3plotReader - 개발 환경 자동 설정 스크립트 (Windows)
REM
REM 이 스크립트는:
REM 1. vcpkg 설치 확인/설치
REM 2. 필요한 패키지 설치
REM 3. 로컬 deps/ 폴더로 복사
REM 4. CMake 빌드 설정
REM
REM 사용법:
REM   setup_dev_env.bat [vcpkg_path]
REM ============================================================

setlocal enabledelayedexpansion

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║         KooD3plotReader Development Environment Setup        ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

REM 프로젝트 루트
set SCRIPT_DIR=%~dp0
set PROJECT_ROOT=%SCRIPT_DIR%..
cd /d "%PROJECT_ROOT%"

REM vcpkg 경로 설정
set VCPKG_ROOT=%1
if "%VCPKG_ROOT%"=="" (
    if defined VCPKG_ROOT (
        echo vcpkg 환경변수 사용: %VCPKG_ROOT%
    ) else (
        set VCPKG_ROOT=C:\dev\vcpkg
    )
)

set TRIPLET=x64-windows

echo [설정]
echo   Project:    %PROJECT_ROOT%
echo   vcpkg:      %VCPKG_ROOT%
echo   Triplet:    %TRIPLET%
echo.

REM ============================================================
REM Step 1: vcpkg 설치 확인
REM ============================================================
echo [1/5] vcpkg 확인 중...

if not exist "%VCPKG_ROOT%\vcpkg.exe" (
    echo   vcpkg가 없습니다. 설치를 시작합니다...

    REM 부모 디렉토리 생성
    for %%i in ("%VCPKG_ROOT%") do set VCPKG_PARENT=%%~dpi
    if not exist "%VCPKG_PARENT%" mkdir "%VCPKG_PARENT%"

    echo   vcpkg 클론 중...
    git clone https://github.com/microsoft/vcpkg.git "%VCPKG_ROOT%"
    if errorlevel 1 (
        echo [오류] git clone 실패
        exit /b 1
    )

    echo   vcpkg 부트스트랩 중...
    cd /d "%VCPKG_ROOT%"
    call bootstrap-vcpkg.bat
    if errorlevel 1 (
        echo [오류] bootstrap 실패
        exit /b 1
    )

    cd /d "%PROJECT_ROOT%"
    echo   vcpkg 설치 완료!
) else (
    echo   vcpkg 발견: %VCPKG_ROOT%
)

REM ============================================================
REM Step 2: 패키지 설치
REM ============================================================
echo.
echo [2/5] 패키지 설치 중...

set PACKAGES=hdf5[cpp] yaml-cpp blosc gtest

for %%p in (%PACKAGES%) do (
    echo   %%p:%TRIPLET% 확인 중...
    "%VCPKG_ROOT%\vcpkg.exe" list | findstr /i "%%p:%TRIPLET%" >nul 2>&1
    if errorlevel 1 (
        echo   %%p 설치 중... (시간이 걸릴 수 있습니다)
        "%VCPKG_ROOT%\vcpkg.exe" install %%p:%TRIPLET%
        if errorlevel 1 (
            echo [경고] %%p 설치 실패, 계속 진행합니다.
        )
    ) else (
        echo   %%p 이미 설치됨
    )
)

REM ============================================================
REM Step 3: 로컬 deps 복사
REM ============================================================
echo.
echo [3/5] 로컬 deps/ 폴더로 복사 중...

call "%SCRIPT_DIR%copy_dependencies.bat" "%VCPKG_ROOT%" "%TRIPLET%"

REM ============================================================
REM Step 4: 빌드 디렉토리 생성 및 CMake 설정
REM ============================================================
echo.
echo [4/5] CMake 설정 중...

set BUILD_DIR=%PROJECT_ROOT%\build

if not exist "%BUILD_DIR%" mkdir "%BUILD_DIR%"
cd /d "%BUILD_DIR%"

echo   CMake 구성 중...
cmake .. -DKOOD3PLOT_USE_LOCAL_DEPS=ON ^
         -DKOOD3PLOT_BUILD_HDF5=ON ^
         -DKOOD3PLOT_BUILD_TESTS=ON ^
         -DKOOD3PLOT_BUILD_EXAMPLES=ON ^
         -DCMAKE_BUILD_TYPE=Release

if errorlevel 1 (
    echo [오류] CMake 구성 실패
    exit /b 1
)

REM ============================================================
REM Step 5: 빌드 (선택적)
REM ============================================================
echo.
echo [5/5] 빌드 중...

cmake --build . --config Release

if errorlevel 1 (
    echo [경고] 빌드 실패. 수동으로 빌드해주세요.
) else (
    echo   빌드 완료!
)

REM ============================================================
REM 완료
REM ============================================================
echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║                    설정 완료!                                 ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.
echo 다음 명령으로 테스트할 수 있습니다:
echo.
echo   cd build
echo   ctest -C Release
echo.
echo 또는 직접 실행:
echo.
echo   build\Release\test_hdf5_writer.exe
echo   build\Release\test_quantization.exe
echo   build\Release\02_hdf5_benchmark.exe
echo.
echo 프로젝트를 다른 PC로 복사해도 deps/ 폴더 덕분에 바로 빌드 가능합니다!
echo.

cd /d "%PROJECT_ROOT%"
endlocal
