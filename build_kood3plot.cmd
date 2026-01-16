@echo off
call "C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\VC\Auxiliary\Build\vcvarsall.bat" x64
cd /d d:\KooD3plotReader
if exist build rd /s /q build
mkdir build
cd build
cmake -G "NMake Makefiles" -DCMAKE_BUILD_TYPE=Release -DKOOD3PLOT_BUILD_TESTS=OFF -DKOOD3PLOT_BUILD_EXAMPLES=OFF ..
nmake kood3plot_net
dir kood3plot_net.* 2>nul
