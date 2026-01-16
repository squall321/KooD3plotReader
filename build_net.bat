@echo off
setlocal

echo Building kood3plot_net.dll...

REM Set up VS2019 BuildTools environment
call "C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\VC\Auxiliary\Build\vcvarsall.bat" x64
if errorlevel 1 (
    echo Failed to set up Visual Studio environment
    exit /b 1
)

REM Go to project directory
cd /d d:\KooD3plotReader

REM Clean and create build directory
if exist build rmdir /s /q build
mkdir build
cd build

REM Configure with CMake
cmake -G "NMake Makefiles" -DCMAKE_BUILD_TYPE=Release -DKOOD3PLOT_BUILD_TESTS=OFF -DKOOD3PLOT_BUILD_EXAMPLES=OFF ..
if errorlevel 1 (
    echo CMake configuration failed
    exit /b 1
)

REM Build only kood3plot_net target
nmake kood3plot_net
if errorlevel 1 (
    echo Build failed
    exit /b 1
)

echo.
echo Build complete!
echo DLL location: d:\KooD3plotReader\build\kood3plot_net.dll

dir kood3plot_net.* 2>nul

endlocal
