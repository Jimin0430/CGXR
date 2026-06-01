@echo off
SET ANACONDA=C:\Users\USER\anaconda3
SET ENV=%ANACONDA%\envs\mobile-gs
SET "PATH=%ENV%;%ENV%\Library\mingw-w64\bin;%ENV%\Library\usr\bin;%ENV%\Library\bin;%ENV%\Scripts;%ANACONDA%\Scripts;%PATH%"

SET SOURCE=D:\JM\cgxr\CGXR\data\lego
SET OUTPUT=D:\JM\cgxr\CGXR\output
SET MOBILE_GS=D:\JM\cgxr\CGXR\mobile_gs

cd /d "%MOBILE_GS%"

echo [STEP 1] Mobile-GS Pretrain (Mini-Splatting, 30000 iters)...
"%ENV%\python.exe" pretrain.py ^
  -s "%SOURCE%" ^
  -m "%OUTPUT%" ^
  --eval ^
  --imp_metric outdoor ^
  --sh_degree 3 ^
  --iterations 30000 ^
  --white_background ^
  --save_iterations 30000 ^
  --checkpoint_iterations 30000

IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Pretrain failed with code %ERRORLEVEL%.
    exit /b 1
)
echo [OK] Pretrain complete.

echo.
echo [STEP 2] Mobile-GS Fine-tuning (KD + SVQ)...
"%ENV%\python.exe" train.py ^
  -s "%SOURCE%" ^
  -m "%OUTPUT%" ^
  --eval ^
  --white_background ^
  --start_checkpoint "%OUTPUT%\chkpnt30000.pth"

IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Fine-tuning failed with code %ERRORLEVEL%.
    exit /b 1
)
echo [DONE] Training complete.
