@echo off
setlocal enabledelayedexpansion

REM =========================================
REM  KooD3plotReader Windows Build Script
REM  Visual Studio Compiler (MSVC)
REM =========================================

echo =========================================
echo  KooD3plotReader Build and Packaging
echo =========================================
echo.

REM Color codes for Windows (limited support)
set "STEP_PREFIX=[Step]"

REM =========================================
REM Project paths
REM =========================================
set "PROJECT_ROOT=%~dp0"
set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"
set "BUILD_DIR=%PROJECT_ROOT%\build"
set "INSTALL_DIR=%PROJECT_ROOT%\installed"
set "ARCH=x64"

REM =========================================
REM [1/7] Find Visual Studio
REM =========================================
echo %STEP_PREFIX% [1/7] Finding Visual Studio installation...

set "VCVARSALL="

REM Check VS 2022 Community
if exist "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvarsall.bat" (
    set "VCVARSALL=C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvarsall.bat"
    set "VS_VERSION=2022 Community"
    goto :vs_found
)

REM Check VS 2022 Professional
if exist "C:\Program Files\Microsoft Visual Studio\2022\Professional\VC\Auxiliary\Build\vcvarsall.bat" (
    set "VCVARSALL=C:\Program Files\Microsoft Visual Studio\2022\Professional\VC\Auxiliary\Build\vcvarsall.bat"
    set "VS_VERSION=2022 Professional"
    goto :vs_found
)

REM Check VS 2022 Enterprise
if exist "C:\Program Files\Microsoft Visual Studio\2022\Enterprise\VC\Auxiliary\Build\vcvarsall.bat" (
    set "VCVARSALL=C:\Program Files\Microsoft Visual Studio\2022\Enterprise\VC\Auxiliary\Build\vcvarsall.bat"
    set "VS_VERSION=2022 Enterprise"
    goto :vs_found
)

REM Check VS 2019 Community
if exist "C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\VC\Auxiliary\Build\vcvarsall.bat" (
    set "VCVARSALL=C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\VC\Auxiliary\Build\vcvarsall.bat"
    set "VS_VERSION=2019 Community"
    goto :vs_found
)

REM Check VS 2019 Professional
if exist "C:\Program Files (x86)\Microsoft Visual Studio\2019\Professional\VC\Auxiliary\Build\vcvarsall.bat" (
    set "VCVARSALL=C:\Program Files (x86)\Microsoft Visual Studio\2019\Professional\VC\Auxiliary\Build\vcvarsall.bat"
    set "VS_VERSION=2019 Professional"
    goto :vs_found
)

REM Check VS 2019 Enterprise
if exist "C:\Program Files (x86)\Microsoft Visual Studio\2019\Enterprise\VC\Auxiliary\Build\vcvarsall.bat" (
    set "VCVARSALL=C:\Program Files (x86)\Microsoft Visual Studio\2019\Enterprise\VC\Auxiliary\Build\vcvarsall.bat"
    set "VS_VERSION=2019 Enterprise"
    goto :vs_found
)

REM Check VS 2019 BuildTools
if exist "C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\VC\Auxiliary\Build\vcvarsall.bat" (
    set "VCVARSALL=C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\VC\Auxiliary\Build\vcvarsall.bat"
    set "VS_VERSION=2019 BuildTools"
    goto :vs_found
)

REM Check VS 2017 WDExpress
if exist "C:\Program Files (x86)\Microsoft Visual Studio\2017\WDExpress\VC\Auxiliary\Build\vcvarsall.bat" (
    set "VCVARSALL=C:\Program Files (x86)\Microsoft Visual Studio\2017\WDExpress\VC\Auxiliary\Build\vcvarsall.bat"
    set "VS_VERSION=2017 WDExpress"
    goto :vs_found
)

REM VS not found
echo [ERROR] Visual Studio 2017, 2019, or 2022 not found!
echo Please install Visual Studio with C++ development tools.
exit /b 1

