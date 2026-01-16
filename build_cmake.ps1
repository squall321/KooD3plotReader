# Build script for kood3plot_net.dll
$ErrorActionPreference = "Continue"

# Visual Studio 2019 BuildTools paths
$vsPath = "C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools"
$msvcVersion = "14.29.30133"
$msvcBin = "$vsPath\VC\Tools\MSVC\$msvcVersion\bin\Hostx64\x64"
$msvcInclude = "$vsPath\VC\Tools\MSVC\$msvcVersion\include"
$msvcLib = "$vsPath\VC\Tools\MSVC\$msvcVersion\lib\x64"

# Windows SDK
$sdkPath = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.19041.0"
$sdkBin = "$sdkPath\bin\$sdkVersion\x64"

# Set environment variables
$env:PATH = "$msvcBin;$sdkBin;$env:PATH"
$env:INCLUDE = "$msvcInclude;$sdkPath\Include\$sdkVersion\ucrt;$sdkPath\Include\$sdkVersion\shared;$sdkPath\Include\$sdkVersion\um;$sdkPath\Include\$sdkVersion\winrt"
$env:LIB = "$msvcLib;$sdkPath\Lib\$sdkVersion\ucrt\x64;$sdkPath\Lib\$sdkVersion\um\x64"

Write-Host "=== Build Environment ==="
Write-Host "MSVC: $msvcBin"
Write-Host "SDK:  $sdkBin"

Write-Host "`nChecking tools..."
$clOutput = & cl 2>&1
Write-Host "cl.exe: $($clOutput[0])"
$rcOutput = & rc 2>&1
Write-Host "rc.exe: OK"

# Build
Set-Location d:\KooD3plotReader
if (Test-Path build) { Remove-Item -Recurse -Force build }
New-Item -ItemType Directory -Path build | Out-Null
Set-Location build

Write-Host "`n=== Running CMake ==="
& cmake -G "NMake Makefiles" -DCMAKE_BUILD_TYPE=Release -DKOOD3PLOT_BUILD_TESTS=OFF -DKOOD3PLOT_BUILD_EXAMPLES=OFF .. 2>&1 | ForEach-Object { $_.ToString() }

Write-Host "`n=== Building kood3plot_net ==="
& nmake kood3plot_net 2>&1 | ForEach-Object { $_.ToString() }

Write-Host "`n=== Build Result ==="
$dll = Get-ChildItem kood3plot_net.dll -ErrorAction SilentlyContinue
if ($dll) {
    Write-Host "SUCCESS: $($dll.FullName)"
    Write-Host "Size: $([math]::Round($dll.Length / 1KB, 2)) KB"
} else {
    Write-Host "FAILED: DLL not found"
}
