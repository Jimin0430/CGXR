@echo off
REM ──────────────────────────────────────────────────────────────────────
REM uCO3D 소규모 서브셋 다운로드 + SfM 파이프라인 실행
REM
REM 사용법:
REM   run_uco3d.bat                    → 52개 서브셋 다운로드 + SfM
REM   run_uco3d.bat skip_download      → 다운로드 건너뛰고 SfM만
REM   run_uco3d.bat skip_sfm           → 다운로드만 (SfM 건너뜀)
REM ──────────────────────────────────────────────────────────────────────

setlocal

set DOWNLOAD_FOLDER=data\uco3d
set OUTPUT_FOLDER=data\uco3d_sfm
set FPS=2.0
set MAX_SEQUENCES=0

REM COLMAP 경로 (시스템 PATH에 있으면 비워도 됩니다)
set COLMAP_EXE=

REM ── 인수 처리 ──
set EXTRA_FLAGS=--small_subset

if "%1"=="skip_download" set EXTRA_FLAGS=%EXTRA_FLAGS% --skip_download
if "%1"=="skip_sfm"      set EXTRA_FLAGS=%EXTRA_FLAGS% --skip_sfm

REM COLMAP 경로 설정
set COLMAP_OPT=
if not "%COLMAP_EXE%"=="" set COLMAP_OPT=--colmap_executable "%COLMAP_EXE%"

REM ── 실행 ──
python prepare_uco3d.py ^
    --download_folder "%DOWNLOAD_FOLDER%" ^
    --output_folder "%OUTPUT_FOLDER%" ^
    --fps %FPS% ^
    %EXTRA_FLAGS% ^
    %COLMAP_OPT%

echo.
echo 완료!
pause