:vs_found
echo   Found: Visual Studio %VS_VERSION%
echo   Setting up %ARCH% environment...
call "%VCVARSALL%" %ARCH% >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Failed to set up Visual Studio environment
    exit /b 1
)
echo   Environment configured successfully.
echo.

REM =========================================
REM [2/7] Clean previous build
REM =========================================
echo %STEP_PREFIX% [2/7] Cleaning previous build...
if exist "%BUILD_DIR%" (
    rmdir /s /q "%BUILD_DIR%"
)
if exist "%INSTALL_DIR%" (
    rmdir /s /q "%INSTALL_DIR%"
)
echo   Previous build cleaned.
echo.

REM =========================================
REM [3/7] Create build directory
REM =========================================
echo %STEP_PREFIX% [3/7] Creating build directory...
mkdir "%BUILD_DIR%"
cd /d "%BUILD_DIR%"
echo   Build directory created: %BUILD_DIR%
echo.

REM =========================================
REM [4/7] CMake configuration (Static library)
REM =========================================
echo %STEP_PREFIX% [4/7] CMake configuration (Static library)...

cmake -G "NMake Makefiles" ^
      -DCMAKE_BUILD_TYPE=Release ^
      -DBUILD_SHARED_LIBS=OFF ^
      -DCMAKE_INSTALL_PREFIX="%INSTALL_DIR%\library" ^
      -DKOOD3PLOT_BUILD_TESTS=OFF ^
      -DKOOD3PLOT_BUILD_EXAMPLES=ON ^
      -DCMAKE_CXX_FLAGS="/utf-8" ^
      "%PROJECT_ROOT%"

if errorlevel 1 (
    echo [ERROR] CMake configuration failed
    exit /b 1
)
echo   CMake configuration completed.
echo.

REM =========================================
REM [5/7] Build Static library
REM =========================================
echo %STEP_PREFIX% [5/7] Building Static library...
nmake
if errorlevel 1 (
    echo [ERROR] Build failed
    exit /b 1
)
echo   Static library build completed.
echo.

echo %STEP_PREFIX% [5/7] Installing Static library...
nmake install
if errorlevel 1 (
    echo [ERROR] Install failed
    exit /b 1
)
echo   Static library installed.
echo.

REM =========================================
REM [5.5/7] Build Shared library
REM =========================================
echo %STEP_PREFIX% [5.5/7] CMake reconfiguration (Shared library)...

cmake -G "NMake Makefiles" ^
      -DCMAKE_BUILD_TYPE=Release ^
      -DBUILD_SHARED_LIBS=ON ^
      -DCMAKE_INSTALL_PREFIX="%INSTALL_DIR%\library" ^
      -DKOOD3PLOT_BUILD_TESTS=OFF ^
      -DKOOD3PLOT_BUILD_EXAMPLES=ON ^
      -DCMAKE_CXX_FLAGS="/utf-8" ^
      "%PROJECT_ROOT%"

if errorlevel 1 (
    echo [ERROR] CMake configuration failed
    exit /b 1
)

echo   Building Shared library...
nmake
if errorlevel 1 (
    echo [ERROR] Shared library build failed
    exit /b 1
)

nmake install
if errorlevel 1 (
    echo [ERROR] Shared library install failed
    exit /b 1
)
echo   Shared library build completed.
echo.

REM =========================================
REM Copy CLI tool and config files
REM =========================================
echo   Copying CLI tool...
if not exist "%INSTALL_DIR%\bin" mkdir "%INSTALL_DIR%\bin"

if exist "%BUILD_DIR%\kood3plot_cli.exe" (
    copy "%BUILD_DIR%\kood3plot_cli.exe" "%INSTALL_DIR%\bin\" >nul
    echo   [OK] kood3plot_cli.exe copied
) else (
    echo   [WARN] kood3plot_cli.exe not built
)

