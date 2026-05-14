@echo off
SET ANACONDA=C:\Users\USER\anaconda3
SET "PATH=%ANACONDA%;%ANACONDA%\Library\bin;%ANACONDA%\Scripts;%PATH%"
CALL "%ANACONDA%\Scripts\activate.bat" "%ANACONDA%"
CALL conda activate lightgaussian

SET SOURCE=D:\JM\cgxr\CGXR\Extract_SfM
SET CHECKPOINT=D:\JM\cgxr\CGXR\output\chkpnt30000.pth
SET OUTPUT=D:\JM\cgxr\CGXR\output_lightgaussian\stage1_pruned

IF NOT EXIST "%CHECKPOINT%" (
    echo [ERROR] Checkpoint not found: %CHECKPOINT%
    pause
    exit /b 1
)

echo [Stage 1] Pruning + Finetune...
cd /d "D:\JM\cgxr\CGXR\LightGaussian\repo"
mkdir "..\logs" 2>nul

python prune_finetune.py ^
  -s "%SOURCE%" ^
  -m "%OUTPUT%" ^
  --start_checkpoint "%CHECKPOINT%" ^
  --iteration 35000 ^
  --prune_percent 0.66 ^
  --prune_type v_important_score ^
  --prune_decay 1 ^
  --position_lr_max_steps 35000 ^
  --v_pow 0.1

echo Stage 1 done! Next: 2_stage2_distill.bat
pause
