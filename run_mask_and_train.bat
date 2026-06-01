@echo off
setlocal EnableDelayedExpansion

:: ── 경로 설정 ──────────────────────────────────────────────────────────────
SET SOURCE=D:\JM\cgxr\CGXR\data\my_video
SET OUTPUT=D:\JM\cgxr\CGXR\output_my_video_masked
SET SAM2_CKPT=D:\JM\cgxr\CGXR\sam2.1_hiera_large.pt
SET SAM2_CFG=configs/sam2.1/sam2.1_hiera_l.yaml
SET SAM2_PY=D:\JM\cgxr\CGXR\sam2_env\Scripts\python.exe
SET SAM2_SCRIPT=D:\JM\cgxr\CGXR\Extract_SfM\remove_background_sam2.py

SET GS_ENV=C:\Users\USER\anaconda3\envs\mobile-gs
SET "PATH=%GS_ENV%;%GS_ENV%\Library\mingw-w64\bin;%GS_ENV%\Library\usr\bin;%GS_ENV%\Library\bin;%GS_ENV%\Scripts;C:\Users\USER\anaconda3\Scripts;%PATH%"
SET MOBILE_GS_DIR=D:\JM\cgxr\CGXR\mobile_gs

:: ── Step 1: SAM 2 배경 제거 ──────────────────────────────────────────────
echo.
echo [STEP 1] SAM 2 배경 제거 시작...
echo   Source  : %SOURCE%\images\
echo   Checkpoint: %SAM2_CKPT%
echo   Mode    : video  (프레임 시퀀스 → 시간적 일관성)
echo.

"%SAM2_PY%" "%SAM2_SCRIPT%" ^
  --source_path "%SOURCE%" ^
  --checkpoint "%SAM2_CKPT%" ^
  --config "%SAM2_CFG%" ^
  --mode video ^
  --images_dir images ^
  --out_images_dir images ^
  --out_masks_dir masks

IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] SAM 2 배경 제거 실패 (code %ERRORLEVEL%)
    exit /b 1
)
echo [STEP 1] SAM 2 배경 제거 완료
echo   images\          : 배경 제거된 이미지 (3DGS 입력)
echo   images_masked\   : 별도 저장본
echo   masks\           : 바이너리 마스크
echo   images_original\ : 원본 백업
echo.

:: ── Step 2: Mobile-GS 학습 ───────────────────────────────────────────────
echo [STEP 2] Mobile-GS Pretrain 시작...
echo   Source : %SOURCE%
echo   Output : %OUTPUT%
echo.

cd /d "%MOBILE_GS_DIR%"

"%GS_ENV%\python.exe" pretrain.py ^
  -s "%SOURCE%" ^
  -m "%OUTPUT%" ^
  --eval ^
  --imp_metric outdoor ^
  --sh_degree 3 ^
  --iterations 30000 ^
  --save_iterations 30000 ^
  --checkpoint_iterations 30000

IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Pretrain 실패 (code %ERRORLEVEL%)
    exit /b 1
)
echo [STEP 2a] Pretrain 완료

echo [STEP 2b] Mobile-GS Fine-tuning 시작...
"%GS_ENV%\python.exe" train.py ^
  -s "%SOURCE%" ^
  -m "%OUTPUT%" ^
  --eval ^
  --start_checkpoint "%OUTPUT%\chkpnt30000.pth"

IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Fine-tuning 실패 (code %ERRORLEVEL%)
    exit /b 1
)

echo.
echo ══════════════════════════════════════════════════════
echo [DONE] 전체 파이프라인 완료
echo   학습 결과 : %OUTPUT%
echo   point_cloud\iteration_30000\ : 최종 PLY
echo ══════════════════════════════════════════════════════