REM Copy CLI config examples
echo   Copying CLI config examples...
if not exist "%INSTALL_DIR%\bin\config" mkdir "%INSTALL_DIR%\bin\config"
if exist "%PROJECT_ROOT%\config\cli_examples" (
    xcopy /s /e /q /y "%PROJECT_ROOT%\config\cli_examples\*" "%INSTALL_DIR%\bin\config\" >nul
    echo   [OK] CLI config examples copied
) else (
    echo   [WARN] CLI config examples not found
)
echo.

REM =========================================
REM [6/7] Create source package
REM =========================================
echo %STEP_PREFIX% [6/7] Creating source package...
cd /d "%PROJECT_ROOT%"

REM Create source package directory
if not exist "%INSTALL_DIR%\source\kood3plot" mkdir "%INSTALL_DIR%\source\kood3plot"

REM Copy include folder
echo   Copying include folder...
xcopy /s /e /q /y "%PROJECT_ROOT%\include" "%INSTALL_DIR%\source\kood3plot\include\" >nul

REM Copy src folder
echo   Copying src folder...
xcopy /s /e /q /y "%PROJECT_ROOT%\src" "%INSTALL_DIR%\source\kood3plot\src\" >nul

REM Copy examples folder
echo   Copying examples folder...
if exist "%PROJECT_ROOT%\examples" (
    xcopy /s /e /q /y "%PROJECT_ROOT%\examples" "%INSTALL_DIR%\source\examples\" >nul
    xcopy /s /e /q /y "%PROJECT_ROOT%\examples" "%INSTALL_DIR%\library\examples\" >nul
)
echo   Source package created.
echo.

REM =========================================
REM [7/7] Copy documentation
REM =========================================
echo %STEP_PREFIX% [7/7] Copying documentation...

REM Create docs folder
if not exist "%INSTALL_DIR%\docs" mkdir "%INSTALL_DIR%\docs"

REM Copy to root
if exist "%PROJECT_ROOT%\README.md" copy "%PROJECT_ROOT%\README.md" "%INSTALL_DIR%\" >nul
if exist "%PROJECT_ROOT%\USAGE.md" copy "%PROJECT_ROOT%\USAGE.md" "%INSTALL_DIR%\" >nul
if exist "%PROJECT_ROOT%\LICENSE" copy "%PROJECT_ROOT%\LICENSE" "%INSTALL_DIR%\" >nul
if exist "%PROJECT_ROOT%\PROGRESS.md" copy "%PROJECT_ROOT%\PROGRESS.md" "%INSTALL_DIR%\" >nul

REM Copy to docs
if exist "%PROJECT_ROOT%\USAGE.md" copy "%PROJECT_ROOT%\USAGE.md" "%INSTALL_DIR%\docs\" >nul
if exist "%PROJECT_ROOT%\README.md" copy "%PROJECT_ROOT%\README.md" "%INSTALL_DIR%\docs\" >nul
if exist "%PROJECT_ROOT%\KOOD3PLOT_CLI_*.md" copy "%PROJECT_ROOT%\KOOD3PLOT_CLI_*.md" "%INSTALL_DIR%\docs\" >nul 2>&1

echo   Documentation copied.
echo.

REM =========================================
REM Create CMakeLists.txt example (source)
REM =========================================
echo   Creating example files...

