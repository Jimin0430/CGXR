@echo off
SET ANACONDA=C:\Users\USER\anaconda3
SET "PATH=%ANACONDA%;%ANACONDA%\Library\bin;%ANACONDA%\Scripts;%PATH%"
CALL "%ANACONDA%\Scripts\activate.bat" "%ANACONDA%"
CALL conda activate lightgaussian

SET SOURCE=D:\JM\cgxr\CGXR\Extract_SfM
SET STAGE1_CKPT=D:\JM\cgxr\CGXR\output_lightgaussian\stage1_pruned\chkpnt35000.pth
SET TEACHER_CKPT=D:\JM\cgxr\CGXR\output\chkpnt30000.pth
SET OUTPUT=D:\JM\cgxr\CGXR\output_lightgaussian\stage2_distilled

IF NOT EXIST "%STAGE1_CKPT%" (
    echo [ERROR] Stage 1 checkpoint not found: %STAGE1_CKPT%
    echo Run 1_stage1_prune.bat first.
    pause
    exit /b 1
)

echo [Stage 2] SH Distillation...
cd /d "D:\JM\cgxr\CGXR\LightGaussian\repo"

python distill_train.py ^
  -s "%SOURCE%" ^
  -m "%OUTPUT%" ^
  --start_checkpoint "%STAGE1_CKPT%" ^
  --iteration 40000 ^
  --teacher_model "%TEACHER_CKPT%" ^
  --new_max_sh 2 ^
  --position_lr_max_steps 40000 ^
  --enable_covariance ^
  --augmented_view

echo Stage 2 done! Next: 3_stage3_quantize.bat
pause
