@echo off
REM ============================================================
REM LSPrePost Windows 자동 다운로드 스크립트
REM
REM 사용법:
REM   download_lsprepost.bat [설치 디렉토리]
REM
REM 예시:
REM   download_lsprepost.bat                     (기본: .\lsprepost)
REM   download_lsprepost.bat C:\lsprepost
REM ============================================================

setlocal enabledelayedexpansion

set VERSION=4.12.11
set DATE=17Dec2025
set FILENAME=LS-PrePost-2025R1[%VERSION%]-x64-%DATE%_setup.exe
set URL=https://ftp.lstc.com/anonymous/outgoing/lsprepost/4.12/win64/%FILENAME%

set INSTALL_DIR=%1
if "%INSTALL_DIR%"=="" set INSTALL_DIR=%~dp0..\lsprepost

echo.
echo ========================================
echo  LSPrePost %VERSION% Windows Downloader
echo ========================================
echo.
echo  URL: %URL%
echo  설치 디렉토리: %INSTALL_DIR%
echo.

REM 디렉토리 생성
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

REM 이미 설치되어 있는지 확인
if exist "%INSTALL_DIR%\lsprepost.exe" (
    echo [INFO] lsprepost.exe가 이미 존재합니다: %INSTALL_DIR%\lsprepost.exe
    echo [INFO] 재설치하려면 해당 디렉토리를 삭제 후 다시 실행하세요.
    goto :done
)

REM 다운로드
set SETUP_PATH=%INSTALL_DIR%\%FILENAME%
echo [1/2] 다운로드 중... (약 300MB)

where curl >nul 2>&1
if %errorlevel% equ 0 (
    curl -L -o "%SETUP_PATH%" "%URL%"
) else (
    powershell -Command "Invoke-WebRequest -Uri '%URL%' -OutFile '%SETUP_PATH%'"
)

if not exist "%SETUP_PATH%" (
    echo [오류] 다운로드 실패. URL을 확인하세요:
    echo   %URL%
    exit /b 1
)

echo.
echo [2/2] 다운로드 완료: %SETUP_PATH%
echo.
echo ========================================
echo  설치 방법:
echo    1. %SETUP_PATH% 를 실행하세요
echo    2. 설치 경로를 %INSTALL_DIR% 로 지정하세요
echo    3. 설치 후 lsprepost.exe 경로를 확인하세요
echo.
echo  또는 single_analyzer에서 자동 탐색:
echo    single_analyzer ... --lsprepost-path "%INSTALL_DIR%\lsprepost.exe"
echo ========================================

:done
echo.
endlocal