(
echo # KooD3plotReader source inclusion example
echo cmake_minimum_required(VERSION 3.15^)
echo project(MyD3plotApp^)
echo.
echo set(CMAKE_CXX_STANDARD 17^)
echo set(CMAKE_CXX_STANDARD_REQUIRED ON^)
echo.
echo # kood3plot source files
echo file(GLOB_RECURSE KOOD3PLOT_SOURCES
echo     kood3plot/src/*.cpp
echo ^)
echo.
echo # Executable
echo add_executable(my_app main.cpp ${KOOD3PLOT_SOURCES}^)
echo.
echo # Include paths
echo target_include_directories(my_app PRIVATE kood3plot/include^)
) > "%INSTALL_DIR%\source\CMakeLists.txt.example"

REM =========================================
REM Create main.cpp example
REM =========================================
(
echo #include ^<kood3plot/D3plotReader.hpp^>
echo #include ^<iostream^>
echo.
echo int main(int argc, char* argv[]^) {
echo     if (argc ^< 2^) {
echo         std::cerr ^<^< "Usage: " ^<^< argv[0] ^<^< " ^<d3plot_file^>\n";
echo         return 1;
echo     }
echo.
echo     kood3plot::D3plotReader reader(argv[1]^);
echo.
echo     if (reader.open(^) != kood3plot::ErrorCode::SUCCESS^) {
echo         std::cerr ^<^< "Failed to open file: " ^<^< argv[1] ^<^< "\n";
echo         return 1;
echo     }
echo.
echo     std::cout ^<^< "File opened successfully!\n";
echo.
echo     // Control data
echo     auto cd = reader.get_control_data(^);
echo     std::cout ^<^< "\n[Model Info]\n";
echo     std::cout ^<^< "  Nodes: " ^<^< cd.NUMNP ^<^< "\n";
echo     std::cout ^<^< "  Solid elements: " ^<^< std::abs(cd.NEL8^) ^<^< "\n";
echo.
echo     // Mesh
echo     auto mesh = reader.read_mesh(^);
echo     std::cout ^<^< "\n[Mesh]\n";
echo     std::cout ^<^< "  Actual nodes loaded: " ^<^< mesh.nodes.size(^) ^<^< "\n";
echo     std::cout ^<^< "  Actual elements loaded: " ^<^< mesh.solids.size(^) ^<^< "\n";
echo.
echo     // States
echo     auto states = reader.read_all_states(^);
echo     std::cout ^<^< "\n[Time States]\n";
echo     std::cout ^<^< "  Total states: " ^<^< states.size(^) ^<^< "\n";
echo.
echo     if (!states.empty(^)^) {
echo         std::cout ^<^< "  First time: " ^<^< states.front(^).time ^<^< "\n";
echo         std::cout ^<^< "  Last time: " ^<^< states.back(^).time ^<^< "\n";
echo     }
echo.
echo     reader.close(^);
echo     std::cout ^<^< "\nSuccess!\n";
echo.
echo     return 0;
echo }
) > "%INSTALL_DIR%\source\main.cpp.example"

REM Copy to library folder too
copy "%INSTALL_DIR%\source\main.cpp.example" "%INSTALL_DIR%\library\" >nul

REM =========================================
REM Create CMakeLists.txt example (library)
REM =========================================
(
echo # KooD3plotReader library usage example
echo cmake_minimum_required(VERSION 3.15^)
echo project(MyD3plotApp^)
echo.
echo set(CMAKE_CXX_STANDARD 17^)
echo set(CMAKE_CXX_STANDARD_REQUIRED ON^)
echo.
echo # kood3plot installation path
echo set(KooD3plot_DIR "${CMAKE_CURRENT_SOURCE_DIR}"^)
echo.
echo # Static library usage
echo add_executable(my_app_static main.cpp^)
echo target_include_directories(my_app_static PRIVATE include^)
echo target_link_libraries(my_app_static PRIVATE
echo     ${CMAKE_CURRENT_SOURCE_DIR}/lib/kood3plot.lib
echo ^)
echo.
echo # Shared library usage
echo add_executable(my_app_shared main.cpp^)
echo target_include_directories(my_app_shared PRIVATE include^)
echo target_link_libraries(my_app_shared PRIVATE
echo     ${CMAKE_CURRENT_SOURCE_DIR}/lib/kood3plot.lib
echo ^)
) > "%INSTALL_DIR%\library\CMakeLists.txt.example"

echo   Example files created.
echo.

REM =========================================
REM Create README for installed package
REM =========================================
(
echo # KooD3plotReader Installation Package
echo.
echo This package supports two usage methods:
echo.
echo ## Method 1: Compiled Library (library/^)
echo.
echo The `library/` folder contains pre-built libraries:
echo.
echo ```
echo library/
echo   +-- lib/
echo   ^|   +-- kood3plot.lib      (Static library^)
echo   ^|   +-- kood3plot.dll      (Shared library^)
echo   +-- include/
echo   ^|   +-- kood3plot/         (Header files^)
echo   +-- examples/              (Example programs^)
echo   +-- CMakeLists.txt.example
echo   +-- main.cpp.example
echo ```
echo.
echo ### Usage:
echo.
echo ```batch
echo cd library
echo copy main.cpp.example main.cpp
echo copy CMakeLists.txt.example CMakeLists.txt
echo mkdir build ^&^& cd build
echo cmake ..
echo cmake --build . --config Release
echo my_app_static.exe ..\path\to\d3plot
echo ```
echo.
echo ## Method 2: Source Code (source/^)
echo.
echo The `source/` folder contains the full source code:
echo.
echo ```
echo source/
echo   +-- kood3plot/
echo   ^|   +-- include/          (Header files^)
echo   ^|   +-- src/              (Source files^)
echo   +-- examples/             (Example programs^)
echo   +-- CMakeLists.txt.example
echo   +-- main.cpp.example
echo ```
echo.
echo ### Usage:
echo.
echo ```batch
echo cd source
echo copy main.cpp.example main.cpp
echo copy CMakeLists.txt.example CMakeLists.txt
echo mkdir build ^&^& cd build
echo cmake ..
echo cmake --build . --config Release
echo my_app.exe ..\path\to\d3plot
echo ```
echo.
echo ## Direct Compilation (without CMake^)
echo.
echo ```batch
echo cl /EHsc /std:c++17 /O2 /I library\include main.cpp library\lib\kood3plot.lib /Fe:my_app.exe
echo ```
echo.
echo ## CLI Tool
echo.
echo ```batch
echo bin\kood3plot_cli.exe --help
echo bin\kood3plot_cli.exe --mode query --d3plot path\to\d3plot
echo ```
echo.
echo For detailed usage and API documentation, see `docs/USAGE.md`.
) > "%INSTALL_DIR%\README_WINDOWS.md"

REM =========================================
REM Done!
REM =========================================
echo.
echo =========================================
echo  Build and Packaging Complete!
echo =========================================
echo.
echo Installation location: %INSTALL_DIR%
echo.
echo Available packages:
echo   1. %INSTALL_DIR%\library\  - Compiled libraries
echo      - kood3plot.lib (static^)
echo      - kood3plot.dll (shared^)
echo.
echo   2. %INSTALL_DIR%\source\   - Source code
echo.
echo CLI Tool:
echo   %INSTALL_DIR%\bin\kood3plot_cli.exe
echo   Usage: kood3plot_cli.exe --mode ^<query^|render^|batch^|autosection^|multirun^|export^> ...
echo.
echo   3. %INSTALL_DIR%\bin\config\ - CLI config examples
echo      - query_basic.yaml      (데이터 추출)
echo      - render_basic.yaml     (렌더링)
echo      - batch_render.yaml     (배치 렌더링)
echo      - multisection.yaml     (다중 단면)
echo      - autosection.yaml      (자동 단면)
echo      - multirun_*.yaml       (다중 실행 비교)
echo      - export_*.yaml         (LS-DYNA 내보내기)
echo.
echo Quick Start:
echo   kood3plot_cli.exe --help
echo   kood3plot_cli.exe --mode query --config bin\config\query_basic.yaml
echo.
echo For detailed usage:
echo   type %INSTALL_DIR%\README_WINDOWS.md
echo   type %INSTALL_DIR%\docs\USAGE.md
echo   type %INSTALL_DIR%\bin\config\README.md
echo.

endlocal
exit /b 0
