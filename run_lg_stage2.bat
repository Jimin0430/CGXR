@echo off
SET LG_ENV=C:\Users\USER\anaconda3\envs\lightgaussian
SET "PATH=%LG_ENV%;%LG_ENV%\Library\mingw-w64\bin;%LG_ENV%\Library\usr\bin;%LG_ENV%\Library\bin;%LG_ENV%\Scripts;C:\Users\USER\anaconda3\Scripts;%PATH%"

echo [Stage 2] SH Distillation (35k -> 40k iter)...
cd /d "D:\JM\cgxr\CGXR\LightGaussian\repo"

"%LG_ENV%\python.exe" distill_train.py ^
  -s "D:\JM\cgxr\CGXR\data\lego" ^
  -m "D:\JM\cgxr\CGXR\output_lightgaussian\stage2_distilled" ^
  --start_checkpoint "D:\JM\cgxr\CGXR\output_lightgaussian\stage1_pruned\chkpnt35000.pth" ^
  --iteration 40000 ^
  --teacher_model "D:\JM\cgxr\CGXR\output\chkpnt30000.pth" ^
  --new_max_sh 2 ^
  --position_lr_max_steps 40000 ^
  --enable_covariance ^
  --augmented_view ^
  --white_background

IF %ERRORLEVEL% NEQ 0 (echo [ERROR] Stage 2 failed & exit /b 1)
echo [DONE] Stage 2 complete.
