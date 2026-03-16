@echo off
setlocal enabledelayedexpansion

REM ============================================================
REM  KooD3plot Unified Installer (Windows)
REM ============================================================
REM  Builds C++ unified_analyzer + Python koo_deep_report into
REM  a single, self-contained install directory.
REM
REM  Usage:
REM    install.bat                          Full build + install
REM    install.bat --prefix=C:\koo          Custom install path
REM    install.bat --update                 Rebuild changed files only
REM    install.bat --clean                  Clean + full rebuild
REM    install.bat --python-only            Skip C++ build
REM    install.bat --cpp-only               Skip Python packaging
REM
REM  After install:
REM    dist\activate.bat                    Set up PATH
REM    koo_deep_report <d3plot_path>        Run single analysis
REM    koo_deep_report batch <dir>          Run batch analysis
REM ============================================================

set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
set "PREFIX=%SCRIPT_DIR%\dist"
set "BUILD_DIR=%SCRIPT_DIR%\build"
set "BUILD_TYPE=Release"
set "CLEAN=0"
set "UPDATE=0"
set "CPP_BUILD=1"
set "PY_BUILD=1"
set "ARCH=x64"

REM ============================================================
REM Parse arguments
REM ============================================================
:parse_args
if "%~1"=="" goto :done_args
set "ARG=%~1"

if "%ARG:~0,9%"=="--prefix=" (
    set "PREFIX=%ARG:~9%"
    shift & goto :parse_args
)
if "%ARG%"=="--clean"       ( set "CLEAN=1"    & shift & goto :parse_args )
if "%ARG%"=="--update"      ( set "UPDATE=1"   & shift & goto :parse_args )
if "%ARG%"=="--python-only" ( set "CPP_BUILD=0" & shift & goto :parse_args )
if "%ARG%"=="--cpp-only"    ( set "PY_BUILD=0"  & shift & goto :parse_args )
if "%ARG%"=="--help" goto :show_help
if "%ARG%"=="-h"     goto :show_help

echo Unknown option: %ARG%
exit /b 1

:done_args

echo.
echo ============================================================
echo  KooD3plot Unified Installer (Windows)
echo ============================================================
echo.
echo   Source:    %SCRIPT_DIR%
echo   Install:  %PREFIX%
echo   Build:    %BUILD_TYPE%
echo   C++ build: %CPP_BUILD%
echo   Python:   %PY_BUILD%
echo.

REM ============================================================
REM [1] Find Visual Studio
REM ============================================================
echo [1/6] Finding Visual Studio...

set "VCVARSALL="
set "VS_VERSION="

for %%E in (Community Professional Enterprise BuildTools) do (
    if exist "C:\Program Files\Microsoft Visual Studio\2022\%%E\VC\Auxiliary\Build\vcvarsall.bat" (
        set "VCVARSALL=C:\Program Files\Microsoft Visual Studio\2022\%%E\VC\Auxiliary\Build\vcvarsall.bat"
        set "VS_VERSION=2022 %%E"
        goto :vs_found
    )
)
for %%E in (Community Professional Enterprise BuildTools) do (
    if exist "C:\Program Files (x86)\Microsoft Visual Studio\2019\%%E\VC\Auxiliary\Build\vcvarsall.bat" (
        set "VCVARSALL=C:\Program Files (x86)\Microsoft Visual Studio\2019\%%E\VC\Auxiliary\Build\vcvarsall.bat"
        set "VS_VERSION=2019 %%E"
        goto :vs_found
    )
)

echo   [ERROR] Visual Studio 2019/2022 not found!
echo   Please install Visual Studio with "Desktop development with C++" workload.
exit /b 1

:vs_found
echo   Found: Visual Studio %VS_VERSION%
call "%VCVARSALL%" %ARCH% >nul 2>&1
if errorlevel 1 (
    echo   [ERROR] Failed to set up VS environment
    exit /b 1
)
echo   Environment configured.
echo.

REM ============================================================
REM [2] Check prerequisites
REM ============================================================
echo [2/6] Checking prerequisites...

where cmake >nul 2>&1
if errorlevel 1 (
    echo   [ERROR] CMake not found. Install from https://cmake.org
    exit /b 1
)
for /f "tokens=3" %%v in ('cmake --version 2^>nul ^| findstr /c:"cmake version"') do echo   CMake %%v

