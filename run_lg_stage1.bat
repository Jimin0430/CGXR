@echo off
SET LG_ENV=C:\Users\USER\anaconda3\envs\lightgaussian
SET "PATH=%LG_ENV%;%LG_ENV%\Library\mingw-w64\bin;%LG_ENV%\Library\usr\bin;%LG_ENV%\Library\bin;%LG_ENV%\Scripts;C:\Users\USER\anaconda3\Scripts;%PATH%"

echo [Stage 1] Prune + Finetune (30k -> 35k iter)...
cd /d "D:\JM\cgxr\CGXR\LightGaussian\repo"

"%LG_ENV%\python.exe" prune_finetune.py ^
  -s "D:\JM\cgxr\CGXR\data\lego" ^
  -m "D:\JM\cgxr\CGXR\output_lightgaussian\stage1_pruned" ^
  --start_checkpoint "D:\JM\cgxr\CGXR\output\chkpnt30000.pth" ^
  --iteration 35000 ^
  --prune_iterations 30001 ^
  --prune_percent 0.66 ^
  --prune_type v_important_score ^
  --prune_decay 1 ^
  --position_lr_max_steps 35000 ^
  --v_pow 0.1 ^
  --white_background

IF %ERRORLEVEL% NEQ 0 (echo [ERROR] Stage 1 failed & exit /b 1)
echo [DONE] Stage 1 complete.
