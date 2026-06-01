@echo off
SETLOCAL ENABLEDELAYEDEXPANSION

REM ============================================================
REM  Full 3DGS + LightGaussian Pipeline
REM  Stages: Train → Prune → Distill → Quantize
REM  Dataset: NeRF synthetic (Blender format) — no COLMAP needed
REM ============================================================

SET ANACONDA=C:\Users\USER\anaconda3
SET "PATH=%ANACONDA%;%ANACONDA%\Library\mingw-w64\bin;%ANACONDA%\Library\usr\bin;%ANACONDA%\Library\bin;%ANACONDA%\Scripts;%PATH%"
CALL "%ANACONDA%\Scripts\activate.bat" "%ANACONDA%"

REM ---- Paths (edit SOURCE to change dataset) ----------------
SET SOURCE=D:\JM\cgxr\CGXR\data\lego
SET MOBILE_GS_DIR=D:\JM\cgxr\CGXR\mobile_gs
SET LG_DIR=D:\JM\cgxr\CGXR\LightGaussian\repo
SET BASE_OUTPUT=D:\JM\cgxr\CGXR\output
SET LG_OUTPUT=D:\JM\cgxr\CGXR\output_lightgaussian

REM Derived paths (do not edit)
SET TRAIN_CKPT=%BASE_OUTPUT%\chkpnt30000.pth
SET STAGE1_OUTPUT=%LG_OUTPUT%\stage1_pruned
SET STAGE1_CKPT=%STAGE1_OUTPUT%\chkpnt35000.pth
SET STAGE2_OUTPUT=%LG_OUTPUT%\stage2_distilled
SET STAGE2_PLY=%STAGE2_OUTPUT%\point_cloud\iteration_40000\point_cloud.ply
SET STAGE3_OUTPUT=%LG_OUTPUT%\stage3_quantized

REM -----------------------------------------------------------
echo.
echo ============================================================
echo  STEP 1a: Mobile-GS Pretrain / Mini-Splatting (30 000 iters)
echo  Source: %SOURCE%
echo ============================================================
CALL conda activate mobile-gs
cd /d "%MOBILE_GS_DIR%"
mkdir "%BASE_OUTPUT%" 2>nul

python pretrain.py ^
  -s "%SOURCE%" ^
  -m "%BASE_OUTPUT%" ^
  --eval ^
  --imp_metric outdoor ^
  --sh_degree 3 ^
  --iterations 30000 ^
  --save_iterations 30000 ^
  --checkpoint_iterations 30000 ^
  --white_background

IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Pretrain failed. Aborting.
    pause & exit /b 1
)
echo [OK] Pretrain complete.

echo.
echo ============================================================
echo  STEP 1b: Mobile-GS Fine-tuning (KD + SVQ)
echo ============================================================
python train.py ^
  -s "%SOURCE%" ^
  -m "%BASE_OUTPUT%" ^
  --eval ^
  --white_background ^
  --start_checkpoint "%TRAIN_CKPT%"

IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Fine-tuning failed. Aborting.
    pause & exit /b 1
)
echo [OK] Fine-tuning complete.

REM -----------------------------------------------------------
echo.
echo ============================================================
echo  STEP 2: LightGaussian Stage 1 - Prune + Finetune
echo ============================================================
CALL conda activate lightgaussian
cd /d "%LG_DIR%"
mkdir "%STAGE1_OUTPUT%" 2>nul

python prune_finetune.py ^
  -s "%SOURCE%" ^
  -m "%STAGE1_OUTPUT%" ^
  --start_checkpoint "%TRAIN_CKPT%" ^
  --iteration 35000 ^
  --prune_iterations 30001 ^
  --prune_percent 0.66 ^
  --prune_type v_important_score ^
  --prune_decay 1 ^
  --position_lr_max_steps 35000 ^
  --v_pow 0.1 ^
  --white_background

IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Stage 1 prune failed. Aborting.
    pause & exit /b 1
)
echo [OK] Stage 1 complete.

REM -----------------------------------------------------------
echo.
echo ============================================================
echo  STEP 3: LightGaussian Stage 2 - SH Distillation
echo ============================================================
mkdir "%STAGE2_OUTPUT%" 2>nul

python distill_train.py ^
  -s "%SOURCE%" ^
  -m "%STAGE2_OUTPUT%" ^
  --start_checkpoint "%STAGE1_CKPT%" ^
  --iteration 40000 ^
  --teacher_model "%TRAIN_CKPT%" ^
  --new_max_sh 2 ^
  --position_lr_max_steps 40000 ^
  --enable_covariance ^
  --augmented_view ^
  --white_background

IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Stage 2 distillation failed. Aborting.
    pause & exit /b 1
)
echo [OK] Stage 2 complete.

REM -----------------------------------------------------------
echo.
echo ============================================================
echo  STEP 4: LightGaussian Stage 3 - VecTree Quantization
echo ============================================================
mkdir "%STAGE3_OUTPUT%" 2>nul

python vectree/vectree.py ^
  --important_score_npz_path "%STAGE2_OUTPUT%" ^
  --input_path "%STAGE2_PLY%" ^
  --save_path "%STAGE3_OUTPUT%" ^
  --vq_ratio 0.6 ^
  --codebook_size 8192

IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Stage 3 quantization failed. Aborting.
    pause & exit /b 1
)

echo.
echo ============================================================
echo  ALL DONE
echo  Base model:       %BASE_OUTPUT%
echo  Stage 1 pruned:   %STAGE1_OUTPUT%
echo  Stage 2 distilled:%STAGE2_OUTPUT%
echo  Final compressed: %STAGE3_OUTPUT%
echo ============================================================
pause
