@echo off
REM ============================================================
REM KooD3plotReader - vcpkg 의존성 로컬 복사 스크립트 (Windows)
REM
REM 사용법:
REM   copy_dependencies.bat [vcpkg_root] [triplet]
REM
REM 예시:
REM   copy_dependencies.bat C:\dev\vcpkg x64-windows
REM   copy_dependencies.bat                          (기본값 사용)
REM ============================================================

setlocal enabledelayedexpansion

echo.
echo ========================================
echo  KooD3plotReader Dependency Copier
echo ========================================
echo.

REM 기본값 설정
set VCPKG_ROOT=%1
if "%VCPKG_ROOT%"=="" (
    if defined VCPKG_ROOT (
        set VCPKG_ROOT=%VCPKG_ROOT%
    ) else (
        set VCPKG_ROOT=C:\dev\vcpkg
    )
)

set TRIPLET=%2
if "%TRIPLET%"=="" set TRIPLET=x64-windows

REM 프로젝트 루트 찾기
set SCRIPT_DIR=%~dp0
set PROJECT_ROOT=%SCRIPT_DIR%..

REM 로컬 deps 디렉토리
set DEPS_DIR=%PROJECT_ROOT%\deps\%TRIPLET%

echo [설정]
echo   VCPKG_ROOT:   %VCPKG_ROOT%
echo   TRIPLET:      %TRIPLET%
echo   PROJECT_ROOT: %PROJECT_ROOT%
echo   DEPS_DIR:     %DEPS_DIR%
echo.

REM vcpkg 확인
if not exist "%VCPKG_ROOT%\vcpkg.exe" (
    echo [오류] vcpkg를 찾을 수 없습니다: %VCPKG_ROOT%
    echo vcpkg를 먼저 설치해주세요:
    echo   git clone https://github.com/microsoft/vcpkg.git
    echo   cd vcpkg
    echo   bootstrap-vcpkg.bat
    exit /b 1
)

REM deps 디렉토리 생성
echo [1/4] 디렉토리 생성 중...
if exist "%DEPS_DIR%" (
    echo   기존 deps 디렉토리 삭제 중...
    rmdir /s /q "%DEPS_DIR%"
)
mkdir "%DEPS_DIR%"
mkdir "%DEPS_DIR%\include"
mkdir "%DEPS_DIR%\lib"
mkdir "%DEPS_DIR%\bin"
mkdir "%DEPS_DIR%\share"

REM vcpkg 설치 확인 및 설치
echo.
echo [2/4] vcpkg 패키지 설치 확인 중...

set PACKAGES=hdf5[cpp] yaml-cpp blosc gtest

for %%p in (%PACKAGES%) do (
    echo   %%p 확인 중...
    "%VCPKG_ROOT%\vcpkg.exe" list | findstr /i "%%p:%TRIPLET%" >nul
    if errorlevel 1 (
        echo   %%p 설치 중...
        "%VCPKG_ROOT%\vcpkg.exe" install %%p:%TRIPLET%
    ) else (
        echo   %%p 이미 설치됨
    )
)

REM 설치된 패키지 경로
set INSTALLED_DIR=%VCPKG_ROOT%\installed\%TRIPLET%

REM 파일 복사
echo.
echo [3/4] 파일 복사 중...

REM include 복사
echo   include 파일 복사 중...
xcopy /e /i /q /y "%INSTALLED_DIR%\include\*" "%DEPS_DIR%\include\" >nul

REM lib 복사
echo   lib 파일 복사 중...
xcopy /e /i /q /y "%INSTALLED_DIR%\lib\*" "%DEPS_DIR%\lib\" >nul

REM bin 복사 (DLL)
echo   bin 파일 복사 중...
if exist "%INSTALLED_DIR%\bin" (
    xcopy /e /i /q /y "%INSTALLED_DIR%\bin\*" "%DEPS_DIR%\bin\" >nul
)

REM debug 복사 (선택적)
if exist "%INSTALLED_DIR%\debug" (
    echo   debug 파일 복사 중...
    mkdir "%DEPS_DIR%\debug" 2>nul
    mkdir "%DEPS_DIR%\debug\lib" 2>nul
    mkdir "%DEPS_DIR%\debug\bin" 2>nul
    xcopy /e /i /q /y "%INSTALLED_DIR%\debug\lib\*" "%DEPS_DIR%\debug\lib\" >nul
    if exist "%INSTALLED_DIR%\debug\bin" (
        xcopy /e /i /q /y "%INSTALLED_DIR%\debug\bin\*" "%DEPS_DIR%\debug\bin\" >nul
    )
)

REM share 복사 (CMake 설정 등)
echo   share 파일 복사 중...
xcopy /e /i /q /y "%INSTALLED_DIR%\share\*" "%DEPS_DIR%\share\" >nul

REM 버전 정보 저장
echo.
echo [4/4] 버전 정보 저장 중...

echo # KooD3plotReader Local Dependencies > "%DEPS_DIR%\VERSION.txt"
echo # Generated: %date% %time% >> "%DEPS_DIR%\VERSION.txt"
echo # Triplet: %TRIPLET% >> "%DEPS_DIR%\VERSION.txt"
echo. >> "%DEPS_DIR%\VERSION.txt"
echo ## Installed Packages: >> "%DEPS_DIR%\VERSION.txt"
"%VCPKG_ROOT%\vcpkg.exe" list | findstr "%TRIPLET%" >> "%DEPS_DIR%\VERSION.txt"

REM 사용법 파일 생성
echo # Local Dependencies Usage > "%DEPS_DIR%\README.md"
echo. >> "%DEPS_DIR%\README.md"
echo This directory contains pre-built dependencies for KooD3plotReader. >> "%DEPS_DIR%\README.md"
echo. >> "%DEPS_DIR%\README.md"
echo ## Usage >> "%DEPS_DIR%\README.md"
echo. >> "%DEPS_DIR%\README.md"
echo ```bash >> "%DEPS_DIR%\README.md"
echo # CMake will automatically find these dependencies >> "%DEPS_DIR%\README.md"
echo cmake .. -DKOOD3PLOT_USE_LOCAL_DEPS=ON >> "%DEPS_DIR%\README.md"
echo ``` >> "%DEPS_DIR%\README.md"
echo. >> "%DEPS_DIR%\README.md"
echo ## Regenerate >> "%DEPS_DIR%\README.md"
echo. >> "%DEPS_DIR%\README.md"
echo ```bash >> "%DEPS_DIR%\README.md"
echo scripts\copy_dependencies.bat [vcpkg_root] [triplet] >> "%DEPS_DIR%\README.md"
echo ``` >> "%DEPS_DIR%\README.md"

echo.
echo ========================================
echo  완료!
echo ========================================
echo.
echo 로컬 의존성이 다음 위치에 복사되었습니다:
echo   %DEPS_DIR%
echo.
echo 사용 방법:
echo   cmake .. -DKOOD3PLOT_USE_LOCAL_DEPS=ON
echo.
echo 또는 프로젝트를 다른 PC로 복사하면 자동으로 deps/ 폴더가 사용됩니다.
echo.

endlocal