where python >nul 2>&1
if errorlevel 1 (
    echo   [WARN] Python not found - skipping Python packaging
    set "PY_BUILD=0"
) else (
    for /f "tokens=2" %%v in ('python --version 2^>^&1') do echo   Python %%v
)

where ffmpeg >nul 2>&1
if errorlevel 1 (
    echo   [WARN] ffmpeg not found - MP4 encoding will fail at runtime
) else (
    echo   ffmpeg found
)
echo.

REM ============================================================
REM [3] Clean if requested
REM ============================================================
if "%CLEAN%"=="1" (
    echo [3/6] Cleaning...
    if exist "%BUILD_DIR%" rmdir /s /q "%BUILD_DIR%"
    if exist "%PREFIX%" rmdir /s /q "%PREFIX%"
    echo   Cleaned.
    echo.
) else (
    echo [3/6] Clean skipped.
    echo.
)

REM ============================================================
REM [4] C++ Build
REM ============================================================
if "%CPP_BUILD%"=="0" goto :skip_cpp

echo [4/6] Building C++...
if not exist "%BUILD_DIR%" mkdir "%BUILD_DIR%"

REM Configure
cmake -B "%BUILD_DIR%" -S "%SCRIPT_DIR%" ^
    -G "NMake Makefiles" ^
    -DCMAKE_BUILD_TYPE=%BUILD_TYPE% ^
    -DCMAKE_INSTALL_PREFIX="%PREFIX%" ^
    -DKOOD3PLOT_BUILD_TESTS=OFF ^
    -DKOOD3PLOT_BUILD_EXAMPLES=ON ^
    -DKOOD3PLOT_BUILD_V4_RENDER=ON ^
    -DKOOD3PLOT_BUILD_SECTION_RENDER=ON ^
    -DKOOD3PLOT_BUILD_CAPI=OFF ^
    -DKOOD3PLOT_ENABLE_OPENMP=ON ^
    -DCMAKE_CXX_FLAGS="/utf-8" > "%BUILD_DIR%\cmake_config.log" 2>&1

if errorlevel 1 (
    echo   [ERROR] CMake configuration failed. See %BUILD_DIR%\cmake_config.log
    exit /b 1
)
echo   CMake configured.

REM Build unified_analyzer only
cd /d "%BUILD_DIR%"
nmake unified_analyzer
if errorlevel 1 (
    echo   [ERROR] Build failed
    exit /b 1
)
echo   unified_analyzer.exe built.

REM Install binary
if not exist "%PREFIX%\bin" mkdir "%PREFIX%\bin"
copy /y "%BUILD_DIR%\examples\unified_analyzer.exe" "%PREFIX%\bin\" >nul
echo   Installed: %PREFIX%\bin\unified_analyzer.exe
cd /d "%SCRIPT_DIR%"
echo.
goto :done_cpp

:skip_cpp
echo [4/6] C++ build skipped.
echo.
:done_cpp

REM ============================================================
REM [5] Python packaging
REM ============================================================
if "%PY_BUILD%"=="0" goto :skip_py

echo [5/6] Installing Python package...

set "PY_SRC=%SCRIPT_DIR%\python\koo_deep_report"
set "PY_DEST=%PREFIX%\python\koo_deep_report"

if not exist "%PY_DEST%" mkdir "%PY_DEST%"
xcopy /s /e /q /y "%PY_SRC%\koo_deep_report" "%PY_DEST%\koo_deep_report\" >nul
if exist "%PY_SRC%\pyproject.toml" copy /y "%PY_SRC%\pyproject.toml" "%PY_DEST%\" >nul

REM Create wrapper batch file
(
echo @echo off
echo setlocal
echo set "INSTALL_DIR=%%~dp0.."
echo set "PYTHONPATH=%%INSTALL_DIR%%\python\koo_deep_report;%%PYTHONPATH%%"
echo set "PATH=%%INSTALL_DIR%%\bin;%%PATH%%"
echo python -m koo_deep_report %%*
echo endlocal
) > "%PREFIX%\bin\koo_deep_report.bat"

echo   Python package installed.
echo   Wrapper: %PREFIX%\bin\koo_deep_report.bat

REM ── PyInstaller exe builds ──
echo.
echo   Building standalone executables (PyInstaller)...

pip install --quiet pyinstaller 2>nul
if errorlevel 1 pip install --quiet --user pyinstaller 2>nul

where pyinstaller >nul 2>&1
if errorlevel 1 (
    echo   [WARN] pyinstaller not found - skipping exe builds
    goto :done_exe
)

cd /d "%PY_SRC%"

REM CLI exe (lightweight, no GUI)
echo   Building koo_deep_report CLI exe...
pyinstaller --noconfirm --distpath "%PREFIX%\bin" koo_deep_report_cli.spec > "%BUILD_DIR%\pyinstaller_cli.log" 2>&1
if errorlevel 1 (
    echo   [WARN] CLI exe build failed. See %BUILD_DIR%\pyinstaller_cli.log
) else (
    echo   koo_deep_report.exe built.
)

REM GUI exe (with customtkinter)
python -c "import customtkinter" 2>nul
if errorlevel 1 (
    echo   [WARN] customtkinter not installed - skipping GUI exe
    echo   Install with: pip install customtkinter
) else (
    echo   Building koo_deep_report_gui exe...
    pyinstaller --noconfirm --distpath "%PREFIX%\bin" koo_deep_report.spec > "%BUILD_DIR%\pyinstaller_gui.log" 2>&1
    if errorlevel 1 (
        echo   [WARN] GUI exe build failed. See %BUILD_DIR%\pyinstaller_gui.log
    ) else (
        echo   koo_deep_report_gui.exe built.
    )
)

REM Clean PyInstaller temp
if exist "%PY_SRC%\build" rmdir /s /q "%PY_SRC%\build"

:done_exe
cd /d "%SCRIPT_DIR%"
echo.
goto :done_py

:skip_py
echo [5/6] Python packaging skipped.
echo.
:done_py

REM ============================================================
REM [6] Create helper scripts
REM ============================================================
echo [6/6] Creating helper scripts...

REM Activation script
(
echo @echo off
echo REM Source this to set up KooD3plot environment
echo set "KOOD3PLOT_HOME=%PREFIX%"
echo set "PATH=%PREFIX%\bin;%%PATH%%"
echo set "PYTHONPATH=%PREFIX%\python\koo_deep_report;%%PYTHONPATH%%"
echo echo KooD3plot environment activated.
echo echo   KOOD3PLOT_HOME=%PREFIX%
) > "%PREFIX%\activate.bat"

REM Update script
(
echo @echo off
echo echo Updating KooD3plot...
echo cd /d "%SCRIPT_DIR%"
echo git pull --ff-only 2^>nul ^|^| echo (git pull skipped^)
echo call install.bat --prefix="%PREFIX%" --update
) > "%PREFIX%\update.bat"

REM Version info
echo build_date: %date% %time% > "%PREFIX%\version.txt"
echo build_type: %BUILD_TYPE% >> "%PREFIX%\version.txt"
echo platform: Windows-%PROCESSOR_ARCHITECTURE% >> "%PREFIX%\version.txt"

echo   activate.bat created.
echo   update.bat created.
echo.

REM ============================================================
REM Done
REM ============================================================
echo ============================================================
echo  Installation Complete!
echo ============================================================
echo.
echo   Install directory: %PREFIX%
echo.
if exist "%PREFIX%\bin\unified_analyzer.exe" (
    echo   C++ binary:
    echo     %PREFIX%\bin\unified_analyzer.exe
    echo.
)
if exist "%PREFIX%\bin\koo_deep_report.bat" (
    echo   Python CLI (wrapper^):
    echo     %PREFIX%\bin\koo_deep_report.bat
    echo.
)
if exist "%PREFIX%\bin\koo_deep_report.exe" (
    echo   Standalone CLI exe:
    echo     %PREFIX%\bin\koo_deep_report.exe
    echo.
)
if exist "%PREFIX%\bin\koo_deep_report_gui.exe" (
    echo   GUI exe:
    echo     %PREFIX%\bin\koo_deep_report_gui.exe
    echo.
)
echo   Quick start:
echo     %PREFIX%\activate.bat
echo     koo_deep_report ^<d3plot_path^>
echo     koo_deep_report batch ^<directory^>
echo.
echo   Update:
echo     %PREFIX%\update.bat
echo.

endlocal
exit /b 0

:show_help
echo.
echo KooD3plot Unified Installer (Windows)
echo.
echo Usage:
echo   install.bat                          Full build + install
echo   install.bat --prefix=C:\koo          Custom install path
echo   install.bat --update                 Rebuild changed files only
echo   install.bat --clean                  Clean + full rebuild
echo   install.bat --python-only            Skip C++ build
echo   install.bat --cpp-only               Skip Python packaging
echo.
exit /b 0
